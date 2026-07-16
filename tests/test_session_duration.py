#!/usr/bin/env python3
"""Tests for session_duration.py — current-sitting wall time from a transcript.

Covers:
- current_sitting counts only the last sitting when a >30min gap exists
- current_sitting returns the full span when there is no big gap
- fmt_duration formatting (s / m / h)
- project_dir encodes every non-alphanumeric char as '-' (slash AND dot)
- find_transcript prefers session_id, falls back to most-recent .jsonl
- run() end-to-end against a fixture transcript
- missing transcript -> run() None and CLI non-zero exit
- lines without timestamps are ignored
"""

import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import session_duration as sd  # noqa: E402

TOOL = Path(__file__).resolve().parent.parent / "tools" / "session_duration.py"


def _dt(iso):
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))


class TestCurrentSitting(unittest.TestCase):
    def test_last_sitting_only_after_big_gap(self):
        stamps = [
            _dt("2026-01-01T00:00:00Z"),
            _dt("2026-01-01T00:05:00Z"),
            # >30min gap here
            _dt("2026-01-01T01:05:00Z"),
            _dt("2026-01-01T01:20:00Z"),
            _dt("2026-01-01T01:30:00Z"),
        ]
        start, end = sd.current_sitting(stamps)
        self.assertEqual(start, _dt("2026-01-01T01:05:00Z"))
        self.assertEqual(end, _dt("2026-01-01T01:30:00Z"))

    def test_no_gap_returns_full_span(self):
        stamps = [
            _dt("2026-01-01T00:00:00Z"),
            _dt("2026-01-01T00:10:00Z"),
            _dt("2026-01-01T00:20:00Z"),
        ]
        start, end = sd.current_sitting(stamps)
        self.assertEqual(start, stamps[0])
        self.assertEqual(end, stamps[-1])

    def test_empty_returns_none(self):
        self.assertIsNone(sd.current_sitting([]))


class TestFmtDuration(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(sd.fmt_duration(45_000), "45s")

    def test_minutes(self):
        self.assertEqual(sd.fmt_duration(25 * 60 * 1000), "25m00s")

    def test_hours(self):
        self.assertEqual(sd.fmt_duration((2 * 3600 + 5 * 60 + 3) * 1000), "2h05m03s")


class TestProjectDir(unittest.TestCase):
    def test_encodes_slash_and_dot(self):
        pdir = sd.project_dir("/home/u/.claude/commands")
        self.assertTrue(pdir.endswith("-home-u--claude-commands"))

    def test_preserves_case_and_hyphen(self):
        pdir = sd.project_dir("/home/b/Documents/sage-plugin")
        self.assertTrue(pdir.endswith("-home-b-Documents-sage-plugin"))


class TestTranscriptLookupAndRun(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self._orig_home = os.environ.get("HOME")
        os.environ["HOME"] = self.home
        self.cwd = "/fake/project"
        self.pdir = sd.project_dir(self.cwd)
        os.makedirs(self.pdir, exist_ok=True)

    def tearDown(self):
        if self._orig_home is not None:
            os.environ["HOME"] = self._orig_home
        else:
            del os.environ["HOME"]
        import shutil

        shutil.rmtree(self.home, ignore_errors=True)

    def _write_transcript(self, name, timestamps, extra_noise=True):
        path = os.path.join(self.pdir, name)
        with open(path, "w") as f:
            if extra_noise:
                # metadata lines without a timestamp — must be ignored
                f.write(json.dumps({"type": "summary", "leafUuid": "x"}) + "\n")
            for ts in timestamps:
                f.write(json.dumps({"type": "assistant", "timestamp": ts}) + "\n")
        return path

    def test_find_prefers_session_id(self):
        self._write_transcript("aaa.jsonl", ["2026-01-01T00:00:00Z"])
        self._write_transcript("bbb.jsonl", ["2026-01-02T00:00:00Z"])
        found = sd.find_transcript(session_id="aaa", cwd=self.cwd)
        self.assertTrue(found.endswith("aaa.jsonl"))

    def test_find_falls_back_to_most_recent(self):
        old = self._write_transcript("old.jsonl", ["2026-01-01T00:00:00Z"])
        new = self._write_transcript("new.jsonl", ["2026-01-02T00:00:00Z"])
        os.utime(old, (1_000_000, 1_000_000))
        os.utime(new, (2_000_000, 2_000_000))
        found = sd.find_transcript(session_id="", cwd=self.cwd)
        self.assertTrue(found.endswith("new.jsonl"))

    def test_run_end_to_end_last_sitting(self):
        self._write_transcript(
            "s.jsonl",
            [
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:05:00Z",
                # >30min gap
                "2026-01-01T01:05:00Z",
                "2026-01-01T01:30:00Z",
            ],
        )
        self.assertEqual(sd.run(session_id="s", cwd=self.cwd), "25m00s")

    def test_run_missing_transcript_returns_none(self):
        self.assertIsNone(sd.run(session_id="nope", cwd="/no/such/project"))


class TestCLI(unittest.TestCase):
    def test_missing_transcript_exits_nonzero(self):
        env = dict(os.environ)
        env["HOME"] = tempfile.mkdtemp()
        proc = subprocess.run(
            [sys.executable, str(TOOL), "does-not-exist"],
            capture_output=True,
            text=True,
            cwd="/tmp",
            env=env,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
