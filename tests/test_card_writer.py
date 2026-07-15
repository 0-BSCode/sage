#!/usr/bin/env python3
"""Regression-safety tests for the card_writer CLI tool.

Tests the CLI contract via subprocess — no internal imports.
Every test creates an isolated temp directory and invokes the tool
as a separate process, asserting exit codes, stdout/stderr, and
file side-effects.
"""

import json
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

TOOL_PATH = str(
    Path(__file__).resolve().parent.parent / "tools" / "srs" / "card_writer.py"
)

TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WELL_FORMED_CARDS_MD = """\
# Flashcards: Test Topic

Last updated: 2025-01-01

---

### Card 1
**Q:** What is a closure?
**A:** A function that retains access to its lexical scope.
**Tags:** type:fact, javascript

---

### Card 2
**Q:** Why do closures matter?
**A:** They enable data privacy and functional patterns.
**Tags:** type:why, javascript

---
"""

MALFORMED_CARDS_MD = """\
# Flashcards: Bad Format

---

### Card 1
**Q**: What is a closure?
**A**: A function that captures its environment.
**Tags**: type:fact, javascript

---

### Card 2
**Q** : Another bad line
**A**: Answer here
**Tags**: type:fact

---
"""


def _make_card(question: str, answer: str, tags: list[str]) -> dict:
    return {"question": question, "answer": answer, "tags": tags}


def _run(args: list[str], stdin_data: str | None = None) -> subprocess.CompletedProcess:
    """Run the card_writer tool as a subprocess."""
    return subprocess.run(
        ["python3", TOOL_PATH] + args,
        capture_output=True,
        text=True,
        input=stdin_data,
    )


class TestAppendCreatesNew(unittest.TestCase):
    """append — creates new cards.md from scratch with correct format."""

    def test_append_creates_cards_in_empty_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            # The tool requires the file to exist already
            cards_md.write_text("# Flashcards\n\nLast updated: 2025-01-01\n\n---\n")

            payload = json.dumps([
                _make_card("What is X?", "X is a thing.", ["type:fact", "testing"]),
            ])
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Appended 1 card(s)", result.stdout)

            content = cards_md.read_text()
            self.assertIn("### Card 1", content)
            self.assertIn("**Q:** What is X?", content)
            self.assertIn("**A:** X is a thing.", content)
            self.assertIn("**Tags:** type:fact, testing", content)
            self.assertIn(TODAY, content)


class TestAppendAutoNumbers(unittest.TestCase):
    """append — appends to existing file, auto-numbers correctly."""

    def test_auto_numbering_continues_from_last(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(WELL_FORMED_CARDS_MD)

            payload = json.dumps([
                _make_card("What is hoisting?", "Variable declarations are moved to the top.", ["type:fact", "javascript"]),
            ])
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0, result.stderr)
            content = cards_md.read_text()
            self.assertIn("### Card 3", content)
            self.assertNotIn("### Card 0", content)

    def test_multiple_cards_numbered_sequentially(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(WELL_FORMED_CARDS_MD)

            payload = json.dumps([
                _make_card("Q three?", "A three.", ["type:fact"]),
                _make_card("Q four?", "A four.", ["type:why"]),
            ])
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0, result.stderr)
            content = cards_md.read_text()
            self.assertIn("### Card 3", content)
            self.assertIn("### Card 4", content)
            self.assertIn("Card numbers: 3", result.stdout)


class TestAppendStdin(unittest.TestCase):
    """append --stdin — reads from stdin (pipe)."""

    def test_reads_json_from_stdin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(WELL_FORMED_CARDS_MD)

            payload = json.dumps([
                _make_card("What is stdin?", "Standard input stream.", ["type:fact"]),
            ])
            result = _run(["append", str(cards_md), "--stdin"], stdin_data=payload)

            self.assertEqual(result.returncode, 0, result.stderr)
            content = cards_md.read_text()
            self.assertIn("### Card 3", content)
            self.assertIn("**Q:** What is stdin?", content)


