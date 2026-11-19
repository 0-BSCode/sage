from test_session_context import SessionFixture, ROOT
import session_context as sc
import host_hooks as hh

class VerificationCounter(SessionFixture):
    def test_threshold_and_once_per_cycle(self):
        for host in sc.HOSTS:
            self.activate(host)
            self.assertEqual(hh.handle(host,'Stop',{'session_id':'parent'},ROOT), {})
            token=sc.start(host,'parent','verification-gate','verify-claims')['token']
            sc.complete(host,'parent',token,'completed')
            for _ in range(4):
                self.assertEqual(hh.handle(host,'Stop',{'session_id':'parent'},ROOT), {})
            self.assertIn('VERIFICATION OVERDUE', hh.handle(host,'Stop',{'session_id':'parent'},ROOT)['systemMessage'])
            self.assertEqual(hh.handle(host,'Stop',{'session_id':'parent'},ROOT), {})

    def test_recursive_stop_is_not_counted(self):
        self.activate()
        token=sc.start('claude-code','parent','verification-gate','verify-claims')['token']
        sc.complete('claude-code','parent',token,'completed')
        self.assertEqual(hh.handle('claude-code','Stop',{'session_id':'parent','stop_hook_active':True},ROOT), {})
        self.assertEqual(sc.inspect('claude-code','parent')['counter'],0)
