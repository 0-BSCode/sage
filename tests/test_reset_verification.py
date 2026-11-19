from test_session_context import SessionFixture, ROOT
import session_context as sc
import host_hooks as hh

class VerificationReset(SessionFixture):
    def test_success_resets_cycle_but_failed_operation_does_not(self):
        for host in sc.HOSTS:
            self.activate(host)
            token = sc.start(host, 'parent', 'verification-gate', 'verify-claims')['token']
            sc.complete(host, 'parent', token, 'completed')
            for _ in range(6):
                hh.handle(host, 'Stop', {'session_id':'parent'}, ROOT)
            token = sc.start(host, 'parent', 'verification-gate', 'verify-claims')['token']
            sc.complete(host, 'parent', token, 'failed')
            self.assertTrue(sc.inspect(host, 'parent')['warned'])
            token = sc.start(host, 'parent', 'verification-gate', 'verify-claims')['token']
            sc.complete(host, 'parent', token, 'completed')
            self.assertEqual(sc.inspect(host, 'parent')['counter'], 0)
            self.assertFalse(sc.inspect(host, 'parent')['warned'])
