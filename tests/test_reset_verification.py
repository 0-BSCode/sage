#!/usr/bin/env python3
"""Regression-safety tests for reset-verification.sh hook."""

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
    / "reset-verification.sh"
)


class TestResetVerification(unittest.TestCase):
    """Test the PostToolUse reset-verification hook via subprocess."""

    def setUp(self):
        self.session_id = f"test-{uuid.uuid4().hex[:8]}"
        self.counter_file = f"/tmp/claude-verif-counter-{self.session_id}"
        self.warned_file = f"/tmp/claude-verif-warned-{self.session_id}"
        self.cards_flag = f"/tmp/claude-cards-verified-{self.session_id}"

    def tearDown(self):
        for f in [self.counter_file, self.warned_file, self.cards_flag]:
            try:
                os.unlink(f)
            except FileNotFoundError:
                pass

    def _run(self, input_json: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", SCRIPT],
            input=json.dumps(input_json),
            capture_output=True,
            text=True,
            timeout=10,
        )

    def _agent_input(self, subagent_type: str, prompt: str) -> dict:
        return {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": subagent_type,
                "prompt": prompt,
            },
            "session_id": self.session_id,
        }

    # ------------------------------------------------------------------
    # 1. Verification-gate resets counter file to 0
    # ------------------------------------------------------------------
    def test_verification_gate_resets_counter(self):
        # Pre-populate with a non-zero counter
        Path(self.counter_file).write_text("3")

        inp = self._agent_input("verification-gate", "Verify these claims")
        self._run(inp)

        self.assertTrue(os.path.exists(self.counter_file))
        self.assertEqual(Path(self.counter_file).read_text().strip(), "0")

    # ------------------------------------------------------------------
    # 2. Creates counter file if it doesn't exist (verification-gate)
    # ------------------------------------------------------------------
    def test_verification_gate_creates_counter(self):
        self.assertFalse(os.path.exists(self.counter_file))

        inp = self._agent_input("verification-gate", "Verify claims")
        self._run(inp)

        self.assertTrue(os.path.exists(self.counter_file))
        self.assertEqual(Path(self.counter_file).read_text().strip(), "0")

    # ------------------------------------------------------------------
    # 3. Sets cards-verified flag when prompt contains "verify-cards"
    # ------------------------------------------------------------------
    def test_sets_cards_verified_flag(self):
        inp = self._agent_input(
            "verification-gate", "Please verify-cards for this session"
        )
        self._run(inp)

        self.assertTrue(os.path.exists(self.cards_flag))
        self.assertEqual(Path(self.cards_flag).read_text().strip(), "1")

    # ------------------------------------------------------------------
    # 4. Does NOT set cards-verified flag for other prompts
    # ------------------------------------------------------------------
    def test_no_cards_flag_for_other_prompts(self):
        inp = self._agent_input("verification-gate", "Verify these factual claims")
        self._run(inp)

        self.assertFalse(os.path.exists(self.cards_flag))

    # ------------------------------------------------------------------
    # 5. Clears warned flag file
    # ------------------------------------------------------------------
    def test_clears_warned_flag(self):
        Path(self.warned_file).write_text("1")
        self.assertTrue(os.path.exists(self.warned_file))

        inp = self._agent_input("verification-gate", "Verify claims")
        self._run(inp)

        self.assertFalse(os.path.exists(self.warned_file))

    # ------------------------------------------------------------------
    # 6. Non-Agent tool call is a no-op
    # ------------------------------------------------------------------
    def test_non_agent_tool_is_noop(self):
        inp = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "session_id": self.session_id,
        }
        self._run(inp)

        self.assertFalse(os.path.exists(self.counter_file))
        self.assertFalse(os.path.exists(self.cards_flag))

    # ------------------------------------------------------------------
    # 7. Artifact-clerk checkpoint resets existing counter
    # ------------------------------------------------------------------
    def test_artifact_clerk_checkpoint_resets_counter(self):
        Path(self.counter_file).write_text("4")
        Path(self.warned_file).write_text("1")

        inp = self._agent_input("artifact-clerk", "Checkpoint the session now")
        self._run(inp)

        self.assertEqual(Path(self.counter_file).read_text().strip(), "0")
        self.assertFalse(os.path.exists(self.warned_file))

    # ------------------------------------------------------------------
    # 8. Artifact-clerk checkpoint without existing counter -- no crash
    # ------------------------------------------------------------------
    def test_artifact_clerk_checkpoint_no_counter_file(self):
        self.assertFalse(os.path.exists(self.counter_file))

        inp = self._agent_input("artifact-clerk", "Checkpoint the session")
        result = self._run(inp)

        self.assertEqual(result.returncode, 0)
        # Counter file should NOT be created (script only writes if it exists)
        self.assertFalse(os.path.exists(self.counter_file))

    # ------------------------------------------------------------------
    # 9. Non-verification-gate, non-artifact-clerk agent -- no-op
    # ------------------------------------------------------------------
    def test_other_agent_type_is_noop(self):
        inp = self._agent_input("artifact-clerk", "Read the journal file")
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(self.counter_file))


if __name__ == "__main__":
    unittest.main()
