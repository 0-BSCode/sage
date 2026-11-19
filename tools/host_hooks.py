#!/usr/bin/env python3
"""Thin host event adapters over shared Sage session state (Python stdlib only)."""
import argparse
import json
from pathlib import Path
import sys

from cross_refs_check import check
from session_context import HOSTS, inspect, locked, state_directory


def context(host, payload):
    if host not in HOSTS or not isinstance(payload, dict):
        raise ValueError('Unsupported host or payload')
    sid = payload.get('session_id')
    if not isinstance(sid, str) or not sid.strip():
        raise ValueError('Hook did not supply a parent session_id')
    # Both supported adapters take parent identity from the native session_id.
    # Do not substitute agent_id, cwd, or a newest-session marker.
    return dict(host=host, session_id=sid,
                recursive=payload.get('stop_hook_active') is True,
                agent_id=payload.get('agent_id'))


def additional(event, text):
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}


def handle(host, event, payload, root):
    try:
        ctx = context(host, payload)
    except ValueError as exc:
        # A missing identity cannot safely select any session to block.
        return {'systemMessage': '[SAGE CAPABILITY] Automatic safeguards unavailable: %s' % exc}
    sid = ctx['session_id']
    if event == 'SessionStart':
        from plugin_root import validate
        root = validate(root)
        return additional(event, '[SAGE HOST CONTEXT] ' + json.dumps(
            dict(host=host, session_id=sid, sage_root=str(root))) +
            '\nUse this parent identity only when Sage is explicitly invoked. '
            'Loading the plugin does not activate teaching safeguards.')
    state = inspect(host, sid)
    if not state.get('active'):
        return {}
    # An event from a different plugin copy must not mutate another copy's state.
    if Path(state['sage_root']).resolve() != Path(root).resolve():
        return {'systemMessage': '[SAGE CAPABILITY] Active session belongs to another Sage installation; invoke Sage again to rebind.'}
    if event == 'SessionEnd':
        with locked(host, sid) as current:
            current.update(active=False, operations={})
        return {}
    if event == 'Stop':
        if ctx['recursive']:
            return {}
        learning = Path(state['learning_root'])
        if not learning.is_dir():
            raise OSError('Active learning directory is unavailable: %s' % learning)
        reason = check(str(learning), strict=True)
        reminder = None
        with locked(host, sid) as current:
            if current.get('counter') is not None:
                current['counter'] += 1
                if current['counter'] >= 5 and not current.get('warned'):
                    current['warned'] = True
                    reminder = '[VERIFICATION OVERDUE] %s responses since verification. Batch-verify recent factual claims before continuing.' % current['counter']
        result = {'decision': 'block', 'reason': reason} if reason else {}
        if reminder:
            result['systemMessage'] = reminder
        return result
    # Subagent events are lifecycle observations, not proof of verification.
    # Explicit operation tokens handle generic/native workers with no prompt field.
    if event in ('SubagentStart', 'SubagentStop'):
        token = payload.get('sage_operation_token')
        # Token can be explicitly supplied by adapters that support metadata.
        # No ambiguous "most recent pending operation" correlation is performed.
        if token and ctx['agent_id']:
            with locked(host, sid) as current:
                op = current.get('operations', {}).get(token)
                if op:
                    op['agent_id'] = ctx['agent_id']
        return {}
    return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=HOSTS, required=True)
    parser.add_argument('--event', required=True,
                        choices=('SessionStart', 'SessionEnd', 'SubagentStart', 'SubagentStop', 'Stop'))
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
        output = handle(args.host, args.event, payload, Path(__file__).resolve().parent.parent)
    except (ValueError, OSError, KeyError) as exc:
        output = {'systemMessage': '[SAGE CAPABILITY] Automatic check could not run: %s' % exc}
    if output:
        print(json.dumps(output))


if __name__ == '__main__':
    main()
