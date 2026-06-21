#!/usr/bin/env python3
"""Regression-safety tests for checkpoint-guard.sh hook."""

import json
import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPT = str(
    Path(__file__).resolve().parent.parent / "hooks" / "scripts" / "checkpoint-guard.sh"
)


class TestCheckpointGuard(unittest.TestCase):
    """Test the PreToolUse checkpoint-guard hook via subprocess."""

    def setUp(self):
        self.session_id = f"test-{uuid.uuid4().hex[:8]}"
        self.cards_flag = f"/tmp/claude-cards-verified-{self.session_id}"

    def tearDown(self):
        for f in [self.cards_flag]:
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
    # 1. Non-Agent call -- exits 0, no output
    # ------------------------------------------------------------------
    def test_non_agent_call_exits_zero(self):
        inp = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "session_id": self.session_id,
        }
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    # ------------------------------------------------------------------
    # 2. Checkpoint without new cards -- exits 0, no warning
    # ------------------------------------------------------------------
    def test_checkpoint_without_cards_no_warning(self):
        inp = self._agent_input("artifact-clerk", "Please checkpoint the session")
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("CHECKPOINT GUARD", result.stdout)

    # ------------------------------------------------------------------
    # 3. Checkpoint with cards, cards verified -- exits 0, no warning
    # ------------------------------------------------------------------
    def test_checkpoint_with_cards_verified_no_warning(self):
        # Create the verification flag
        Path(self.cards_flag).write_text("1")

        inp = self._agent_input(
            "artifact-clerk",
            "Checkpoint session with new card updates",
        )
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("CHECKPOINT GUARD", result.stdout)

    # ------------------------------------------------------------------
    # 4. Checkpoint with cards, NOT verified -- exits 0, prints warning
    # ------------------------------------------------------------------
    def test_checkpoint_with_cards_not_verified_warns(self):
        # No flag file exists
        inp = self._agent_input(
            "artifact-clerk",
            "Checkpoint session including new card additions",
        )
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertIn("CHECKPOINT GUARD", result.stdout)
        self.assertIn("verify-cards", result.stdout)

    # ------------------------------------------------------------------
    # 5. Flag file is cleared after a check
    # ------------------------------------------------------------------
    def test_clears_verification_flag_after_check(self):
        Path(self.cards_flag).write_text("1")
        self.assertTrue(os.path.exists(self.cards_flag))

        inp = self._agent_input(
            "artifact-clerk",
            "Checkpoint this session with updated card content",
        )
        self._run(inp)

        self.assertFalse(
            os.path.exists(self.cards_flag),
            "Verification flag should be removed after checkpoint guard runs",
        )

    # ------------------------------------------------------------------
    # Non-artifact-clerk Agent call -- exits 0, no output
    # ------------------------------------------------------------------
    def test_non_artifact_clerk_agent_exits_zero(self):
        inp = self._agent_input("verification-gate", "Verify these claims")
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    # ------------------------------------------------------------------
    # Artifact-clerk but no "checkpoint" in prompt -- exits 0
    # ------------------------------------------------------------------
    def test_artifact_clerk_non_checkpoint_exits_zero(self):
        inp = self._agent_input("artifact-clerk", "Read the knowledge map")
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("CHECKPOINT GUARD", result.stdout)


if __name__ == "__main__":
    unittest.main()
