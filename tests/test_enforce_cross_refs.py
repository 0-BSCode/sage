from test_session_context import SessionFixture, ROOT
import session_context as sc
import host_hooks as hh

class CrossRefsHook(SessionFixture):
    def test_active_outside_root_blocks_then_clears(self):
        for host in sc.HOSTS:
            self.activate(host)
            topic=self.learning/'topic/learning'
            topic.mkdir(parents=True,exist_ok=True)
            (topic/'knowledge-map.md').write_text('| C1 | solid |')
            output=hh.handle(host,'Stop',{'session_id':'parent','cwd':'/elsewhere'},ROOT)
            self.assertEqual(output['decision'],'block')
            self.assertEqual(hh.handle(host,'Stop',{'session_id':'parent','stop_hook_active':True},ROOT),{})
            refs=self.learning/'cross-refs'; refs.mkdir(exist_ok=True)
            (refs/'topic.md').write_text('C1')
            self.assertNotIn('decision',hh.handle(host,'Stop',{'session_id':'parent','cwd':'/elsewhere'},ROOT))
            (refs/'topic.md').unlink()

    def test_inactive_inside_root_does_not_block(self):
        (self.learning/'knowledge-map.md').write_text('| C1 | mastered |')
        self.assertEqual(hh.handle('codex','Stop',{'session_id':'other','cwd':str(self.learning)},ROOT),{})
