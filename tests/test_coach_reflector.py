#!/usr/bin/env python3
"""Tests for coach_reflector.py — coach self-reflection tool.

Covers:
- reflect parses CE/CP entries and clusters by keyword similarity
- reflect requires 2+ entries to produce candidates
- reflect skips clusters with only 1 entry
- reflect handles missing coach-errors.md
- evaluate handles missing coach-insights.md
- evaluate recommends validated after 5+ clean sessions
- evaluate recommends ineffective when errors recur
- evaluate skips non-active insights
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tools" / "coach" / "coach_reflector.py"


def run_tool(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True,
        text=True,
    )


COACH_ERRORS_CLUSTERABLE = """\
# Coach Errors

## CE-1 — Taught wrong API signature for fetch
**Session:** 3
**What happened:** Taught that fetch returns parsed JSON directly
**Correction:** fetch returns a Response object; must call .json() to parse
**Status:** active

## CE-2 — Wrong default method for fetch
**Session:** 5
**What happened:** Taught that fetch defaults to POST method
**Correction:** fetch defaults to GET method; POST requires explicit method option
**Status:** active

## CE-3 — Incorrect cookie expiration behavior
**Session:** 7
**What happened:** Taught that cookies expire at end of browser session by default
**Correction:** Session cookies do expire when browser closes, but persistent cookies require explicit Expires or Max-Age
**Status:** active
"""

COACH_ERRORS_SINGLE = """\
# Coach Errors

## CE-1 — Only one error
**Session:** 3
**What happened:** Something wrong
**Correction:** Something right
**Status:** active
"""

COACH_INSIGHTS = """\
# Coach Insights

## Teaching Behavior Rules

### CI-1: Verify API signatures before teaching
- **Source**: CE-1, CE-2 (2 errors in API accuracy)
- **Rule**: Always verify API signatures against documentation before presenting
- **Adopted**: Session 8
- **Sessions active**: 5
- **Status**: active
- **Impact**: Pending evaluation

### CI-2: Retired rule
- **Source**: CE-99
- **Rule**: Some old rule
- **Adopted**: Session 2
- **Sessions active**: 10
- **Status**: ineffective
- **Impact**: Did not reduce errors
"""


def make_journal_index(sessions: int) -> str:
    lines = [
        "# Session Index",
        "",
        "| # | Date | Type | Focus | Reviews | Avg Grade | Summary | File |",
        "|---|------|------|-------|---------|-----------|---------|------|",
    ]
    for i in range(1, sessions + 1):
        lines.append(f"| {i} | 2026-01-{i:02d} | deep | Topic | 0 | — | — | session-{i:02d}.md |")
    return "\n".join(lines)


class ReflectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="reflector_"))
        self.learning = self.tmp / "learning"
        self.learning.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reflect_clusters_similar_errors(self) -> None:
        (self.learning / "coach-errors.md").write_text(COACH_ERRORS_CLUSTERABLE)
        result = run_tool("reflect", str(self.learning))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertGreaterEqual(len(data["candidates"]), 1)
        self.assertEqual(data["total_errors_analyzed"], 3)

    def test_reflect_insufficient_data(self) -> None:
        (self.learning / "coach-errors.md").write_text(COACH_ERRORS_SINGLE)
        result = run_tool("reflect", str(self.learning))
        data = json.loads(result.stdout)
        self.assertEqual(data["candidates"], [])
        self.assertIn("Insufficient", data["message"])

    def test_reflect_no_errors_file(self) -> None:
        result = run_tool("reflect", str(self.learning))
        data = json.loads(result.stdout)
        self.assertEqual(data["candidates"], [])
        self.assertEqual(data["total_errors_analyzed"], 0)

    def test_reflect_candidate_has_required_fields(self) -> None:
        (self.learning / "coach-errors.md").write_text(COACH_ERRORS_CLUSTERABLE)
        result = run_tool("reflect", str(self.learning))
        data = json.loads(result.stdout)
        if data["candidates"]:
            c = data["candidates"][0]
            self.assertIn("pattern", c)
            self.assertIn("source_entries", c)
            self.assertIn("proposed_rule", c)
            self.assertIn("confidence", c)
            self.assertIn("error_count", c)


class EvaluateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="reflector_"))
        self.learning = self.tmp / "learning"
        self.learning.mkdir()
        journal = self.learning / "journal"
        journal.mkdir()
        (journal / "index.md").write_text(make_journal_index(15))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_evaluate_no_insights_file(self) -> None:
        result = run_tool("evaluate", str(self.learning))
        data = json.loads(result.stdout)
        self.assertEqual(data["evaluations"], [])
        self.assertIn("No insights", data["message"])

    def test_evaluate_validates_after_clean_sessions(self) -> None:
        (self.learning / "coach-insights.md").write_text(COACH_INSIGHTS)
        (self.learning / "coach-errors.md").write_text(COACH_ERRORS_SINGLE)
        result = run_tool("evaluate", str(self.learning))
        data = json.loads(result.stdout)
        # CI-1 adopted at session 8, current is 15, 7 sessions clean
        ci1 = next(e for e in data["evaluations"] if e["id"] == "CI-1")
        self.assertEqual(ci1["recommended_status"], "validated")
        self.assertEqual(ci1["sessions_since_adoption"], 7)

    def test_evaluate_skips_non_active(self) -> None:
        (self.learning / "coach-insights.md").write_text(COACH_INSIGHTS)
        (self.learning / "coach-errors.md").write_text("")
        result = run_tool("evaluate", str(self.learning))
        data = json.loads(result.stdout)
        ids = [e["id"] for e in data["evaluations"]]
        self.assertNotIn("CI-2", ids)

    def test_evaluate_detects_recurrence(self) -> None:
        insights = """\
# Coach Insights

## Teaching Behavior Rules

### CI-1: Verify fetch API details
- **Source**: CE-1, CE-2
- **Rule**: Verify fetch API before teaching
- **Adopted**: Session 3
- **Status**: active
"""
        errors = """\
# Coach Errors

## CE-1 — Wrong fetch signature
**Session:** 2
**What happened:** Taught wrong fetch API
**Correction:** fetch returns Response, call .json()
**Status:** active

## CE-2 — Wrong fetch default
**Session:** 3
**What happened:** Taught wrong fetch default method
**Correction:** fetch defaults to GET
**Status:** active

## CE-3 — Another fetch error after adoption
**Session:** 10
**What happened:** Taught that fetch rejects on HTTP errors
**Correction:** fetch only rejects on network errors, not HTTP status codes like 404
**Status:** active
"""
        (self.learning / "coach-insights.md").write_text(insights)
        (self.learning / "coach-errors.md").write_text(errors)
        result = run_tool("evaluate", str(self.learning))
        data = json.loads(result.stdout)
        ci1 = data["evaluations"][0]
        self.assertEqual(ci1["errors_since_adoption"], 1)
        self.assertEqual(ci1["recommended_status"], "ineffective")


if __name__ == "__main__":
    unittest.main()
