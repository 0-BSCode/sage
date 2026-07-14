#!/usr/bin/env python3
"""Regression-safety tests for demo_index_writer.py.

Tests the CLI contract via subprocess — no internal imports.
Verifies append (create, dedup, sort), validate,
and error handling (invalid JSON, missing fields, bad WS format).
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOL_PATH = str(
    Path(__file__).resolve().parent.parent / "tools" / "demo" / "demo_index_writer.py"
)


def _make_entry(ws_id="WS-1", ws_desc="test weak spot", title="Test Demo",
                filename="test-demo.html", ref="ref-test.md",
                created="2026-01-01", **overrides):
    """Build a demo entry dict with sensible defaults."""
    entry = {
        "weak_spot_id": ws_id,
        "weak_spot_description": ws_desc,
        "demo_title": title,
        "demo_filename": filename,
        "related_reference": ref,
        "created_date": created,
    }
    entry.update(overrides)
    return entry


def _run_append(demos_dir, entry_dict, use_stdin=False):
    """Run demo_index_writer.py append via subprocess."""
    json_str = json.dumps(entry_dict)
    cmd = ["python3", TOOL_PATH, "append", str(demos_dir)]

    if use_stdin:
        cmd.append("--stdin")
        result = subprocess.run(cmd, capture_output=True, text=True, input=json_str)
    else:
        cmd.extend(["--json", json_str])
        result = subprocess.run(cmd, capture_output=True, text=True)

    return result


def _run_validate(demos_dir):
    """Run demo_index_writer.py validate via subprocess."""
    cmd = ["python3", TOOL_PATH, "validate", str(demos_dir)]
    return subprocess.run(cmd, capture_output=True, text=True)


class TestAppendCreatesNewIndex(unittest.TestCase):
    """append — creates new index.html from scratch."""

    def test_creates_index_when_none_exists(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            demos = Path(demos_dir)
            # Create the demo file so the tool doesn't warn
            (demos / "test-demo.html").write_text("<html></html>")

            entry = _make_entry()
            result = _run_append(demos_dir, entry)

            self.assertEqual(result.returncode, 0)
            self.assertIn("Appended", result.stdout)

            index_path = demos / "index.html"
            self.assertTrue(index_path.exists())

            html = index_path.read_text()
            self.assertIn("WS-1", html)
            self.assertIn("test weak spot", html)
            self.assertIn("Test Demo", html)
            self.assertIn("test-demo.html", html)

    def test_creates_index_via_stdin(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            demos = Path(demos_dir)
            (demos / "test-demo.html").write_text("<html></html>")

            entry = _make_entry()
            result = _run_append(demos_dir, entry, use_stdin=True)

            self.assertEqual(result.returncode, 0)
            self.assertTrue((demos / "index.html").exists())


class TestAppendDeduplication(unittest.TestCase):
    """append — updates existing entry when WS-number matches."""

    def test_updates_existing_ws_entry(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            demos = Path(demos_dir)
            (demos / "demo-v1.html").write_text("<html></html>")
            (demos / "demo-v2.html").write_text("<html></html>")

            # First append
            entry1 = _make_entry(
                ws_id="WS-5", title="Original Title",
                filename="demo-v1.html", created="2026-01-01"
            )
            _run_append(demos_dir, entry1)

            # Second append with same WS-5
            entry2 = _make_entry(
                ws_id="WS-5", title="Updated Title",
                filename="demo-v2.html", created="2026-01-02"
            )
            result = _run_append(demos_dir, entry2)

            self.assertEqual(result.returncode, 0)
            self.assertIn("Updated", result.stdout)
            self.assertIn("Total entries: 1", result.stdout)

            html = (demos / "index.html").read_text()
            self.assertIn("Updated Title", html)
            self.assertNotIn("Original Title", html)


class TestAppendSortsByDate(unittest.TestCase):
    """append — sorts entries by created_date."""

    def test_entries_sorted_chronologically(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            demos = Path(demos_dir)
            (demos / "demo-c.html").write_text("<html></html>")
            (demos / "demo-a.html").write_text("<html></html>")
            (demos / "demo-b.html").write_text("<html></html>")

            # Append out of order
            _run_append(demos_dir, _make_entry(
                ws_id="WS-3", title="Third", filename="demo-c.html",
                created="2026-03-01"
            ))
            _run_append(demos_dir, _make_entry(
                ws_id="WS-1", title="First", filename="demo-a.html",
                created="2026-01-01"
            ))
            _run_append(demos_dir, _make_entry(
                ws_id="WS-2", title="Second", filename="demo-b.html",
                created="2026-02-01"
            ))

            html = (demos / "index.html").read_text()
            pos_first = html.index("WS-1")
            pos_second = html.index("WS-2")
            pos_third = html.index("WS-3")

            self.assertLess(pos_first, pos_second)
            self.assertLess(pos_second, pos_third)


class TestAppendMissingReference(unittest.TestCase):
    """append — missing related_reference shows 'No reference doc yet'."""

    def test_no_reference_placeholder(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            demos = Path(demos_dir)
            (demos / "test-demo.html").write_text("<html></html>")

            entry = _make_entry(ref="")
            result = _run_append(demos_dir, entry)

            self.assertEqual(result.returncode, 0)

            html = (demos / "index.html").read_text()
            self.assertIn("No reference doc yet", html)

    def test_omitted_reference_placeholder(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            demos = Path(demos_dir)
            (demos / "test-demo.html").write_text("<html></html>")

            entry = {
                "weak_spot_id": "WS-1",
                "weak_spot_description": "test",
                "demo_title": "Test",
                "demo_filename": "test-demo.html",
                "created_date": "2026-01-01",
                # related_reference intentionally omitted
            }
            result = _run_append(demos_dir, entry)

            self.assertEqual(result.returncode, 0)
            html = (demos / "index.html").read_text()
            self.assertIn("No reference doc yet", html)


class TestValidatePassesOnValid(unittest.TestCase):
    """validate — passes on valid index."""

    def test_valid_index_passes(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            demos = Path(demos_dir)
            (demos / "test-demo.html").write_text("<html></html>")

            # Create the references directory and file so validate doesn't
            # report a missing reference
            refs_dir = demos.parent / "references"
            refs_dir.mkdir(parents=True, exist_ok=True)
            (refs_dir / "ref-test.md").write_text("# Test Reference")

            # Create a valid index via append
            _run_append(demos_dir, _make_entry())

            result = _run_validate(demos_dir)

            self.assertEqual(result.returncode, 0)
            self.assertIn("OK", result.stdout)
            self.assertIn("1 entries", result.stdout)


class TestValidateReportsMissingFiles(unittest.TestCase):
    """validate — reports missing demo files."""

    def test_missing_demo_file_reported(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            demos = Path(demos_dir)
            # Create the demo file for append, then delete it before validate
            demo_file = demos / "test-demo.html"
            demo_file.write_text("<html></html>")

            _run_append(demos_dir, _make_entry())

            # Remove the demo file
            demo_file.unlink()

            result = _run_validate(demos_dir)

            self.assertEqual(result.returncode, 1)
            self.assertIn("Missing demo file", result.stdout)
            self.assertIn("test-demo.html", result.stdout)


class TestValidateNoIndex(unittest.TestCase):
    """validate — fails when index.html does not exist."""

    def test_missing_index_exits_with_error(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            result = _run_validate(demos_dir)

            self.assertEqual(result.returncode, 1)
            self.assertIn("does not exist", result.stderr)


class TestErrorCases(unittest.TestCase):
    """Error cases: invalid JSON, missing required fields, invalid WS format."""

    def test_invalid_json_exits_with_error(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            cmd = [
                "python3", TOOL_PATH, "append", str(demos_dir),
                "--json", "{not valid json",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            self.assertEqual(result.returncode, 1)
            self.assertIn("invalid JSON", result.stderr)

    def test_missing_required_fields_exits_with_error(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            incomplete_entry = {
                "weak_spot_id": "WS-1",
                # missing other required fields
            }
            result = _run_append(demos_dir, incomplete_entry)

            self.assertEqual(result.returncode, 1)
            self.assertIn("missing required fields", result.stderr)

    def test_invalid_ws_number_format_exits_with_error(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            entry = _make_entry(ws_id="INVALID-1")
            result = _run_append(demos_dir, entry)

            self.assertEqual(result.returncode, 1)
            self.assertIn("weak_spot_id must match", result.stderr)

    def test_non_object_json_exits_with_error(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            cmd = [
                "python3", TOOL_PATH, "append", str(demos_dir),
                "--json", "[1, 2, 3]",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            self.assertEqual(result.returncode, 1)
            self.assertIn("single demo entry object", result.stderr)

    def test_no_json_or_stdin_flag_exits_with_error(self):
        with tempfile.TemporaryDirectory() as demos_dir:
            cmd = ["python3", TOOL_PATH, "append", str(demos_dir)]
            result = subprocess.run(cmd, capture_output=True, text=True)

            self.assertEqual(result.returncode, 1)
            self.assertIn("--json or --stdin", result.stderr)

    def test_missing_demo_file_warns_on_append(self):
        """Append still succeeds but warns when demo file is missing."""
        with tempfile.TemporaryDirectory() as demos_dir:
            # Do NOT create the demo file
            entry = _make_entry(filename="nonexistent.html")
            result = _run_append(demos_dir, entry)

            self.assertEqual(result.returncode, 0)
            self.assertIn("Warning: demo file not found", result.stderr)
            self.assertIn("Appended", result.stdout)


if __name__ == "__main__":
    unittest.main()
