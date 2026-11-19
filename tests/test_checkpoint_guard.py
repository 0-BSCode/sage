from test_session_context import SessionFixture
import session_context as sc

class CheckpointGuard(SessionFixture):
    def test_warning_and_marker_consumption_in_both_hosts(self):
        for host in sc.HOSTS:
            self.activate(host)
            warning = sc.start(host, 'parent', 'artifact-clerk', 'checkpoint', True)
            self.assertIn('CHECKPOINT GUARD', warning['warning'])
            token = sc.start(host, 'parent', 'verification-gate', 'verify-cards')['token']
            sc.complete(host, 'parent', token, 'completed')
            self.assertIsNone(sc.start(host, 'parent', 'artifact-clerk', 'checkpoint', True)['warning'])
            self.assertIn('CHECKPOINT GUARD', sc.start(host, 'parent', 'artifact-clerk', 'checkpoint', True)['warning'])

    def test_checkpoint_without_cards_has_no_warning(self):
        self.activate()
        self.assertIsNone(sc.start('claude-code', 'parent', 'artifact-clerk', 'checkpoint')['warning'])
