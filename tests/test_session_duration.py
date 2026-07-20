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
- an id is resolved from ANY cwd (the cwd-resolution bug, ADR-0004)
- an unresolvable id fails hard instead of guessing
- $CLAUDE_CODE_SESSION_ID is used when no id is passed; argv overrides it
- the no-id fallback warns that it guessed
- the three failure modes emit distinguishable messages
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
        # The real session's id leaks in from the environment and would be
        # resolved ahead of any fixture. Tests opt in explicitly instead.
        self._orig_sid = os.environ.pop(sd.SESSION_ID_ENV, None)
        self.cwd = "/fake/project"
        self.pdir = sd.project_dir(self.cwd)
        os.makedirs(self.pdir, exist_ok=True)

    def tearDown(self):
        if self._orig_home is not None:
            os.environ["HOME"] = self._orig_home
        else:
            del os.environ["HOME"]
        if self._orig_sid is not None:
            os.environ[sd.SESSION_ID_ENV] = self._orig_sid
        else:
            os.environ.pop(sd.SESSION_ID_ENV, None)
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

    def test_end_is_last_timestamp_not_now(self):
        # A single sitting entirely in the distant past. If the end were derived
        # from datetime.now() instead of stamps[-1], the duration would be years,
        # not the 10-minute transcript span. Pins the deliberate stamps[-1] choice.
        self._write_transcript(
            "past.jsonl",
            ["2020-01-01T00:00:00Z", "2020-01-01T00:10:00Z"],
        )
        self.assertEqual(sd.run(session_id="past", cwd=self.cwd), "10m00s")

    # --- ADR-0004: resolve by session id, never by cwd ---

    def test_id_resolves_from_unrelated_cwd(self):
        # THE regression test. The transcript lives under /fake/project's slug;
        # we look it up from a cwd that has no transcript directory at all.
        # Pre-fix this returned None, and the coach asked for a stopwatch reading.
        self._write_transcript(
            "abc-123.jsonl",
            ["2026-01-01T00:00:00Z", "2026-01-01T00:15:00Z"],
        )
        self.assertEqual(sd.run(session_id="abc-123", cwd="/tmp/somewhere/else"), "15m00s")

    def test_unknown_id_fails_even_when_cwd_dir_exists(self):
        # Pre-fix this silently returned the newest transcript's duration, exit 0.
        self._write_transcript("real.jsonl", ["2026-01-01T00:00:00Z", "2026-01-01T00:15:00Z"])
        duration, error, _ = sd.compute(session_id="not-a-real-id", cwd=self.cwd)
        self.assertIsNone(duration)
        self.assertIn("not-a-real-id", error)
        self.assertIn("refusing to guess", error)

    def test_env_var_used_when_no_argument(self):
        self._write_transcript("from-env.jsonl", ["2026-01-01T00:00:00Z", "2026-01-01T00:20:00Z"])
        os.environ[sd.SESSION_ID_ENV] = "from-env"
        self.assertEqual(sd.run(cwd="/tmp/somewhere/else"), "20m00s")

    def test_argument_overrides_env_var(self):
        self._write_transcript("from-env.jsonl", ["2026-01-01T00:00:00Z", "2026-01-01T00:20:00Z"])
        self._write_transcript("from-argv.jsonl", ["2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z"])
        os.environ[sd.SESSION_ID_ENV] = "from-env"
        self.assertEqual(sd.run(session_id="from-argv", cwd=self.cwd), "5m00s")

    def test_error_names_the_id_source(self):
        _, from_argv, _ = sd.compute(session_id="nope", cwd=self.cwd)
        os.environ[sd.SESSION_ID_ENV] = "nope"
        _, from_env, _ = sd.compute(cwd=self.cwd)
        self.assertIn("from argument", from_argv)
        self.assertIn(f"from ${sd.SESSION_ID_ENV}", from_env)

    # --- no-id fallback: still works, but announces the guess ---

    def test_no_id_fallback_warns_on_success(self):
        self._write_transcript("guess.jsonl", ["2026-01-01T00:00:00Z", "2026-01-01T00:30:00Z"])
        duration, error, warning = sd.compute(cwd=self.cwd)
        self.assertEqual(duration, "30m00s")
        self.assertIsNone(error)
        self.assertIn("guessed newest transcript", warning)

    def test_three_failure_modes_are_distinguishable(self):
        # 1. no id, no transcript directory for this cwd
        _, no_dir, _ = sd.compute(cwd="/no/such/project")
        # 2. no id, directory exists but is empty
        _, no_files, _ = sd.compute(cwd=self.cwd)
        # 3. transcript found but nothing parseable in it
        path = os.path.join(self.pdir, "empty.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({"type": "summary"}) + "\n")
        _, no_stamps, _ = sd.compute(session_id="empty", cwd=self.cwd)

        self.assertIn("no transcript directory for cwd", no_dir)
        self.assertIn("contains no .jsonl files", no_files)
        self.assertIn("no parseable timestamps", no_stamps)
        self.assertEqual(len({no_dir, no_files, no_stamps}), 3)


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
        self.assertIn("does-not-exist", proc.stderr)

    def test_bogus_id_does_not_silently_return_a_duration(self):
        # Pre-fix regression: a nonexistent id from a directory that HAS
        # transcripts printed the newest one's duration and exited 0.
        home = tempfile.mkdtemp()
        pdir = os.path.join(home, ".claude", "projects", "-tmp")
        os.makedirs(pdir)
        with open(os.path.join(pdir, "someone-else.jsonl"), "w") as f:
            for ts in ("2026-01-01T00:00:00Z", "2026-01-01T00:42:00Z"):
                f.write(json.dumps({"type": "assistant", "timestamp": ts}) + "\n")

        env = dict(os.environ)
        env["HOME"] = home
        proc = subprocess.run(
            [sys.executable, str(TOOL), "00000000-dead-beef-0000-000000000000"],
            capture_output=True,
            text=True,
            cwd="/tmp",
            env=env,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertNotIn("42m", proc.stderr)


if __name__ == "__main__":
    unittest.main()
