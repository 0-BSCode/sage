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

    def setUp(self):
        self.session_id = f"test-{uuid.uuid4().hex[:8]}"
        self.tmpdir = tempfile.mkdtemp()
        self.transcript_path = os.path.join(self.tmpdir, "transcript.jsonl")
        # Fallback log dir under a controlled HOME
        self.fake_home = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        shutil.rmtree(self.fake_home, ignore_errors=True)

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
    def test_writes_to_project_learning_logs(self):
        project_dir = os.path.join(self.tmpdir, "project")
        learning_dir = os.path.join(project_dir, "learning")
        os.makedirs(learning_dir)

        self._write_transcript(self._sample_transcript())

        inp = self._base_input()
        self._run(inp, env_extra={"CLAUDE_PROJECT_DIR": project_dir})

        log_file = os.path.join(learning_dir, "logs", "subagent-tokens.jsonl")
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
        self._write_transcript(self._sample_transcript())

        inp = self._base_input()
        # No CLAUDE_PROJECT_DIR set
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
        project_dir = os.path.join(self.tmpdir, "project")
        learning_dir = os.path.join(project_dir, "learning")
        os.makedirs(learning_dir)

        self._write_transcript(self._sample_transcript())

        inp = self._base_input()
        env = {"CLAUDE_PROJECT_DIR": project_dir}

        self._run(inp, env_extra=env)
        self._run(inp, env_extra=env)

        log_file = os.path.join(learning_dir, "logs", "subagent-tokens.jsonl")
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

        project_dir = os.path.join(self.tmpdir, "project")
        learning_dir = os.path.join(project_dir, "learning")
        os.makedirs(learning_dir)

        inp = self._base_input()
        result = self._run(inp, env_extra={"CLAUDE_PROJECT_DIR": project_dir})

        # Should still exit 0 (jq handles empty selections)
        self.assertEqual(result.returncode, 0)

    # ------------------------------------------------------------------
    # 7. CLAUDE_PROJECT_DIR set but no learning/ subdir -- uses fallback
    # ------------------------------------------------------------------
    def test_project_dir_without_learning_uses_fallback(self):
        project_dir = os.path.join(self.tmpdir, "project-no-learning")
        os.makedirs(project_dir)
        # No learning/ subdir

        self._write_transcript(self._sample_transcript())

        inp = self._base_input()
        self._run(inp, env_extra={"CLAUDE_PROJECT_DIR": project_dir})

        fallback_log = os.path.join(
            self.fake_home, ".claude", "logs", "subagent-tokens.jsonl"
        )
        self.assertTrue(os.path.exists(fallback_log))


if __name__ == "__main__":
    unittest.main()
