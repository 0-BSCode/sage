#!/usr/bin/env python3
"""Regression-safety tests for tools/config.py."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOL_PATH = str(Path(__file__).resolve().parent.parent / "tools" / "config.py")


class TestConfigCLIWithEnvVar(unittest.TestCase):
    """SAGE_LEARNING_ROOT env var takes highest precedence."""

    def test_env_var_printed(self):
        env = os.environ.copy()
        env["SAGE_LEARNING_ROOT"] = "/tmp/my-learning-root"
        result = subprocess.run(
            ["python3", TOOL_PATH],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "/tmp/my-learning-root")

    def test_env_var_overrides_config_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".config" / "sage"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "config.json"
            config_file.write_text(json.dumps({
                "learning_root": "/from/config",
                "version": 1,
            }))

            env = os.environ.copy()
            env["SAGE_LEARNING_ROOT"] = "/from/env"
            env["HOME"] = tmpdir
            result = subprocess.run(
                ["python3", TOOL_PATH],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "/from/env")


class TestConfigCLIWithConfigFile(unittest.TestCase):
    """Config file is read when env var is not set."""

    def test_config_file_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".config" / "sage"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "config.json"
            config_file.write_text(json.dumps({
                "learning_root": "/home/user/sage",
                "version": 1,
            }))

            env = os.environ.copy()
            env.pop("SAGE_LEARNING_ROOT", None)
            env["HOME"] = tmpdir
            result = subprocess.run(
                ["python3", TOOL_PATH],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "/home/user/sage")


class TestConfigCLIMissing(unittest.TestCase):
    """No env var and no config file — exits non-zero."""

    def test_no_config_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env.pop("SAGE_LEARNING_ROOT", None)
            env["HOME"] = tmpdir
            result = subprocess.run(
                ["python3", TOOL_PATH],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout.strip(), "")


class TestConfigCLIMalformedFile(unittest.TestCase):
    """Malformed config file is handled gracefully."""

    def test_invalid_json_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".config" / "sage"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text("not json{{{")

            env = os.environ.copy()
            env.pop("SAGE_LEARNING_ROOT", None)
            env["HOME"] = tmpdir
            result = subprocess.run(
                ["python3", TOOL_PATH],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 1)

    def test_missing_learning_root_key_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".config" / "sage"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(json.dumps({"version": 1}))

            env = os.environ.copy()
            env.pop("SAGE_LEARNING_ROOT", None)
            env["HOME"] = tmpdir
            result = subprocess.run(
                ["python3", TOOL_PATH],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 1)


class TestSaveConfig(unittest.TestCase):
    """save_config writes a valid config file."""

    def test_save_creates_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["HOME"] = tmpdir
            result = subprocess.run(
                ["python3", "-c", f"""
import sys; sys.path.insert(0, '{Path(TOOL_PATH).parent}')
from config import save_config
save_config('/my/learning/root')
"""],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 0)

            config_file = Path(tmpdir) / ".config" / "sage" / "config.json"
            self.assertTrue(config_file.exists())
            data = json.loads(config_file.read_text())
            self.assertEqual(data["learning_root"], "/my/learning/root")
            self.assertEqual(data["version"], 1)

    def test_save_preserves_existing_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".config" / "sage"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(json.dumps({
                "learning_root": "/old/path",
                "version": 1,
                "custom_field": "preserved",
            }))

            env = os.environ.copy()
            env["HOME"] = tmpdir
            result = subprocess.run(
                ["python3", "-c", f"""
import sys; sys.path.insert(0, '{Path(TOOL_PATH).parent}')
from config import save_config
save_config('/new/path')
"""],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 0)

            data = json.loads((config_dir / "config.json").read_text())
            self.assertEqual(data["learning_root"], "/new/path")
            self.assertEqual(data["custom_field"], "preserved")


if __name__ == "__main__":
    unittest.main()
