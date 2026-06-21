#!/usr/bin/env python3
"""Tests for kmap_writer.py — add-concept and update-status subcommands.

Covers:
- add-concept appends to last table in 5-col format
- add-concept appends to last table in 4-col (legacy) format
- add-concept validates introduced format (S<N> or prior)
- add-concept rejects duplicate concept names
- add-concept rejects missing required fields
- update-status finds concept by name and updates status/last_tested/notes
- update-status preserves Introduced in 5-col tables
- update-status works on 4-col (legacy) tables
- update-status rejects unknown concept names
- concept search is case-insensitive
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WRITER = Path(__file__).resolve().parent.parent / "tools" / "srs" / "kmap_writer.py"

KMAP_5COL = """\
# Knowledge Map — Test

## Status Legend
- **Solid** — Reliable retrieval

## Concepts
| Concept | Status | Introduced | Last Tested | Notes |
|---------|--------|------------|-------------|-------|
| Alpha | Solid | S1 | S5 | Good recall |
| Beta | Developing | S2 | S4 | Needs work |
"""

KMAP_4COL = """\
# Knowledge Map — Legacy

| Concept | Status | Last Tested | Notes |
|---------|--------|-------------|-------|
| Gamma | Solid | S3 | Fine |
| Delta | Introduced | S1 | New |
"""

KMAP_MULTI_TABLE = """\
# Knowledge Map

## 1. Basics
| Concept | Status | Introduced | Last Tested | Notes |
|---------|--------|------------|-------------|-------|
| Foo | Solid | S1 | S5 | ok |

