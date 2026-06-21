#!/usr/bin/env python3
"""Tests for weak_spot_writer.py — kind-aware writer.

Covers:
- --kind WS writes to weak-spots.md with `## WS-[N] —` headings + History
- --kind M writes to weak-spots.md as WS alias with Category: wrong-model
- --kind CE writes to coach-errors.md with `## CE-[N] —` headings (unchanged)
- --kind CP writes to coach-errors.md with `## CP-[N] —` headings (unchanged)
- Mismatched explicit paths raise (CE → weak-spots.md is rejected, etc.)
- CE and CP namespaces are independent within coach-errors.md
- weak-spots.md is auto-created with canonical header on first write
- coach-errors.md is auto-created with canonical header on first write
- Category validation rejects invalid categories
- History subsection is generated for WS entries
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WRITER = Path(__file__).resolve().parent.parent / "tools" / "srs" / "weak_spot_writer.py"


def run_writer(*args, stdin: str = None) -> subprocess.CompletedProcess:
    """Invoke the writer as a subprocess."""
    return subprocess.run(
        [sys.executable, str(WRITER), *args],
        input=stdin,
        capture_output=True,
        text=True,
    )


def make_ws_entry(description: str, session: int = 1, category: str = "wrong-model") -> str:
    return json.dumps(
        {
            "description": description,
            "session": session,
            "category": category,
            "what_happened": "what",
            "correct_model": "correct",
            "status": "active",
        }
    )


def make_ce_entry(description: str, session: int = 1) -> str:
    return json.dumps(
        {
            "description": description,
            "session": session,
            "what_happened": "what",
            "correction": "correct",
            "status": "active",
        }
    )


class WeakSpotWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="wstest_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # WS kind: append + heading format
    # ------------------------------------------------------------------

    def test_append_kind_ws_creates_WS_heading(self) -> None:
        result = run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=make_ws_entry("Learner gap"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("## WS-1 — Learner gap", body)

    def test_append_kind_ws_includes_category(self) -> None:
        result = run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=make_ws_entry("Gap", category="fragile-recall"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("**Category:** fragile-recall", body)

    def test_append_kind_ws_includes_correct_model(self) -> None:
        result = run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=make_ws_entry("Gap"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("**Correct model:** correct", body)

    def test_append_kind_ws_includes_history_subsection(self) -> None:
        result = run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=make_ws_entry("Gap"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("### History", body)
        self.assertIn("- **S1:** First observed", body)

    def test_append_kind_ws_custom_history(self) -> None:
        entry = json.dumps({
            "description": "Gap",
            "session": 3,
            "category": "wrong-model",
            "what_happened": "what",
            "correct_model": "correct",
            "status": "active",
            "history": "Learner confused X with Y during exercise",
        })
        result = run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=entry,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("- **S3:** Learner confused X with Y during exercise", body)

    def test_append_kind_ws_auto_sets_last_tested(self) -> None:
        result = run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=make_ws_entry("Gap", session=5),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("**Last tested:** S5", body)

    def test_append_kind_ws_includes_concepts(self) -> None:
        entry = json.dumps({
            "description": "Gap",
            "session": 1,
            "category": "wrong-model",
            "what_happened": "what",
            "correct_model": "correct",
            "concepts": "closures, hoisting",
            "status": "active",
        })
        result = run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=entry,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("**Concepts:** closures, hoisting", body)

    # ------------------------------------------------------------------
    # M kind: alias for WS with auto wrong-model
    # ------------------------------------------------------------------

    def test_append_kind_m_writes_ws_heading(self) -> None:
        """--kind M writes WS-N headings, not M-N."""
        entry = json.dumps({
            "description": "Learner misconception",
            "session": 1,
            "what_happened": "what",
            "correct_model": "correct",
            "status": "active",
        })
        result = run_writer(
            "append", str(self.tmp), "--kind", "M", "--stdin",
            stdin=entry,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("## WS-1 — Learner misconception", body)
        self.assertNotIn("## M1", body)

    def test_append_kind_m_auto_sets_category_wrong_model(self) -> None:
        entry = json.dumps({
            "description": "Wrong model",
            "session": 1,
            "what_happened": "what",
            "correct_model": "correct",
            "status": "active",
        })
        result = run_writer(
            "append", str(self.tmp), "--kind", "M", "--stdin",
            stdin=entry,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("**Category:** wrong-model", body)

    def test_append_kind_m_respects_explicit_category(self) -> None:
        """If user already set category, M alias doesn't override."""
        entry = json.dumps({
            "description": "Wrong model",
            "session": 1,
            "category": "incomplete-model",
            "what_happened": "what",
            "correct_model": "correct",
            "status": "active",
        })
        result = run_writer(
            "append", str(self.tmp), "--kind", "M", "--stdin",
            stdin=entry,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("**Category:** incomplete-model", body)

    def test_kind_m_and_ws_share_namespace(self) -> None:
        """M and WS entries share the same WS-N numbering."""
        run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=make_ws_entry("First"),
        )
        entry = json.dumps({
            "description": "Second",
            "session": 2,
            "what_happened": "what",
            "correct_model": "correct",
            "status": "active",
        })
        result = run_writer(
            "append", str(self.tmp), "--kind", "M", "--stdin",
            stdin=entry,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("## WS-1 — First", body)
        self.assertIn("## WS-2 — Second", body)

    # ------------------------------------------------------------------
    # CE/CP: unchanged behavior
    # ------------------------------------------------------------------

    def test_append_kind_ce_creates_CE_dash_heading(self) -> None:
        result = run_writer(
            "append", str(self.tmp), "--kind", "CE", "--stdin",
            stdin=make_ce_entry("Coach content error"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "coach-errors.md").read_text()
        self.assertIn("## CE-1 — Coach content error", body)

    def test_append_kind_cp_creates_CP_dash_heading(self) -> None:
        result = run_writer(
            "append", str(self.tmp), "--kind", "CP", "--stdin",
            stdin=make_ce_entry("Coach process failure"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "coach-errors.md").read_text()
        self.assertIn("## CP-1 — Coach process failure", body)

    def test_ce_and_cp_namespaces_count_independently(self) -> None:
        for kind, desc in [
            ("CE", "first content"),
            ("CP", "first process"),
            ("CE", "second content"),
            ("CP", "second process"),
            ("CE", "third content"),
        ]:
            r = run_writer(
                "append", str(self.tmp), "--kind", kind, "--stdin",
                stdin=make_ce_entry(desc),
            )
            self.assertEqual(r.returncode, 0, r.stderr)

        body = (self.tmp / "coach-errors.md").read_text()
        self.assertIn("## CE-1 — first content", body)
        self.assertIn("## CE-2 — second content", body)
        self.assertIn("## CE-3 — third content", body)
        self.assertIn("## CP-1 — first process", body)
        self.assertIn("## CP-2 — second process", body)

    def test_ce_entry_has_no_history_subsection(self) -> None:
        result = run_writer(
            "append", str(self.tmp), "--kind", "CE", "--stdin",
            stdin=make_ce_entry("Error"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "coach-errors.md").read_text()
        self.assertNotIn("### History", body)

    # ------------------------------------------------------------------
    # Path validation (kind ↔ filename)
    # ------------------------------------------------------------------

    def test_kind_ws_with_explicit_coach_errors_path_rejected(self) -> None:
        target = self.tmp / "coach-errors.md"
        target.write_text("# Coach Errors\n\n---\n")
        result = run_writer(
            "append", str(target), "--kind", "WS", "--stdin",
            stdin=make_ws_entry("misfiled"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match kind=WS", result.stderr)

    def test_kind_ce_with_explicit_weak_spots_path_rejected(self) -> None:
        target = self.tmp / "weak-spots.md"
        target.write_text("# Weak Spots\n\n---\n")
        result = run_writer(
            "append", str(target), "--kind", "CE", "--stdin",
            stdin=make_ce_entry("misfiled coach error"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match kind=CE", result.stderr)

    # ------------------------------------------------------------------
    # Auto-creation
    # ------------------------------------------------------------------

    def test_weak_spots_auto_created_with_canonical_header(self) -> None:
        target = self.tmp / "weak-spots.md"
        self.assertFalse(target.exists())
        result = run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=make_ws_entry("first"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(target.exists())
        body = target.read_text()
        self.assertIn("# Weak Spots", body)
        self.assertIn("wrong-model", body)
        self.assertIn("incomplete-model", body)
        self.assertIn("fragile-recall", body)
        self.assertIn("application-gap", body)

    def test_coach_errors_auto_created_with_canonical_header(self) -> None:
        target = self.tmp / "coach-errors.md"
        self.assertFalse(target.exists())
        result = run_writer(
            "append", str(self.tmp), "--kind", "CE", "--stdin",
            stdin=make_ce_entry("first ever"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(target.exists())
        body = target.read_text()
        self.assertIn("# Coach Errors", body)
        self.assertIn("weak-spots.md", body)

    # ------------------------------------------------------------------
    # Category validation
    # ------------------------------------------------------------------

    def test_invalid_category_rejected_on_append(self) -> None:
        result = run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=make_ws_entry("bad", category="totally-wrong"),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid category", result.stderr)

    def test_all_valid_categories_accepted(self) -> None:
        for cat in ["wrong-model", "incomplete-model", "fragile-recall", "application-gap"]:
            # Each iteration uses a fresh tmp dir to avoid numbering issues
            tmp = Path(tempfile.mkdtemp(prefix="wscat_"))
            try:
                result = run_writer(
                    "append", str(tmp), "--kind", "WS", "--stdin",
                    stdin=make_ws_entry(f"test-{cat}", category=cat),
                )
                self.assertEqual(result.returncode, 0, f"Category {cat} rejected: {result.stderr}")
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Validate command
    # ------------------------------------------------------------------

    def test_validate_kind_ws_passes_on_clean_file(self) -> None:
        run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=make_ws_entry("clean entry"),
        )
        result = run_writer("validate", str(self.tmp), "--kind", "WS")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_validate_kind_ce_passes_on_clean_file(self) -> None:
        run_writer(
            "append", str(self.tmp), "--kind", "CE", "--stdin",
            stdin=make_ce_entry("clean entry"),
        )
        result = run_writer("validate", str(self.tmp), "--kind", "CE")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    # ------------------------------------------------------------------
    # Fix command preserves History
    # ------------------------------------------------------------------

    def test_fix_preserves_history(self) -> None:
        entry = json.dumps({
            "description": "Gap",
            "session": 3,
            "category": "wrong-model",
            "what_happened": "what",
            "correct_model": "correct",
            "status": "active",
            "history": "Confused X with Y",
        })
        run_writer(
            "append", str(self.tmp), "--kind", "WS", "--stdin",
            stdin=entry,
        )
        result = run_writer("fix", str(self.tmp), "--kind", "WS")
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.tmp / "weak-spots.md").read_text()
        self.assertIn("### History", body)
        self.assertIn("- **S3:** Confused X with Y", body)


if __name__ == "__main__":
    unittest.main()
