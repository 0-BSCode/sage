#!/usr/bin/env python3
"""Regression-safety tests for enforce-cross-refs.sh hook."""

import json
import os
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path

SCRIPT = str(
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "scripts"
    / "enforce-cross-refs.sh"
)


class TestEnforceCrossRefs(unittest.TestCase):
    """Test the Stop enforce-cross-refs hook via subprocess.

    Uses SAGE_DIR env var override so tests run against a temp
    directory instead of the hardcoded path.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.session_id = f"test-{uuid.uuid4().hex[:8]}"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, input_json: dict) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["SAGE_DIR"] = self.tmpdir
        return subprocess.run(
            ["bash", SCRIPT],
            input=json.dumps(input_json),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

    def _base_input(self, cwd: str, stop_hook_active: bool = False) -> dict:
        return {
            "cwd": cwd,
            "stop_hook_active": stop_hook_active,
            "session_id": self.session_id,
        }

    def _touch(self, path: str, mtime: float | None = None):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
        if mtime is not None:
            os.utime(path, (mtime, mtime))

    # ------------------------------------------------------------------
    # Not in sage repo -- exits 0
    # ------------------------------------------------------------------
    def test_not_in_sage_repo_exits_zero(self):
        inp = self._base_input("/some/other/project")
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("block", result.stdout)

    # ------------------------------------------------------------------
    # Knowledge map not recently modified -- exits 0
    # ------------------------------------------------------------------
    def test_kmap_not_recent_exits_zero(self):
        kmap = os.path.join(self.tmpdir, "knowledge-map.md")
        old_time = time.time() - 7200
        self._touch(kmap, mtime=old_time)

        inp = self._base_input(self.tmpdir)
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("block", result.stdout)

    # ------------------------------------------------------------------
    # Knowledge map modified, cross-refs updated -- exits 0
    # ------------------------------------------------------------------
    def test_kmap_modified_crossrefs_updated_exits_zero(self):
        now = time.time()
        kmap = os.path.join(self.tmpdir, "knowledge-map.md")
        self._touch(kmap, mtime=now)

        cr_dir = os.path.join(self.tmpdir, "cross-refs")
        os.makedirs(cr_dir, exist_ok=True)
        cr_file = os.path.join(cr_dir, "test-project.md")
        self._touch(cr_file, mtime=now)

        inp = self._base_input(self.tmpdir)
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("block", result.stdout)

    # ------------------------------------------------------------------
    # Knowledge map modified, cross-refs stale -- blocks
    # ------------------------------------------------------------------
    def test_kmap_modified_crossrefs_stale_blocks(self):
        now = time.time()
        kmap = os.path.join(self.tmpdir, "knowledge-map.md")
        self._touch(kmap, mtime=now)

        cr_dir = os.path.join(self.tmpdir, "cross-refs")
        os.makedirs(cr_dir, exist_ok=True)
        cr_file = os.path.join(cr_dir, "test-project.md")
        old_time = now - 7200
        self._touch(cr_file, mtime=old_time)

        inp = self._base_input(self.tmpdir)
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertIn("block", result.stdout)

    # ------------------------------------------------------------------
    # Legacy cross-references.md fallback works
    # ------------------------------------------------------------------
    def test_legacy_crossrefs_fallback(self):
        now = time.time()
        kmap = os.path.join(self.tmpdir, "knowledge-map.md")
        self._touch(kmap, mtime=now)

        legacy_file = os.path.join(self.tmpdir, "cross-references.md")
        self._touch(legacy_file, mtime=now)

        inp = self._base_input(self.tmpdir)
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("block", result.stdout)

    # ------------------------------------------------------------------
    # No knowledge-map.md exists -- exits 0
    # ------------------------------------------------------------------
    def test_no_kmap_exits_zero(self):
        inp = self._base_input(self.tmpdir)
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("block", result.stdout)

    # ------------------------------------------------------------------
    # stop_hook_active prevents execution
    # ------------------------------------------------------------------
    def test_stop_hook_active_exits_zero(self):
        inp = self._base_input(self.tmpdir, stop_hook_active=True)
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("block", result.stdout)

    # ------------------------------------------------------------------
    # Subdirectory of sage still triggers
    # ------------------------------------------------------------------
    def test_subdirectory_triggers(self):
        now = time.time()
        sub = os.path.join(self.tmpdir, "learning", "react")
        os.makedirs(sub, exist_ok=True)

        kmap = os.path.join(self.tmpdir, "knowledge-map.md")
        self._touch(kmap, mtime=now)

        inp = self._base_input(sub)
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertIn("block", result.stdout)

    # ------------------------------------------------------------------
    # Knowledge map modified, no cross-refs at all -- blocks
    # ------------------------------------------------------------------
    def test_kmap_modified_no_crossrefs_blocks(self):
        now = time.time()
        kmap = os.path.join(self.tmpdir, "knowledge-map.md")
        self._touch(kmap, mtime=now)

        inp = self._base_input(self.tmpdir)
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertIn("block", result.stdout)


if __name__ == "__main__":
    unittest.main()
