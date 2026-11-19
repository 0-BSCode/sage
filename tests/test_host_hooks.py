import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from test_session_context import SessionFixture, ROOT
import host_hooks as hh
import session_context as sc


class HostHooks(SessionFixture):
    def event(self, host='claude-code', event='Stop', sid='parent', **fields):
        return hh.handle(host, event, dict({'session_id':sid, 'cwd':'/unrelated'}, **fields), ROOT)

    def test_startup_context_in_both_hosts_without_activation(self):
        for host in sc.HOSTS:
            output = self.event(host, 'SessionStart')
            text = output['hookSpecificOutput']['additionalContext']
            self.assertIn(host, text); self.assertIn('parent', text)
            self.assertFalse(sc.inspect(host, 'parent').get('active'))

    def test_inactive_session_inside_learning_root_has_no_effect(self):
        self.assertEqual(self.event(cwd=str(self.learning)), {})
        self.assertEqual(self.event(event='SubagentStop', agent_type='verification-gate'), {})

    def test_missing_identity_and_bad_json_are_visible_but_not_blocking(self):
        output = hh.handle('codex', 'Stop', {}, ROOT)
        self.assertIn('unavailable', output['systemMessage'])
        self.assertNotIn('decision', output)
        run = subprocess.run([sys.executable, str(ROOT / 'tools/host_hooks.py'),
                              '--host', 'codex', '--event', 'Stop'],
                             input='bad-json', text=True, capture_output=True)
        self.assertEqual(run.returncode, 0)
        self.assertIn('SAGE CAPABILITY', json.loads(run.stdout)['systemMessage'])

    def test_parent_operation_correlation_does_not_imply_success(self):
        for host in sc.HOSTS:
            self.activate(host)
            token = sc.start(host, 'parent', 'verification-gate', 'verify-cards')['token']
            self.event(host, 'SubagentStart', agent_id='child', sage_operation_token=token)
            self.event(host, 'SubagentStop', agent_id='child', sage_operation_token=token)
            state = sc.inspect(host, 'parent')
            self.assertEqual(state['operations'][token]['agent_id'], 'child')
            self.assertFalse(state['cards_verified'])
            sc.complete(host, 'parent', token, 'completed', 'child')
            self.assertTrue(sc.inspect(host, 'parent')['cards_verified'])

    def test_ambiguous_subagent_does_not_claim_pending_operation(self):
        self.activate()
        token = sc.start('claude-code', 'parent', 'verification-gate', 'verify-cards')['token']
        self.event(event='SubagentStop', agent_id='some-worker')
        self.assertIsNone(sc.inspect('claude-code', 'parent')['operations'][token]['agent_id'])

    def test_other_installation_does_not_mutate_state(self):
        self.activate()
        output = hh.handle('claude-code', 'Stop', {'session_id': 'parent'}, self.home)
        self.assertIn('another Sage installation', output['systemMessage'])

    def test_learning_access_failure_and_end_cleanup(self):
        self.activate()
        self.learning.rmdir()
        with self.assertRaises(OSError):
            self.event()
        self.event(event='SessionEnd')
        self.assertFalse(sc.inspect('claude-code', 'parent')['active'])
