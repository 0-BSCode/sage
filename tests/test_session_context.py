import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import session_context as sc
import host_hooks as hh

ROOT = Path(__file__).resolve().parents[1]


class SessionFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.learning = self.home / 'Learning'
        self.learning.mkdir()
        self.env = patch.dict(os.environ, HOME=str(self.home), SAGE_LEARNING_ROOT=str(self.learning))
        self.env.start(); self.addCleanup(self.env.stop)

    def activate(self, host='claude-code', sid='parent'):
        return sc.activate(host, sid, ROOT, 'learn topic')



class SessionCase(SessionFixture):
    def test_routing_does_not_activate_non_learning_requests(self):
        for request in ('', 'learn', 'archive topic', 'unknown topic'):
            self.assertFalse(sc.activate('codex', 'parent', ROOT, request)['active'])
        self.assertEqual(sc.inspect('codex', 'parent'), {})

    def test_paths_and_host_namespace(self):
        state = self.activate(sid='../../not-a-path')
        self.assertEqual(state['learning_root'], str(self.learning))
        self.assertNotIn('..', sc.state_directory('claude-code', '../../not-a-path').name)
        self.assertEqual(sc.inspect('codex', '../../not-a-path'), {})
        with self.assertRaises(ValueError):
            sc.inspect('codex', '')
        with self.assertRaises(ValueError):
            sc.activate('codex', 'x', self.home, 'learn topic')

    def test_failed_verification_does_not_reset_or_mark_cards(self):
        self.activate()
        token = sc.start('claude-code', 'parent', 'verification-gate', 'verify-cards')['token']
        sc.complete('claude-code', 'parent', token, 'failed')
        state = sc.inspect('claude-code', 'parent')
        self.assertIsNone(state['counter']); self.assertFalse(state['cards_verified'])
        self.assertIn('CHECKPOINT GUARD', sc.start('claude-code', 'parent', 'artifact-clerk', 'checkpoint', True)['warning'])

    def test_complete_is_idempotent_and_session_specific(self):
        self.activate(); self.activate('codex')
        token = sc.start('claude-code', 'parent', 'verification-gate', 'verify-cards')['token']
        sc.complete('claude-code', 'parent', token, 'completed', 'worker')
        sc.complete('claude-code', 'parent', token, 'completed', 'worker')
        self.assertTrue(sc.inspect('claude-code', 'parent')['cards_verified'])
        self.assertFalse(sc.inspect('codex', 'parent')['cards_verified'])
        with self.assertRaises(ValueError):
            sc.complete('codex', 'parent', token, 'completed')
        with self.assertRaises(ValueError):
            sc.complete('claude-code', 'parent', token, 'failed')

    def test_close_requires_successful_checkpoint_and_clean_validation(self):
        self.activate()
        with self.assertRaises(ValueError):
            sc.close('claude-code', 'parent')
        self.assertFalse(sc.close_if_clean('claude-code', 'parent', {'errors': ['write failed']}))
        self.assertFalse(sc.close_if_clean('claude-code', 'parent', {'cross_refs_stale': 'stale'}))
        self.assertTrue(sc.inspect('claude-code', 'parent')['active'])
        self.assertTrue(sc.close_if_clean('claude-code', 'parent', {}))
        self.assertFalse(sc.inspect('claude-code', 'parent')['active'])
        self.assertTrue(self.activate()['active'])

    def test_override_is_bound_and_new_journey_resets_cycle(self):
        self.activate()
        other = self.home / 'Other'; other.mkdir()
        with patch.dict(os.environ, SAGE_LEARNING_ROOT=str(other)):
            self.assertEqual(sc.inspect('claude-code', 'parent')['learning_root'], str(self.learning))
            sc.activate('claude-code', 'parent', ROOT, 'learn different')
        self.assertEqual(sc.inspect('claude-code', 'parent')['learning_root'], str(other))

    def test_new_sitting_requires_its_own_checkpoint(self):
        for host in sc.HOSTS:
            first = self.activate(host)
            token = sc.start(host, 'parent', 'artifact-clerk', 'checkpoint')['token']
            sc.complete(host, 'parent', token, 'completed')
            verify = sc.start(host, 'parent', 'verification-gate', 'verify-cards')['token']
            sc.complete(host, 'parent', verify, 'completed')
            second = self.activate(host)
            self.assertNotEqual(first['sitting_id'], second['sitting_id'])
            self.assertFalse(second['cards_verified'])
            self.assertIsNone(second['counter'])
            self.assertFalse(second['warned'])
            with self.assertRaisesRegex(ValueError, 'checkpoint'):
                sc.close(host, 'parent')
            with self.assertRaisesRegex(ValueError, 'earlier learning sitting'):
                sc.complete(host, 'parent', verify, 'completed')
            self.assertFalse(sc.close_if_clean(host, 'parent', {}, first['sitting_id']))
            checkpoint = sc.start(host, 'parent', 'artifact-clerk', 'checkpoint')['token']
            sc.complete(host, 'parent', checkpoint, 'completed')
            with patch('session_wrapup.run', return_value={'blocking_errors': [], 'warnings': ['duration unavailable']}):
                self.assertTrue(sc.close(host, 'parent')['session_closed'])

    def test_optional_wrapup_failures_allow_close_but_integrity_failures_block(self):
        for host in sc.HOSTS:
            self.activate(host)
            token = sc.start(host, 'parent', 'artifact-clerk', 'checkpoint')['token']
            sc.complete(host, 'parent', token, 'completed')
            with patch.dict(os.environ, CLAUDE_CODE_SESSION_ID='missing-transcript'), \
                    patch('session_wrapup.run_script', return_value=(False, 'unavailable')), \
                    patch('cross_refs_check.check', side_effect=PermissionError('denied')):
                blocked = sc.close(host, 'parent')
            self.assertFalse(blocked['session_closed'])
            self.assertTrue(blocked['blocking_errors'])
            with patch.dict(os.environ, CLAUDE_CODE_SESSION_ID='missing-transcript'), \
                    patch('session_wrapup.run_script', return_value=(False, 'unavailable')), \
                    patch('cross_refs_check.check', return_value=None):
                closed = sc.close(host, 'parent')
            self.assertTrue(closed['session_closed'])
            self.assertIsNone(closed['duration'])
            self.assertTrue(any('session_duration' in warning for warning in closed['warnings']))
            self.assertTrue(any('coach_metrics' in warning for warning in closed['warnings']))
            self.assertEqual(closed['blocking_errors'], [])

    def test_invalid_and_denied_state_is_reported(self):
        self.activate()
        directory = sc.state_directory('claude-code', 'parent')
        (directory / 'state.json').write_text('not-json')
        with self.assertRaises(ValueError):
            sc.inspect('claude-code', 'parent')
        with patch.object(Path, 'mkdir', side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError):
                self.activate('codex')

    def test_learning_permission_failure_does_not_create_fallback(self):
        with patch.object(sc.os, 'access', return_value=False):
            with self.assertRaises(PermissionError):
                self.activate()
        self.assertEqual(sc.inspect('claude-code', 'parent'), {})
        self.assertFalse((self.home / 'topic').exists())

    def test_cross_process_atomic_operations(self):
        self.activate()
        def operation(_):
            result = subprocess.run([sys.executable, str(ROOT / 'tools/session_context.py'),
                '--host', 'claude-code', '--session-id', 'parent', 'start',
                'assessment-agent', 'select-and-prepare'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)['token']
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            tokens = list(pool.map(operation, range(12)))
        self.assertEqual(len(set(tokens)), 12)
        self.assertEqual(len(sc.inspect('claude-code', 'parent')['operations']), 12)
