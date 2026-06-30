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


def _run_save(tmpdir, raw_path):
    """Run save_config(raw_path) in a subprocess with HOME=tmpdir. Returns CompletedProcess."""
    env = os.environ.copy()
    env["HOME"] = tmpdir
    return subprocess.run(
        ["python3", "-c", f"""
import sys; sys.path.insert(0, '{Path(TOOL_PATH).parent}')
from config import save_config
save_config({raw_path!r})
"""],
        capture_output=True, text=True, env=env,
    )


class TestSaveConfig(unittest.TestCase):
    """save_config normalizes the path, creates the tree, then persists."""

    def test_save_creates_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = os.path.join(tmpdir, "learning", "root")
            result = _run_save(tmpdir, root)
            self.assertEqual(result.returncode, 0, result.stderr)

            config_file = Path(tmpdir) / ".config" / "sage" / "config.json"
            self.assertTrue(config_file.exists())
            data = json.loads(config_file.read_text())
            self.assertEqual(data["learning_root"], str(Path(root).resolve()))
            self.assertEqual(data["version"], 1)

    def test_save_creates_directory_and_cross_refs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = os.path.join(tmpdir, "does", "not", "exist", "yet")
            result = _run_save(tmpdir, root)
            self.assertEqual(result.returncode, 0, result.stderr)

            self.assertTrue(Path(root).is_dir())
            self.assertTrue((Path(root) / "cross-refs").is_dir())

    def test_save_expands_tilde_to_absolute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run_save(tmpdir, "~/sage-learning")
            self.assertEqual(result.returncode, 0, result.stderr)

            expected = str((Path(tmpdir) / "sage-learning").resolve())
            data = json.loads(
                (Path(tmpdir) / ".config" / "sage" / "config.json").read_text()
            )
            self.assertEqual(data["learning_root"], expected)
            self.assertNotIn("~", data["learning_root"])
            self.assertTrue((Path(expected) / "cross-refs").is_dir())

    def test_save_does_not_persist_on_mkdir_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # A regular file in the path means mkdir of a child must fail.
            blocker = Path(tmpdir) / "blocker"
            blocker.write_text("i am a file, not a directory")

            result = _run_save(tmpdir, str(blocker / "sub"))
            self.assertNotEqual(result.returncode, 0)

            config_file = Path(tmpdir) / ".config" / "sage" / "config.json"
            self.assertFalse(config_file.exists())

    def test_save_preserves_existing_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".config" / "sage"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(json.dumps({
                "learning_root": "/old/path",
                "version": 1,
                "custom_field": "preserved",
            }))

            root = os.path.join(tmpdir, "new", "path")
            result = _run_save(tmpdir, root)
            self.assertEqual(result.returncode, 0, result.stderr)

            data = json.loads((config_dir / "config.json").read_text())
            self.assertEqual(data["learning_root"], str(Path(root).resolve()))
            self.assertEqual(data["custom_field"], "preserved")


class TestNormalizeCLI(unittest.TestCase):
    """`config.py --normalize PATH` previews the resolved path without writing."""

    def test_normalize_expands_tilde(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["HOME"] = tmpdir
            result = subprocess.run(
                ["python3", TOOL_PATH, "--normalize", "~/foo"],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout.strip(), str((Path(tmpdir) / "foo").resolve())
            )

    def test_normalize_makes_relative_absolute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["HOME"] = tmpdir
            result = subprocess.run(
                ["python3", TOOL_PATH, "--normalize", "rel/sub"],
                capture_output=True, text=True, env=env, cwd=tmpdir,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                result.stdout.strip(), str((Path(tmpdir) / "rel" / "sub").resolve())
            )

    def test_normalize_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["HOME"] = tmpdir
            subprocess.run(
                ["python3", TOOL_PATH, "--normalize", "~/foo"],
                capture_output=True, text=True, env=env,
            )
            self.assertFalse((Path(tmpdir) / ".config" / "sage" / "config.json").exists())
            self.assertFalse((Path(tmpdir) / "foo").exists())

    def test_normalize_without_path_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["HOME"] = tmpdir
            result = subprocess.run(
                ["python3", TOOL_PATH, "--normalize"],
                capture_output=True, text=True, env=env,
            )
            self.assertNotEqual(result.returncode, 0)


class TestGetLearningRootExpandsTilde(unittest.TestCase):
    """Stored / env-supplied `~` paths are expanded on read."""

    def test_tilde_in_env_var_expanded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ.copy()
            env["HOME"] = tmpdir
            env["SAGE_LEARNING_ROOT"] = "~/from-env"
            result = subprocess.run(
                ["python3", TOOL_PATH],
                capture_output=True, text=True, env=env,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), str(Path(tmpdir) / "from-env"))

    def test_tilde_in_config_file_expanded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".config" / "sage"
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(json.dumps({
                "learning_root": "~/from-config",
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
            self.assertEqual(result.stdout.strip(), str(Path(tmpdir) / "from-config"))


if __name__ == "__main__":
    unittest.main()
