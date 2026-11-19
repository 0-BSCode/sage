#!/usr/bin/env python3
"""Internal, host-qualified Sage session and specialist-operation state.

Use --help for activation/inspection/operation commands. This is not a public
tutoring CLI. A marker records lifecycle completion, never factual correctness.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

from plugin_root import validate

HOSTS = ('claude-code', 'codex')
CHECKPOINT_WARNING = ('[CHECKPOINT GUARD] This checkpoint includes cards but '
                      'verify-cards has not completed this session. Verify new '
                      'cards before including them in the checkpoint.')


def state_directory(host, session_id):
    if host not in HOSTS or not isinstance(session_id, str) or not session_id.strip():
        raise ValueError('A supported host and explicit parent session ID are required')
    key = hashlib.sha256(session_id.encode('utf-8')).hexdigest()
    return Path.home() / '.config/sage/runtime' / host / key


@contextmanager
def locked(host, session_id):
    directory = state_directory(host, session_id)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    with (directory / 'lock').open('a+b') as lock:
        os.chmod(directory / 'lock', 0o600)
        if os.name == 'nt':
            import msvcrt
            lock.write(b'0'); lock.flush(); lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            path = directory / 'state.json'
            state = json.loads(path.read_text()) if path.exists() else {}
            if not isinstance(state, dict):
                raise ValueError('Invalid Sage session state')
            yield state
            handle, temp = tempfile.mkstemp(dir=str(directory), prefix='state-')
            try:
                with os.fdopen(handle, 'w') as stream:
                    json.dump(state, stream); stream.write('\n')
                os.replace(temp, path)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        finally:
            if os.name == 'nt':
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def inspect(host, session_id):
    directory = state_directory(host, session_id)
    if not (directory / 'state.json').exists():
        return {}
    with locked(host, session_id) as state:
        return dict(state)


def activate(host, session_id, root, request):
    from session_router import route
    root = validate(root)
    result = route(str(root), request)
    if result['mode'] not in ('fresh', 'resume'):
        return {'active': False, 'mode': result['mode']}
    learning = Path(result['learning_root']).expanduser().resolve(strict=True)
    topic = Path(result['topic_path']).resolve()
    if learning not in topic.parents:
        raise ValueError('Topic must be inside the configured learning directory')
    if not os.access(str(learning), os.R_OK | os.W_OK | os.X_OK):
        raise PermissionError('Learning directory is not readable/writable: %s' % learning)
    with locked(host, session_id) as state:
        # Preserve history only while bound to the same journey.
        same = (state.get('active') and state.get('topic_path') == str(topic)
                and state.get('sage_root') == str(root))
        if not same:
            state.clear()
            state.update(operations={}, counter=None, warned=False, cards_verified=False)
        else:
            # An explicit new learn/resume invocation starts a new execution
            # boundary; unfinished workers from the previous sitting are not
            # silently considered successful and must not prevent recovery.
            for op in state.get('operations', {}).values():
                if op.get('status') == 'running':
                    op['status'] = 'failed'
        state.update(active=True, host=host, session_id=session_id,
                     sitting_id=uuid.uuid4().hex, counter=None, warned=False,
                     cards_verified=False,
                     sage_root=str(root), learning_root=str(learning), topic_path=str(topic))
        return dict(state)


def start(host, session_id, clerk, operation, cards=False):
    with locked(host, session_id) as state:
        if not state.get('active'):
            raise ValueError('Activate Sage in this parent session first')
        if (clerk not in ('artifact-clerk', 'assessment-agent', 'verification-gate',
                          'reference-clerk', 'demo-generator', 'capstone-architect')
                or not (Path(state['sage_root']) / 'agents' / (clerk + '.md')).is_file()):
            raise ValueError('Unknown specialist')
        warning = None
        if clerk == 'artifact-clerk' and operation == 'checkpoint':
            if cards and not state.get('cards_verified'):
                warning = CHECKPOINT_WARNING
            state['cards_verified'] = False
        token = uuid.uuid4().hex
        state['operations'][token] = dict(clerk=clerk, operation=operation,
                                        sitting_id=state['sitting_id'], status='running', agent_id=None)
        return dict(token=token, warning=warning)


def complete(host, session_id, token, status, agent_id=None):
    if status not in ('completed', 'failed'):
        raise ValueError('Invalid operation status')
    with locked(host, session_id) as state:
        if not state.get('active'):
            raise ValueError('Sage session is inactive')
        op = state.get('operations', {}).get(token)
        if not op:
            raise ValueError('Unknown operation token for this parent session')
        if op.get('sitting_id') != state.get('sitting_id'):
            raise ValueError('Operation belongs to an earlier learning sitting')
        if op['status'] != 'running':
            if op['status'] != status:
                raise ValueError('Operation already finished with another outcome')
            return dict(status=status)
        op.update(status=status, agent_id=agent_id or op.get('agent_id'))
        if status == 'completed':
            if op['clerk'] == 'verification-gate':
                state.update(counter=0, warned=False)
                if op['operation'] == 'verify-cards':
                    state['cards_verified'] = True
            if op['clerk'] == 'artifact-clerk' and op['operation'] == 'checkpoint':
                if state.get('counter') is not None:
                    state['counter'] = 0
                state['warned'] = False
        return dict(status=status)


def close_if_clean(host, session_id, result, sitting_id=None):
    if result.get('blocking_errors', result.get('errors')) or result.get('cross_refs_stale'):
        return False
    with locked(host, session_id) as state:
        if sitting_id is not None and state.get('sitting_id') != sitting_id:
            return False
        if state.get('active'):
            state['active'] = False
            state['operations'] = {}
    return True


def close(host, session_id):
    from session_wrapup import run
    state = inspect(host, session_id)
    if not state.get('active'):
        raise ValueError('Sage session is inactive')
    operations = [op for op in state.get('operations', {}).values()
                  if state.get('sitting_id') and op.get('sitting_id') == state['sitting_id']]
    checkpoints = [op for op in operations if op['clerk'] == 'artifact-clerk'
                   and op['operation'] == 'checkpoint']
    if not checkpoints or checkpoints[-1]['status'] != 'completed':
        raise ValueError('Complete the checkpoint successfully before closing')
    if any(op['status'] == 'running' for op in operations):
        raise ValueError('Finish pending specialist operations before closing')
    result = run(state['sage_root'], state['topic_path'],
                 learning_root=state['learning_root'])
    result['session_closed'] = close_if_clean(host, session_id, result, state['sitting_id'])
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', choices=HOSTS, required=True)
    p.add_argument('--session-id', required=True, help='Parent identity from startup context; never guess')
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('activate'); a.add_argument('--root', required=True); a.add_argument('--request', required=True)
    sub.add_parser('inspect')
    sub.add_parser('close', help='Validate wrap-up after checkpoint; close only if clean')
    s = sub.add_parser('start'); s.add_argument('clerk'); s.add_argument('operation'); s.add_argument('--cards', action='store_true')
    c = sub.add_parser('complete'); c.add_argument('token'); c.add_argument('--status', choices=('completed', 'failed'), required=True); c.add_argument('--agent-id')
    args = p.parse_args()
    try:
        if args.command == 'activate':
            result = activate(args.host, args.session_id, args.root, args.request)
        elif args.command == 'inspect':
            result = inspect(args.host, args.session_id)
        elif args.command == 'start':
            result = start(args.host, args.session_id, args.clerk, args.operation, args.cards)
        elif args.command == 'close':
            result = close(args.host, args.session_id)
        else:
            result = complete(args.host, args.session_id, args.token, args.status, args.agent_id)
        print(json.dumps(result))
    except (OSError, ValueError, KeyError) as exc:
        p.exit(1, 'Sage session state unavailable: %s\n' % exc)


if __name__ == '__main__':
    main()
