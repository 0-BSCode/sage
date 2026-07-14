#!/usr/bin/env python3
"""Regression-safety tests for journal_writer.py CLI contract.

Tests the CLI through subprocess invocation only — no internal imports.
Validates exit codes, stdout/stderr content, and file side-effects.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOL_PATH = str(
    Path(__file__).resolve().parent.parent / "tools" / "srs" / "journal_writer.py"
)

# Canonical 8-column header and separator
CANONICAL_HEADER = "| # | Date | Type | Focus | Reviews | Avg Grade | Summary | File |"
CANONICAL_SEPARATOR = "|---|---|---|---|---|---|---|---|"

# A well-formatted canonical file for reuse
WELL_FORMATTED_FILE = """\
# Session Index

| # | Date | Type | Focus | Reviews | Avg Grade | Summary | File |
|---|---|---|---|---|---|---|---|
| 1 | 2026-06-01 | learn | React Hooks | 5 | 4.20 | First session | session-01.md |
| 2 | 2026-06-02 | review | Closures | 3 | 3.67 | Review session | session-02.md |
"""

# A 5-column file missing Reviews, Avg Grade, Summary — validate must reject it
FEWER_COLUMNS_FILE = """\
# Session Index

| # | Date | Type | Focus | File |
|---|---|---|---|---|
| 1 | 2026-06-01 | learn | React Hooks | session-01.md |
| 2 | 2026-06-02 | review | Closures | session-02.md |
"""

# A malformed file with wrong column count in a row
MALFORMED_FILE = """\
# Session Index

| # | Date | Type | Focus | Reviews | Avg Grade | Summary | File |
|---|---|---|---|---|---|---|---|
| 1 | 2026-06-01 | learn | React Hooks | 5 | 4.20 | First session | session-01.md |
| 2 | 2026-06-02 | review |
"""


def _run(args, stdin_data=None):
    """Run the journal_writer CLI and return the CompletedProcess."""
    cmd = ["python3", TOOL_PATH] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=stdin_data,
    )


class TestAppendCreatesNewFile(unittest.TestCase):
    """append — creates new index.md from scratch with header and row."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmpdir, "journal", "index.md")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_creates_file_with_header_and_row(self):
        row = json.dumps({
            "session_number": 1,
            "date": "2026-06-01",
            "type": "learn",
            "focus": "React Hooks",
            "review_count": 5,
            "avg_grade": 4.2,
            "summary": "First session",
        })
        result = _run(["append", self.index_path, "--json", row])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Appended session 1", result.stdout)

        content = Path(self.index_path).read_text()
        self.assertIn(CANONICAL_HEADER, content)
        self.assertIn("session-01.md", content)
        self.assertIn("React Hooks", content)
        self.assertIn("4.20", content)

    def test_created_file_has_title(self):
        row = json.dumps({
            "session_number": 1,
            "date": "2026-06-01",
            "focus": "Testing",
        })
        result = _run(["append", self.index_path, "--json", row])

        self.assertEqual(result.returncode, 0, result.stderr)
        content = Path(self.index_path).read_text()
        self.assertIn("# Session Index", content)


class TestAppendToExistingFile(unittest.TestCase):
    """append — appends to existing file, auto-numbers correctly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmpdir, "index.md")
        Path(self.index_path).write_text(WELL_FORMATTED_FILE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_appends_new_row(self):
        row = json.dumps({
            "session_number": 3,
            "date": "2026-06-03",
            "type": "drill",
            "focus": "Promises",
            "review_count": 8,
            "avg_grade": 3.88,
            "summary": "Drill session",
        })
        result = _run(["append", self.index_path, "--json", row])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Appended session 3", result.stdout)

        content = Path(self.index_path).read_text()
        self.assertIn("session-03.md", content)
        self.assertIn("Promises", content)
        # Original rows still present
        self.assertIn("React Hooks", content)
        self.assertIn("Closures", content)

    def test_preserves_existing_rows(self):
        row = json.dumps({
            "session_number": 3,
            "date": "2026-06-03",
            "focus": "New Topic",
        })
        _run(["append", self.index_path, "--json", row])

        content = Path(self.index_path).read_text()
        lines = [l for l in content.split("\n") if l.strip().startswith("| ") and not l.strip().startswith("| #")]
        # Should have 3 data rows (original 2 + appended 1)
        self.assertEqual(len(lines), 3)


class TestAppendFromStdin(unittest.TestCase):
    """append --stdin — reads from stdin."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmpdir, "index.md")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_reads_json_from_stdin(self):
        row = json.dumps({
            "session_number": 1,
            "date": "2026-06-01",
            "type": "learn",
            "focus": "stdin test",
            "review_count": 2,
            "avg_grade": 5.0,
            "summary": "Via stdin",
        })
        result = _run(["append", self.index_path, "--stdin"], stdin_data=row)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Appended session 1", result.stdout)

        content = Path(self.index_path).read_text()
        self.assertIn("stdin test", content)
        self.assertIn("Via stdin", content)


