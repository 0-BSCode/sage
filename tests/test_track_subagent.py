#!/usr/bin/env python3
"""Regression-safety tests for track-subagent.sh hook."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPT = str(
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "scripts"
    / "track-subagent.sh"
)


class TestTrackSubagent(unittest.TestCase):
    """Test the SubagentStop track-subagent hook via subprocess."""

    LEARNING_ROOT_FILE = "/tmp/.sage-learning-root"

    def setUp(self):
        self.session_id = f"test-{uuid.uuid4().hex[:8]}"
        self.tmpdir = tempfile.mkdtemp()
        self.transcript_path = os.path.join(self.tmpdir, "transcript.jsonl")
        # Fallback log dir under a controlled HOME
        self.fake_home = tempfile.mkdtemp()
        # Save and clear real learning root file to isolate tests
        self._saved_learning_root = None
        if os.path.exists(self.LEARNING_ROOT_FILE):
            with open(self.LEARNING_ROOT_FILE) as f:
                self._saved_learning_root = f.read()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.fake_home, ignore_errors=True)
        # Restore learning root file
        if self._saved_learning_root is not None:
            with open(self.LEARNING_ROOT_FILE, "w") as f:
                f.write(self._saved_learning_root)
        elif os.path.exists(self.LEARNING_ROOT_FILE):
            os.remove(self.LEARNING_ROOT_FILE)

    def _set_learning_root(self, path: str):
        with open(self.LEARNING_ROOT_FILE, "w") as f:
            f.write(path)

    def _clear_learning_root(self):
        if os.path.exists(self.LEARNING_ROOT_FILE):
            os.remove(self.LEARNING_ROOT_FILE)

    def _write_transcript(self, entries: list[dict]):
        """Write JSONL transcript file."""
        with open(self.transcript_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    def _sample_transcript(self) -> list[dict]:
        """A minimal transcript with token usage."""
        return [
            {
                "type": "human",
                "message": {"content": "Hello"},
            },
            {
                "type": "assistant",
                "message": {
                    "content": "Hi there",
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_creation_input_tokens": 10,
                        "cache_read_input_tokens": 5,
                    },
                },
            },
            {
                "type": "assistant",
                "message": {
                    "content": "Done",
                    "usage": {
                        "input_tokens": 200,
                        "output_tokens": 80,
                        "cache_creation_input_tokens": 20,
                        "cache_read_input_tokens": 15,
                    },
                },
            },
        ]

    def _run(
        self, input_json: dict, env_extra: dict | None = None
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["HOME"] = self.fake_home
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            ["bash", SCRIPT],
            input=json.dumps(input_json),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )

    def _base_input(
        self,
        agent_type: str = "verification-gate",
        transcript: str | None = None,
    ) -> dict:
        return {
            "agent_type": agent_type,
            "agent_id": f"agent-{self.session_id}",
            "agent_transcript_path": transcript or self.transcript_path,
            "session_id": self.session_id,
        }

    # ------------------------------------------------------------------
    # 1. Writes token data to learning/logs/ when it exists
    # ------------------------------------------------------------------
    def test_writes_to_learning_root_logs(self):
        learning_root = os.path.join(self.tmpdir, "learning-root")
        os.makedirs(learning_root)
        self._set_learning_root(learning_root)

        self._write_transcript(self._sample_transcript())

        inp = self._base_input()
        self._run(inp)

        log_file = os.path.join(learning_root, "logs", "subagent-tokens.jsonl")
        self.assertTrue(os.path.exists(log_file), "Log file should be created")

        with open(log_file) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)

        data = json.loads(lines[0])
        self.assertEqual(data["input_tokens"], 300)
        self.assertEqual(data["output_tokens"], 130)
        self.assertEqual(data["cache_creation_tokens"], 30)
        self.assertEqual(data["cache_read_tokens"], 20)
        self.assertEqual(data["agent_type"], "verification-gate")
        self.assertEqual(data["session_id"], self.session_id)
        self.assertIn("timestamp", data)

    # ------------------------------------------------------------------
    # 2. Falls back to global logs when no learning directory
    # ------------------------------------------------------------------
    def test_falls_back_to_global_logs(self):
        self._clear_learning_root()
        self._write_transcript(self._sample_transcript())

        inp = self._base_input()
        self._run(inp)

        log_file = os.path.join(self.fake_home, ".claude", "logs", "subagent-tokens.jsonl")
        self.assertTrue(os.path.exists(log_file), "Fallback log should be created")

        with open(log_file) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertEqual(data["input_tokens"], 300)

    # ------------------------------------------------------------------
    # 3. Handles missing transcript gracefully (exits 0)
    # ------------------------------------------------------------------
    def test_missing_transcript_exits_zero(self):
        inp = self._base_input(transcript="/tmp/nonexistent-transcript-file.jsonl")
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)

    # ------------------------------------------------------------------
    # 4. Handles empty transcript path gracefully (exits 0)
    # ------------------------------------------------------------------
    def test_empty_transcript_path_exits_zero(self):
        inp = self._base_input(transcript="")
        result = self._run(inp)
        self.assertEqual(result.returncode, 0)

    # ------------------------------------------------------------------
    # 5. Appends (not overwrites) on repeated calls
    # ------------------------------------------------------------------
    def test_appends_on_repeated_calls(self):
        learning_root = os.path.join(self.tmpdir, "learning-root")
        os.makedirs(learning_root)
        self._set_learning_root(learning_root)

        self._write_transcript(self._sample_transcript())

        inp = self._base_input()

        self._run(inp)
        self._run(inp)

        log_file = os.path.join(learning_root, "logs", "subagent-tokens.jsonl")
        with open(log_file) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)

    # ------------------------------------------------------------------
    # 6. Handles transcript with no assistant messages
    # ------------------------------------------------------------------
    def test_transcript_no_assistant_messages(self):
        self._write_transcript([
            {"type": "human", "message": {"content": "Hello"}},
        ])

        learning_root = os.path.join(self.tmpdir, "learning-root")
        os.makedirs(learning_root)
        self._set_learning_root(learning_root)

        inp = self._base_input()
        result = self._run(inp)

        self.assertEqual(result.returncode, 0)

    # ------------------------------------------------------------------
    # 7. CLAUDE_PROJECT_DIR set but no learning/ subdir -- uses fallback
    # ------------------------------------------------------------------
    def test_no_learning_root_uses_fallback(self):
        self._clear_learning_root()

        self._write_transcript(self._sample_transcript())

        inp = self._base_input()
        self._run(inp)

        fallback_log = os.path.join(
            self.fake_home, ".claude", "logs", "subagent-tokens.jsonl"
        )
        self.assertTrue(os.path.exists(fallback_log))


if __name__ == "__main__":
    unittest.main()
