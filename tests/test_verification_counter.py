#!/usr/bin/env python3
"""Regression-safety tests for verification-counter.sh hook."""

import json
import os
import subprocess
import unittest
import uuid
from pathlib import Path

SCRIPT = str(
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "scripts"
    / "verification-counter.sh"
)


class TestVerificationCounter(unittest.TestCase):
    """Test the Stop verification-counter hook via subprocess."""

    def setUp(self):
        self.session_id = f"test-{uuid.uuid4().hex[:8]}"
        self.counter_file = f"/tmp/claude-verif-counter-{self.session_id}"
        self.warned_file = f"/tmp/claude-verif-warned-{self.session_id}"

    def tearDown(self):
        for f in [self.counter_file, self.warned_file]:
            try:
                os.unlink(f)
            except FileNotFoundError:
                pass

    def _run(
        self, input_json: dict
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", SCRIPT],
            input=json.dumps(input_json),
            capture_output=True,
            text=True,
            timeout=10,
        )

    def _base_input(self, stop_hook_active: bool = False) -> dict:
        return {
            "session_id": self.session_id,
            "stop_hook_active": stop_hook_active,
        }

    # ------------------------------------------------------------------
    # 1. No counter file -- exits 0, no output (no-op)
    # ------------------------------------------------------------------
    def test_no_counter_file_noop(self):
        self.assertFalse(os.path.exists(self.counter_file))

        inp = self._base_input()
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    # ------------------------------------------------------------------
    # 2. Counter at 0 -- increments to 1, no warning
    # ------------------------------------------------------------------
    def test_counter_zero_increments_no_warning(self):
        Path(self.counter_file).write_text("0")

        inp = self._base_input()
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(Path(self.counter_file).read_text().strip(), "1")
        self.assertNotIn("VERIFICATION OVERDUE", result.stdout)

    # ------------------------------------------------------------------
    # 3. Counter at 4 -- increments to 5, prints warning
    # ------------------------------------------------------------------
    def test_counter_four_increments_and_warns(self):
        Path(self.counter_file).write_text("4")

        inp = self._base_input()
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(Path(self.counter_file).read_text().strip(), "5")
        self.assertIn("VERIFICATION OVERDUE", result.stdout)
        self.assertIn("5 messages", result.stdout)

    # ------------------------------------------------------------------
    # 4. Counter already warned -- doesn't warn again
    # ------------------------------------------------------------------
    def test_already_warned_no_repeat(self):
        Path(self.counter_file).write_text("6")
        Path(self.warned_file).write_text("1")

        inp = self._base_input()
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(Path(self.counter_file).read_text().strip(), "7")
        self.assertNotIn("VERIFICATION OVERDUE", result.stdout)

    # ------------------------------------------------------------------
    # 5. STOP_HOOK_ACTIVE set -- exits immediately (prevents loops)
    # ------------------------------------------------------------------
    def test_stop_hook_active_exits_immediately(self):
        Path(self.counter_file).write_text("10")

        inp = self._base_input(stop_hook_active=True)
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        # Counter should NOT be incremented
        self.assertEqual(Path(self.counter_file).read_text().strip(), "10")
        self.assertEqual(result.stdout.strip(), "")

    # ------------------------------------------------------------------
    # 6. Incremental counting across multiple invocations
    # ------------------------------------------------------------------
    def test_increments_across_calls(self):
        Path(self.counter_file).write_text("0")
        inp = self._base_input()

        for expected in range(1, 4):
            self._run(inp)
            self.assertEqual(
                Path(self.counter_file).read_text().strip(), str(expected)
            )

    # ------------------------------------------------------------------
    # 7. Warning output is valid JSON with expected structure
    # ------------------------------------------------------------------
    def test_warning_output_is_valid_json(self):
        Path(self.counter_file).write_text("4")

        inp = self._base_input()
        result = self._run(inp)

        output = json.loads(result.stdout)
        self.assertTrue(output.get("continue"))
        self.assertIn("VERIFICATION OVERDUE", output.get("systemMessage", ""))

    # ------------------------------------------------------------------
    # 8. Warned file is created on first warning
    # ------------------------------------------------------------------
    def test_warned_file_created_on_warning(self):
        Path(self.counter_file).write_text("4")
        self.assertFalse(os.path.exists(self.warned_file))

        inp = self._base_input()
        self._run(inp)

        self.assertTrue(os.path.exists(self.warned_file))


if __name__ == "__main__":
    unittest.main()