class TestAppendOptionalColumns(unittest.TestCase):
    """append — handles optional columns (defaults to dash)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmpdir, "index.md")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_missing_optional_fields_default_to_dash(self):
        # Only provide required fields: session_number, date, focus
        row = json.dumps({
            "session_number": 1,
            "date": "2026-06-01",
            "focus": "Minimal row",
        })
        result = _run(["append", self.index_path, "--json", row])

        self.assertEqual(result.returncode, 0, result.stderr)

        content = Path(self.index_path).read_text()
        # Find the data row
        data_lines = [
            l for l in content.split("\n")
            if l.strip().startswith("|") and "Minimal row" in l
        ]
        self.assertEqual(len(data_lines), 1)
        cells = [c.strip() for c in data_lines[0].strip("|").split("|")]
        # Columns: #, Date, Type, Focus, Reviews, Avg Grade, Summary, File
        # Type (idx 2), Reviews (idx 4), Avg Grade (idx 5), Summary (idx 6) should be "—"
        self.assertEqual(cells[2], "—")  # Type
        self.assertEqual(cells[4], "—")  # Reviews
        self.assertEqual(cells[5], "—")  # Avg Grade

    def test_session_number_with_suffix(self):
        row = json.dumps({
            "session_number": "3b",
            "date": "2026-06-03",
            "focus": "Suffixed session",
        })
        result = _run(["append", self.index_path, "--json", row])

        self.assertEqual(result.returncode, 0, result.stderr)
        content = Path(self.index_path).read_text()
        self.assertIn("session-3b.md", content)


class TestValidatePassesOnWellFormatted(unittest.TestCase):
    """validate — passes on well-formatted file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmpdir, "index.md")
        Path(self.index_path).write_text(WELL_FORMATTED_FILE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_returns_zero_on_valid_file(self):
        result = _run(["validate", self.index_path])

        self.assertEqual(result.returncode, 0)
        self.assertIn("OK", result.stdout)
        self.assertIn("no format violations", result.stdout)


class TestValidateReportsViolations(unittest.TestCase):
    """validate — reports violations on malformed file."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmpdir, "index.md")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_reports_column_count_mismatch(self):
        Path(self.index_path).write_text(MALFORMED_FILE)
        result = _run(["validate", self.index_path])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("issue", result.stdout.lower())

    def test_reports_missing_columns(self):
        Path(self.index_path).write_text(FEWER_COLUMNS_FILE)
        result = _run(["validate", self.index_path])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing columns", result.stdout)

    def test_missing_file_exits_nonzero(self):
        result = _run(["validate", os.path.join(self.tmpdir, "nonexistent.md")])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr)


class TestErrorCases(unittest.TestCase):
    """Error cases: invalid JSON, missing file, missing args."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_append_invalid_json_exits_nonzero(self):
        path = os.path.join(self.tmpdir, "index.md")
        result = _run(["append", path, "--json", "{not valid json}"])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid JSON", result.stderr)

    def test_append_non_object_json_exits_nonzero(self):
        path = os.path.join(self.tmpdir, "index.md")
        result = _run(["append", path, "--json", '["an", "array"]'])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be an object", result.stderr)

    def test_append_without_json_or_stdin_exits_nonzero(self):
        path = os.path.join(self.tmpdir, "index.md")
        result = _run(["append", path])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--json", result.stderr)

    def test_validate_missing_file_exits_nonzero(self):
        path = os.path.join(self.tmpdir, "nonexistent.md")
        result = _run(["validate", path])

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not exist", result.stderr)

    def test_no_command_exits_nonzero(self):
        result = _run([])

        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
