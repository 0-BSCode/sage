"""Real writers and router run from two relocated host plugin installations."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from test_session_context import SessionFixture, ROOT
import session_context as sc
import session_wrapup
from unittest.mock import patch


class CrossHostResume(SessionFixture):
    def tool(self, root, name, *args, data=None):
        result = subprocess.run([sys.executable, str(root / 'tools' / name)] + list(args),
            input=json.dumps(data) if data is not None else None,
            cwd=self.home, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(result.stdout.startswith('Error:'), result.stdout)
        return result.stdout

    def test_checkpoint_records_resume_in_both_directions(self):
        copies = []
        for name in ('claude-copy', 'codex-copy'):
            root = self.home / name
            for directory in ('tools', 'agents', 'skills'):
                shutil.copytree(ROOT / directory, root / directory,
                                ignore=shutil.ignore_patterns('__pycache__'))
            copies.append(root)
        for first, second in ((0, 1), (1, 0)):
            with self.subTest(first=first):
                hosts = ('claude-code', 'codex')
                request = 'learn transfer-%s' % first
                state = sc.activate(hosts[first], 'write-%s' % first, copies[first], request)
                topic = Path(state['topic_path']); topic.mkdir(parents=True)
                (topic / 'plan.md').write_text('# Plan\nM2: apply retrieval\nNext: explain failure cases\n')
                (topic / 'weak-spots.md').write_text('M1: confuses recall with exposure\n')
                (topic / 'cards.md').write_text('# Flashcards: transfer\n\nLast updated: 2026-11-17\n\n---\n')
                self.tool(copies[first], 'srs/card_writer.py', 'append', str(topic), '--stdin', data=[{
                    'question':'What is retrieval practice?', 'answer':'Recall from memory.',
                    'tags':['type:fact','learning']}])
                self.tool(copies[first], 'srs/journal_writer.py', 'append', str(topic), '--stdin', data={
                    'session_number':1, 'date':'2026-11-17', 'type':'learn',
                    'focus':'M2 retrieval', 'summary':'Next: explain failure cases',
                    'review_count':1, 'avg_grade':3})
                (topic / 'journal/session-01.md').write_text('# Savepoint\nNext: explain failure cases\n')
                (topic / 'knowledge-map.md').write_text('# Knowledge Map\n| retrieval | developing |\n')
                self.tool(copies[first], 'srs/srs_engine.py', 'init', str(topic))
                self.tool(copies[first], 'srs/srs_engine.py', 'sync', str(topic))
                before = {str(p.relative_to(topic)):p.read_bytes() for p in topic.rglob('*') if p.is_file()}
                output = json.loads(self.tool(copies[second], 'session_router.py', str(copies[second]), request))
                self.assertEqual(output['mode'], 'resume')
                self.assertEqual(Path(output['topic_path']), topic)
                resumed = sc.activate(hosts[second], 'read-%s' % first, copies[second], request)
                self.assertEqual(resumed['topic_path'], str(topic))
                brief = sc.start(hosts[second], 'read-%s' % first, 'artifact-clerk', 'brief')
                self.assertTrue(brief['token'])
                self.assertIn('Operation: `brief`', (copies[second] / 'agents/artifact-clerk.md').read_text())
                due = json.loads(self.tool(copies[second], 'srs/srs_engine.py', 'due', str(topic), '--json'))
                self.assertGreater(due['count'], 0)
                self.assertEqual(before, {str(p.relative_to(topic)):p.read_bytes() for p in topic.rglob('*') if p.is_file()})
                self.assertIn('explain failure cases', (topic/'journal/session-01.md').read_text())
                self.assertIn('exposure', (topic/'weak-spots.md').read_text())

    def test_close_uses_bound_root_and_keeps_failed_validation_active(self):
        self.activate()
        token=sc.start('claude-code','parent','artifact-clerk','checkpoint')['token']
        sc.complete('claude-code','parent',token,'completed')
        with patch.object(session_wrapup,'run',return_value={'errors':[], 'cross_refs_stale':'stale'}) as run:
            self.assertFalse(sc.close('claude-code','parent')['session_closed'])
            self.assertEqual(run.call_args.kwargs['learning_root'],str(self.learning))
        with patch.object(session_wrapup,'run',return_value={'errors':[], 'cross_refs_stale':None}):
            self.assertTrue(sc.close('claude-code','parent')['session_closed'])

    def test_resume_marks_interrupted_operations_failed(self):
        self.activate()
        token=sc.start('claude-code','parent','assessment-agent','select-and-prepare')['token']
        self.activate()
        self.assertEqual(sc.inspect('claude-code','parent')['operations'][token]['status'],'failed')