class TestAppendDedupDetection(unittest.TestCase):
    """append — dedup detection: skips duplicate questions, reports them."""

    def test_skips_exact_duplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(WELL_FORMED_CARDS_MD)

            # "What is a closure?" already exists as Card 1
            payload = json.dumps([
                _make_card("What is a closure?", "Different answer.", ["type:fact"]),
            ])
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0)
            self.assertIn("Skipped 1 duplicate", result.stderr)
            self.assertIn("No valid cards to append", result.stdout)

    def test_skips_case_insensitive_duplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(WELL_FORMED_CARDS_MD)

            payload = json.dumps([
                _make_card("WHAT IS A CLOSURE?", "Another answer.", ["type:fact"]),
            ])
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0)
            self.assertIn("Skipped 1 duplicate", result.stderr)

    def test_skips_trailing_punctuation_duplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(WELL_FORMED_CARDS_MD)

            # Original is "What is a closure?" — try without question mark
            payload = json.dumps([
                _make_card("What is a closure", "Yet another answer.", ["type:fact"]),
            ])
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0)
            self.assertIn("Skipped 1 duplicate", result.stderr)

    def test_intra_batch_dedup(self):
        """Two identical questions in the same batch — only one should be added."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text("# Flashcards\n\nLast updated: 2025-01-01\n\n---\n")

            payload = json.dumps([
                _make_card("Same question?", "Answer one.", ["type:fact"]),
                _make_card("Same question?", "Answer two.", ["type:fact"]),
            ])
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0)
            content = cards_md.read_text()
            # Only one card should exist
            self.assertIn("### Card 1", content)
            self.assertNotIn("### Card 2", content)
            self.assertIn("Skipped 1 duplicate", result.stderr)


class TestAppendTypeTagValidation(unittest.TestCase):
    """append — each card must have a type: tag from the approved set."""

    def test_rejects_card_without_type_tag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text("# Flashcards\n\nLast updated: 2025-01-01\n\n---\n")

            payload = json.dumps([
                _make_card("No type tag?", "Answer.", ["javascript", "testing"]),
            ])
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0)
            self.assertIn("Rejected 1 card(s) with type tag errors", result.stderr)
            self.assertIn("missing required type tag", result.stderr)
            self.assertIn("No valid cards to append", result.stdout)

    def test_rejects_card_with_unapproved_type_tag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text("# Flashcards\n\nLast updated: 2025-01-01\n\n---\n")

            payload = json.dumps([
                _make_card("Bad type?", "Answer.", ["type:bogus"]),
            ])
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0)
            self.assertIn("unapproved type tag", result.stderr)

    def test_rejects_card_with_multiple_type_tags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text("# Flashcards\n\nLast updated: 2025-01-01\n\n---\n")

            payload = json.dumps([
                _make_card("Two types?", "Answer.", ["type:fact", "type:why"]),
            ])
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0)
            self.assertIn("multiple type tags", result.stderr)

    def test_accepts_all_approved_type_tags(self):
        approved = ["fact", "why", "process", "discrimination", "transfer", "reverse", "error"]
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text("# Flashcards\n\nLast updated: 2025-01-01\n\n---\n")

            cards = [
                _make_card(f"Question about {t}?", f"Answer for {t}.", [f"type:{t}"])
                for t in approved
            ]
            payload = json.dumps(cards)
            result = _run(["append", str(cards_md), "--json", payload])

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f"Appended {len(approved)} card(s)", result.stdout)


class TestValidatePass(unittest.TestCase):
    """validate — passes on well-formatted file."""

    def test_validate_clean_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(WELL_FORMED_CARDS_MD)

            result = _run(["validate", str(cards_md)])

            self.assertEqual(result.returncode, 0)
            self.assertIn("OK", result.stdout)


class TestValidateReportsViolations(unittest.TestCase):
    """validate — reports violations on malformed file (exits non-zero)."""

    def test_validate_malformed_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(MALFORMED_CARDS_MD)

            result = _run(["validate", str(cards_md)])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("format violation", result.stdout)

    def test_validate_reports_bad_q_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            # **Q**: instead of **Q:**
            cards_md.write_text(
                "### Card 1\n**Q**: Bad question format\n**A:** Answer\n**Tags:** type:fact\n---\n"
            )

            result = _run(["validate", str(cards_md)])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bad_q_format", result.stdout)


class TestFixRewritesFormat(unittest.TestCase):
    """fix — rewrites non-canonical format in-place."""

    def test_fix_corrects_colon_placement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(MALFORMED_CARDS_MD)

            result = _run(["fix", str(cards_md)])

            self.assertEqual(result.returncode, 0)
            self.assertIn("Fixed", result.stdout)

            content = cards_md.read_text()
            # After fix, colons should be inside the bold markers
            self.assertNotIn("**Q**:", content)
            self.assertNotIn("**A**:", content)
            self.assertNotIn("**Tags**:", content)

    def test_fix_then_validate_passes(self):
        """After fix, validate should pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(MALFORMED_CARDS_MD)

            fix_result = _run(["fix", str(cards_md)])
            self.assertEqual(fix_result.returncode, 0)

            validate_result = _run(["validate", str(cards_md)])
            self.assertEqual(validate_result.returncode, 0)
            self.assertIn("OK", validate_result.stdout)


class TestFixNoOp(unittest.TestCase):
    """fix — no-op on already-canonical file."""

    def test_fix_noop_on_clean_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(WELL_FORMED_CARDS_MD)
            original = cards_md.read_text()

            result = _run(["fix", str(cards_md)])

            self.assertEqual(result.returncode, 0)
            self.assertIn("No fixes needed", result.stdout)
            self.assertEqual(cards_md.read_text(), original)


class TestErrorCases(unittest.TestCase):
    """Error cases: invalid JSON, missing file, non-array JSON."""

    def test_append_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text("# Flashcards\n\n---\n")

            result = _run(["append", str(cards_md), "--json", "not valid json{{{"])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid JSON", result.stderr)

    def test_append_non_array_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text("# Flashcards\n\n---\n")

            result = _run(["append", str(cards_md), "--json", '{"not": "an array"}'])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be an array", result.stderr)

    def test_append_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "nonexistent" / "cards.md"

            result = _run(["append", str(missing), "--json", "[]"])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not exist", result.stderr)

    def test_validate_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "cards.md"

            result = _run(["validate", str(missing)])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not exist", result.stderr)

    def test_fix_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "cards.md"

            result = _run(["fix", str(missing)])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not exist", result.stderr)

    def test_append_no_json_or_stdin_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text("# Flashcards\n\n---\n")

            result = _run(["append", str(cards_md)])

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--json or --stdin", result.stderr)

    def test_directory_path_resolves_to_cards_md(self):
        """Passing a directory should resolve to <dir>/cards.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cards_md = Path(tmpdir) / "cards.md"
            cards_md.write_text(WELL_FORMED_CARDS_MD)

            result = _run(["validate", tmpdir])

            self.assertEqual(result.returncode, 0)
            self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
