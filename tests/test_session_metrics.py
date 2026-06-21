#!/usr/bin/env python3
"""Regression-safety tests for tools/session_metrics.py CLI contract.

Tests invoke the tool via subprocess — no internal imports.
Fixture files live in /tmp with unique suffixes to avoid collisions.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid

TOOL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tools",
    "session_metrics.py",
)


class TestSessionMetricsBasicRun(unittest.TestCase):
    """Test basic CLI invocation with a valid metrics file."""

    def setUp(self):
        self.session_suffix = uuid.uuid4().hex[:8]
        self.session_id = f"test-{self.session_suffix}"
        self.metrics_file = f"/tmp/claude-session-metrics-{self.session_id}.json"
        self.metrics_data = {
            "input_tokens": 5000,
            "output_tokens": 2000,
            "context_window_size": 200000,
            "used_percentage": 45,
            "duration_ms": 125000,
        }
        with open(self.metrics_file, "w") as f:
            json.dump(self.metrics_data, f)

    def tearDown(self):
        if os.path.exists(self.metrics_file):
            os.remove(self.metrics_file)

    def test_exits_zero_on_valid_input(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_prints_session_token_summary_header(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        self.assertIn("Session Token Summary", result.stdout)

    def test_prints_main_session_label(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        self.assertIn("Main session:", result.stdout)

    def test_prints_duration(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        # 125000ms = 2m05s
        self.assertIn("2m05s", result.stdout)

    def test_prints_context_window_info(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        self.assertIn("200.0K", result.stdout)
        self.assertIn("45%", result.stdout)

    def test_prints_conversation_tokens(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        self.assertIn("5000", result.stdout)
        self.assertIn("2000", result.stdout)

    def test_prints_grand_total(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        # main_ctx = 200000 * 45 // 100 = 90000, no subagents => grand_total = 90000
        self.assertIn("Grand total:", result.stdout)
        self.assertIn("90000", result.stdout)


class TestSessionMetricsWithTopicSlug(unittest.TestCase):
    """Test that topic_slug causes a metrics file to be written."""

    def setUp(self):
        self.session_suffix = uuid.uuid4().hex[:8]
        self.session_id = f"test-{self.session_suffix}"
        self.topic_slug = f"test-topic-{self.session_suffix}"
        self.metrics_file = f"/tmp/claude-session-metrics-{self.session_id}.json"
        self.output_file = f"/tmp/session-metrics-{self.topic_slug}.txt"
        self.metrics_data = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "context_window_size": 100000,
            "used_percentage": 20,
            "duration_ms": 60000,
        }
        with open(self.metrics_file, "w") as f:
            json.dump(self.metrics_data, f)

    def tearDown(self):
        for path in [self.metrics_file, self.output_file]:
            if os.path.exists(path):
                os.remove(path)

    def test_exits_zero(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id, self.topic_slug],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_creates_metrics_output_file(self):
        subprocess.run(
            ["python3", TOOL_PATH, self.session_id, self.topic_slug],
            capture_output=True,
            text=True,
        )
        self.assertTrue(
            os.path.exists(self.output_file),
            f"Expected output file {self.output_file} to exist",
        )

    def test_output_file_contains_duration(self):
        subprocess.run(
            ["python3", TOOL_PATH, self.session_id, self.topic_slug],
            capture_output=True,
            text=True,
        )
        with open(self.output_file) as f:
            content = f.read()
        # 60000ms = 1m00s
        self.assertIn("1m00s", content)

    def test_output_file_contains_context_info(self):
        subprocess.run(
            ["python3", TOOL_PATH, self.session_id, self.topic_slug],
            capture_output=True,
            text=True,
        )
        with open(self.output_file) as f:
            content = f.read()
        self.assertIn("20%", content)
        self.assertIn("100.0K", content)

    def test_output_file_contains_grand_total(self):
        subprocess.run(
            ["python3", TOOL_PATH, self.session_id, self.topic_slug],
            capture_output=True,
            text=True,
        )
        with open(self.output_file) as f:
            content = f.read()
        # main_ctx = 100000 * 20 // 100 = 20000
        self.assertIn("Grand total: 20000", content)

    def test_stdout_mentions_metrics_file_written(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id, self.topic_slug],
            capture_output=True,
            text=True,
        )
        self.assertIn("Metrics file written", result.stdout)
        self.assertIn(self.output_file, result.stdout)


class TestSessionMetricsWithSubagentLogs(unittest.TestCase):
    """Test subagent log aggregation via cwd-based discovery."""

    def setUp(self):
        self.session_suffix = uuid.uuid4().hex[:8]
        self.session_id = f"test-{self.session_suffix}"
        self.metrics_file = f"/tmp/claude-session-metrics-{self.session_id}.json"
        self.metrics_data = {
            "input_tokens": 3000,
            "output_tokens": 1500,
            "context_window_size": 200000,
            "used_percentage": 50,
            "duration_ms": 90000,
        }
        with open(self.metrics_file, "w") as f:
            json.dump(self.metrics_data, f)

        # Create a temp directory with learning/logs/subagent-tokens.jsonl
        self.tmpdir = tempfile.mkdtemp()
        self.log_dir = os.path.join(self.tmpdir, "learning", "logs")
        os.makedirs(self.log_dir)
        self.log_file = os.path.join(self.log_dir, "subagent-tokens.jsonl")

        self.subagent_entries = [
            {
                "agent_type": "quiz-master",
                "session_id": self.session_id,
                "input_tokens": 800,
                "output_tokens": 400,
                "cache_creation_tokens": 100,
                "cache_read_tokens": 50,
                "timestamp": "2026-06-21T10:00:00Z",
            },
        ]
        with open(self.log_file, "w") as f:
            for entry in self.subagent_entries:
                f.write(json.dumps(entry) + "\n")

    def tearDown(self):
        if os.path.exists(self.metrics_file):
            os.remove(self.metrics_file)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_aggregates_subagent_tokens(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
            cwd=self.tmpdir,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Subagents:", result.stdout)
        self.assertIn("quiz-master", result.stdout)

    def test_shows_subagent_fresh_total(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
            cwd=self.tmpdir,
        )
        # fresh = input(800) + output(400) + cache_creation(100) = 1300
        self.assertIn("Subagent total:", result.stdout)
        self.assertIn("1300", result.stdout)

    def test_grand_total_includes_subagents(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
            cwd=self.tmpdir,
        )
        # main_ctx = 200000 * 50 // 100 = 100000; sub_total = 1300; grand = 101300
        self.assertIn("Grand total:", result.stdout)
        self.assertIn("101300", result.stdout)

    def test_shows_invocation_detail(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
            cwd=self.tmpdir,
        )
        self.assertIn("2026-06-21T10:00:00Z", result.stdout)


class TestSessionMetricsMissingFile(unittest.TestCase):
    """Test behavior when no metrics file exists."""

    FALLBACK = "/tmp/claude-session-metrics.json"

    def setUp(self):
        self.session_suffix = uuid.uuid4().hex[:8]
        self.session_id = f"missing-{self.session_suffix}"
        # Ensure no files exist for this session
        candidate = f"/tmp/claude-session-metrics-{self.session_id}.json"
        if os.path.exists(candidate):
            os.remove(candidate)
        # Temporarily move the fallback file if it exists so it doesn't interfere
        self._fallback_backup = None
        if os.path.exists(self.FALLBACK):
            self._fallback_backup = self.FALLBACK + f".bak-{self.session_suffix}"
            os.rename(self.FALLBACK, self._fallback_backup)

    def tearDown(self):
        # Restore the fallback file if we moved it
        if self._fallback_backup and os.path.exists(self._fallback_backup):
            os.rename(self._fallback_backup, self.FALLBACK)

    def test_exits_nonzero(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_prints_error_to_stderr(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        self.assertIn("No session metrics found", result.stderr)


class TestSessionMetricsZeroTokens(unittest.TestCase):
    """Test graceful handling of a metrics file with zero tokens."""

    def setUp(self):
        self.session_suffix = uuid.uuid4().hex[:8]
        self.session_id = f"zero-{self.session_suffix}"
        self.metrics_file = f"/tmp/claude-session-metrics-{self.session_id}.json"
        self.metrics_data = {
            "input_tokens": 0,
            "output_tokens": 0,
            "context_window_size": 0,
            "used_percentage": 0,
            "duration_ms": 0,
        }
        with open(self.metrics_file, "w") as f:
            json.dump(self.metrics_data, f)

    def tearDown(self):
        if os.path.exists(self.metrics_file):
            os.remove(self.metrics_file)

    def test_exits_zero(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_prints_summary_with_zeros(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        self.assertIn("Session Token Summary", result.stdout)
        self.assertIn("Grand total:", result.stdout)
        # Grand total should be 0 (ctx_size=0, no subagents)
        self.assertIn("Grand total:       0", result.stdout)

    def test_zero_duration_not_shown(self):
        """Duration line should not appear when duration_ms is 0."""
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
        )
        self.assertNotIn("Duration:", result.stdout)


class TestSessionMetricsMultipleSubagentTypes(unittest.TestCase):
    """Test grouping of multiple subagent types."""

    def setUp(self):
        self.session_suffix = uuid.uuid4().hex[:8]
        self.session_id = f"multi-{self.session_suffix}"
        self.metrics_file = f"/tmp/claude-session-metrics-{self.session_id}.json"
        self.metrics_data = {
            "input_tokens": 2000,
            "output_tokens": 1000,
            "context_window_size": 200000,
            "used_percentage": 30,
            "duration_ms": 60000,
        }
        with open(self.metrics_file, "w") as f:
            json.dump(self.metrics_data, f)

        self.tmpdir = tempfile.mkdtemp()
        self.log_dir = os.path.join(self.tmpdir, "learning", "logs")
        os.makedirs(self.log_dir)
        self.log_file = os.path.join(self.log_dir, "subagent-tokens.jsonl")

        entries = [
            {
                "agent_type": "quiz-master",
                "session_id": self.session_id,
                "input_tokens": 500,
                "output_tokens": 200,
                "cache_creation_tokens": 50,
                "cache_read_tokens": 10,
                "timestamp": "2026-06-21T10:00:00Z",
            },
            {
                "agent_type": "quiz-master",
                "session_id": self.session_id,
                "input_tokens": 600,
                "output_tokens": 300,
                "cache_creation_tokens": 60,
                "cache_read_tokens": 20,
                "timestamp": "2026-06-21T10:05:00Z",
            },
            {
                "agent_type": "artifact-clerk",
                "session_id": self.session_id,
                "input_tokens": 1000,
                "output_tokens": 500,
                "cache_creation_tokens": 200,
                "cache_read_tokens": 100,
                "timestamp": "2026-06-21T10:10:00Z",
            },
            {
                "agent_type": "other-agent",
                "session_id": "different-session",
                "input_tokens": 9999,
                "output_tokens": 9999,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
                "timestamp": "2026-06-21T10:15:00Z",
            },
        ]
        with open(self.log_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    def tearDown(self):
        if os.path.exists(self.metrics_file):
            os.remove(self.metrics_file)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_shows_both_agent_types(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
            cwd=self.tmpdir,
        )
        self.assertIn("quiz-master", result.stdout)
        self.assertIn("artifact-clerk", result.stdout)

    def test_groups_quiz_master_calls(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
            cwd=self.tmpdir,
        )
        # quiz-master should show x2 calls
        self.assertIn("x2", result.stdout)

    def test_excludes_other_session_entries(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
            cwd=self.tmpdir,
        )
        # other-agent belongs to a different session_id
        self.assertNotIn("other-agent", result.stdout)
        self.assertNotIn("9999", result.stdout)

    def test_subagent_total_sums_correctly(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
            cwd=self.tmpdir,
        )
        # quiz-master: fresh = (500+200+50) + (600+300+60) = 750 + 960 = 1710
        # artifact-clerk: fresh = 1000+500+200 = 1700
        # total = 1710 + 1700 = 3410
        self.assertIn("3410", result.stdout)

    def test_sorted_by_fresh_descending(self):
        result = subprocess.run(
            ["python3", TOOL_PATH, self.session_id],
            capture_output=True,
            text=True,
            cwd=self.tmpdir,
        )
        # quiz-master has 1710 fresh, artifact-clerk has 1700 fresh
        # quiz-master should appear first
        qm_pos = result.stdout.index("quiz-master")
        ac_pos = result.stdout.index("artifact-clerk")
        self.assertLess(qm_pos, ac_pos, "quiz-master should appear before artifact-clerk (sorted by fresh desc)")


if __name__ == "__main__":
    unittest.main()
