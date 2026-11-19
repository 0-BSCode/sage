"""An installed plugin must not depend on the development checkout or cwd."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ResourcePaths(unittest.TestCase):
    def test_relocated_copy_and_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            plugin = temp / 'plugin with spaces'
            for name in ('skills', 'agents', 'tools'):
                shutil.copytree(ROOT / name, plugin / name,
                                ignore=shutil.ignore_patterns('__pycache__'))
            link = temp / 'linked-skill'
            link.symlink_to(plugin / 'skills/sage', target_is_directory=True)
            env = dict(os.environ, SAGE_ROOT='/not/the/plugin')
            result = subprocess.run(
                [sys.executable, str(plugin / 'tools/plugin_root.py'),
                 str(link / 'SKILL.md')], cwd=temp, env=env,
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(plugin.resolve()))
            bad = subprocess.run(
                [sys.executable, str(plugin / 'tools/plugin_root.py'),
                 str(link / 'SKILL.md'), '--root', str(temp)],
                capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)

    def test_no_global_root_bootstrap_in_protocols(self):
        files = list((ROOT / 'skills/sage').rglob('*.md'))
        files += list((ROOT / 'agents').glob('*.md'))
        for path in files:
            self.assertNotIn('/tmp/.sage-', path.read_text(), str(path))