## 2. Advanced
| Concept | Status | Introduced | Last Tested | Notes |
|---------|--------|------------|-------------|-------|
| Bar | Developing | S3 | S6 | wip |
"""


def run_writer(*args, stdin: str = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(WRITER), *args],
        input=stdin,
        capture_output=True,
        text=True,
    )


def make_add_entry(concept: str, status: str = "Introduced",
                   introduced: str = "S1", last_tested: str = "S1",
                   notes: str = "") -> str:
    return json.dumps({
        "concept": concept,
        "status": status,
        "introduced": introduced,
        "last_tested": last_tested,
        "notes": notes,
    })


def make_update_entry(concept: str, status: str = "Solid",
                      last_tested: str = "S10", notes: str = "updated") -> str:
    return json.dumps({
        "concept": concept,
        "status": status,
        "last_tested": last_tested,
        "notes": notes,
    })


class AddConceptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="kmaptest_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_kmap(self, content: str) -> Path:
        p = self.tmp / "knowledge-map.md"
        p.write_text(content)
        return p

    def test_add_concept_5col(self) -> None:
        self._write_kmap(KMAP_5COL)
        result = run_writer(
            "add-concept", str(self.tmp), "--stdin",
            stdin=make_add_entry("NewConcept", introduced="S7", last_tested="S7"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "knowledge-map.md").read_text()
        self.assertIn("| NewConcept | Introduced | S7 | S7 |", body)

    def test_add_concept_4col_legacy(self) -> None:
        self._write_kmap(KMAP_4COL)
        result = run_writer(
            "add-concept", str(self.tmp), "--stdin",
            stdin=make_add_entry("Epsilon", introduced="S5", last_tested="S5"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "knowledge-map.md").read_text()
        # 4-col table: Introduced column not written
        self.assertIn("| Epsilon | Introduced | S5 |", body)
        self.assertNotIn("S5 | S5", body)

    def test_add_concept_appends_to_last_table(self) -> None:
        self._write_kmap(KMAP_MULTI_TABLE)
        result = run_writer(
            "add-concept", str(self.tmp), "--stdin",
            stdin=make_add_entry("Baz", introduced="S8", last_tested="S8"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "knowledge-map.md").read_text()
        lines = body.split("\n")
        baz_idx = next(i for i, l in enumerate(lines) if "Baz" in l)
        bar_idx = next(i for i, l in enumerate(lines) if "Bar" in l)
        self.assertGreater(baz_idx, bar_idx)

    def test_add_concept_validates_introduced_format(self) -> None:
        self._write_kmap(KMAP_5COL)
        result = run_writer(
            "add-concept", str(self.tmp), "--stdin",
            stdin=make_add_entry("Bad", introduced="session3"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be S<N> or 'prior'", result.stderr)

    def test_add_concept_accepts_prior(self) -> None:
        self._write_kmap(KMAP_5COL)
        result = run_writer(
            "add-concept", str(self.tmp), "--stdin",
            stdin=make_add_entry("PriorConcept", introduced="prior"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "knowledge-map.md").read_text()
        self.assertIn("| PriorConcept | Introduced | prior |", body)

    def test_add_concept_rejects_duplicate(self) -> None:
        self._write_kmap(KMAP_5COL)
        result = run_writer(
            "add-concept", str(self.tmp), "--stdin",
            stdin=make_add_entry("Alpha"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)

    def test_add_concept_duplicate_check_case_insensitive(self) -> None:
        self._write_kmap(KMAP_5COL)
        result = run_writer(
            "add-concept", str(self.tmp), "--stdin",
            stdin=make_add_entry("alpha"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)

    def test_add_concept_missing_concept_field(self) -> None:
        self._write_kmap(KMAP_5COL)
        result = run_writer(
            "add-concept", str(self.tmp), "--stdin",
            stdin=json.dumps({"status": "Introduced", "introduced": "S1"}),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("concept", result.stderr.lower())

    def test_add_concept_missing_introduced_field(self) -> None:
        self._write_kmap(KMAP_5COL)
        result = run_writer(
            "add-concept", str(self.tmp), "--stdin",
            stdin=json.dumps({"concept": "X", "status": "Introduced"}),
        )
        self.assertNotEqual(result.returncode, 0)


class UpdateStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="kmaptest_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_kmap(self, content: str) -> Path:
        p = self.tmp / "knowledge-map.md"
        p.write_text(content)
        return p

    def test_update_status_5col(self) -> None:
        self._write_kmap(KMAP_5COL)
        result = run_writer(
            "update-status", str(self.tmp), "--stdin",
            stdin=make_update_entry("Beta", status="Solid", last_tested="S10", notes="Mastered"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "knowledge-map.md").read_text()
        self.assertIn("| Beta | Solid | S2 | S10 | Mastered |", body)

    def test_update_preserves_introduced(self) -> None:
        self._write_kmap(KMAP_5COL)
        run_writer(
            "update-status", str(self.tmp), "--stdin",
            stdin=make_update_entry("Alpha", status="Mastered", last_tested="S20"),
        )
        body = (self.tmp / "knowledge-map.md").read_text()
        # Alpha was introduced at S1 — must still be S1
        self.assertIn("| Alpha | Mastered | S1 | S20 |", body)

    def test_update_status_4col_legacy(self) -> None:
        self._write_kmap(KMAP_4COL)
        result = run_writer(
            "update-status", str(self.tmp), "--stdin",
            stdin=make_update_entry("Gamma", status="Mastered", last_tested="S10"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "knowledge-map.md").read_text()
        self.assertIn("| Gamma | Mastered | S10 |", body)

    def test_update_status_case_insensitive_lookup(self) -> None:
        self._write_kmap(KMAP_5COL)
        result = run_writer(
            "update-status", str(self.tmp), "--stdin",
            stdin=make_update_entry("alpha", status="Developing"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_update_status_unknown_concept(self) -> None:
        self._write_kmap(KMAP_5COL)
        result = run_writer(
            "update-status", str(self.tmp), "--stdin",
            stdin=make_update_entry("NonExistent"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr)

    def test_update_status_multi_table(self) -> None:
        self._write_kmap(KMAP_MULTI_TABLE)
        result = run_writer(
            "update-status", str(self.tmp), "--stdin",
            stdin=make_update_entry("Foo", status="Mastered", last_tested="S15"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "knowledge-map.md").read_text()
        self.assertIn("| Foo | Mastered | S1 | S15 |", body)


if __name__ == "__main__":
    unittest.main()
