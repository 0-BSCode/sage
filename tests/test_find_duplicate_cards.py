#!/usr/bin/env python3
"""Regression-safety tests for find_duplicate_cards.py.

Tests the CLI contract via subprocess — no internal imports.
Verifies duplicate detection, case-insensitive matching, retired-card
exclusion, multi-deck scanning, and edge cases (empty root, no decks).
"""

import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

TOOL_PATH = str(
    Path(__file__).resolve().parent.parent / "tools" / "srs" / "find_duplicate_cards.py"
)


def _make_cards_md(cards):
    """Build a minimal cards.md from a list of (number, question, retired) tuples."""
    lines = ["# Flashcards: Test Deck", "", "Last updated: 2026-06-01", "", "---", ""]
    for number, question, retired in cards:
        header = f"### Card {number}"
        if retired:
            header += " [RETIRED]"
        lines.append(header)
        lines.append(f"**Q:** {question}")
        lines.append(f"**A:** Answer for card {number}")
        lines.append("**Tags:** test, type:fact")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _run(root_dir, extra_args=None):
    """Run find_duplicate_cards.py via subprocess."""
    cmd = ["python3", TOOL_PATH, "--root", str(root_dir)]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


class TestFindDuplicateCardsNoDuplicates(unittest.TestCase):
    """No duplicates — clean report."""

    def test_no_duplicates_clean_report(self):
        with tempfile.TemporaryDirectory() as root:
            deck_dir = Path(root) / "topic-a" / "learning"
            deck_dir.mkdir(parents=True)
            cards_md = deck_dir / "cards.md"
            cards_md.write_text(
                _make_cards_md([
                    (1, "What is X?", False),
                    (2, "What is Y?", False),
                ])
            )

            result = _run(root)

            self.assertEqual(result.returncode, 0)
            self.assertIn("No duplicates found", result.stdout)


class TestFindDuplicateCardsExactDuplicates(unittest.TestCase):
    """Exact duplicate questions detected."""

    def test_exact_duplicate_detected(self):
        with tempfile.TemporaryDirectory() as root:
            deck_dir = Path(root) / "topic-a" / "learning"
            deck_dir.mkdir(parents=True)
            cards_md = deck_dir / "cards.md"
            cards_md.write_text(
                _make_cards_md([
                    (1, "What is a closure?", False),
                    (2, "What is a closure?", False),
                    (3, "What is a variable?", False),
                ])
            )

            result = _run(root)

            self.assertEqual(result.returncode, 0)
            self.assertIn("Duplicate group", result.stdout)
            self.assertIn("2 cards", result.stdout)
            self.assertIn("card-1", result.stdout)
            self.assertIn("card-2", result.stdout)


class TestFindDuplicateCardsCaseInsensitive(unittest.TestCase):
    """Case-insensitive duplicates detected."""

    def test_case_insensitive_duplicate(self):
        with tempfile.TemporaryDirectory() as root:
            deck_dir = Path(root) / "topic-a" / "learning"
            deck_dir.mkdir(parents=True)
            cards_md = deck_dir / "cards.md"
            cards_md.write_text(
                _make_cards_md([
                    (1, "What is X?", False),
                    (2, "what is x?", False),
                ])
            )

            result = _run(root)

            self.assertEqual(result.returncode, 0)
            self.assertIn("Duplicate group", result.stdout)
            self.assertIn("2 cards", result.stdout)


class TestFindDuplicateCardsRetiredExcluded(unittest.TestCase):
    """Retired cards excluded from comparison."""

    def test_retired_card_not_counted_as_duplicate(self):
        with tempfile.TemporaryDirectory() as root:
            deck_dir = Path(root) / "topic-a" / "learning"
            deck_dir.mkdir(parents=True)
            cards_md = deck_dir / "cards.md"
            cards_md.write_text(
                _make_cards_md([
                    (1, "What is a closure?", True),   # retired
                    (2, "What is a closure?", False),   # active — no dup partner
                ])
            )

            result = _run(root)

            self.assertEqual(result.returncode, 0)
            self.assertIn("No duplicates found", result.stdout)

    def test_retired_both_no_duplicate_group(self):
        """Two retired cards with same question should not form a group."""
        with tempfile.TemporaryDirectory() as root:
            deck_dir = Path(root) / "topic-a" / "learning"
            deck_dir.mkdir(parents=True)
            cards_md = deck_dir / "cards.md"
            cards_md.write_text(
                _make_cards_md([
                    (1, "What is a closure?", True),
                    (2, "What is a closure?", True),
                    (3, "What is a variable?", False),
                ])
            )

            result = _run(root)

            self.assertEqual(result.returncode, 0)
            self.assertIn("No duplicates found", result.stdout)


class TestFindDuplicateCardsMultipleDecks(unittest.TestCase):
    """Multiple decks scanned under root."""

    def test_multiple_decks_scanned(self):
        with tempfile.TemporaryDirectory() as root:
            # Deck A — no duplicates
            deck_a = Path(root) / "topic-a" / "learning"
            deck_a.mkdir(parents=True)
            (deck_a / "cards.md").write_text(
                _make_cards_md([
                    (1, "What is X?", False),
                    (2, "What is Y?", False),
                ])
            )

            # Deck B — has duplicates
            deck_b = Path(root) / "topic-b" / "learning"
            deck_b.mkdir(parents=True)
            (deck_b / "cards.md").write_text(
                _make_cards_md([
                    (1, "What is Z?", False),
                    (2, "What is Z?", False),
                ])
            )

            result = _run(root)

            self.assertEqual(result.returncode, 0)
            self.assertIn("Scanning 2 deck(s)", result.stdout)
            self.assertIn("topic-a", result.stdout)
            self.assertIn("topic-b", result.stdout)
            # Summary should show 1 deck with duplicates
            self.assertIn("Decks with duplicates:  1", result.stdout)

    def test_summary_footer_present(self):
        with tempfile.TemporaryDirectory() as root:
            deck_dir = Path(root) / "topic-a" / "learning"
            deck_dir.mkdir(parents=True)
            (deck_dir / "cards.md").write_text(
                _make_cards_md([
                    (1, "What is X?", False),
                ])
            )

            result = _run(root)

            self.assertEqual(result.returncode, 0)
            self.assertIn("SUMMARY", result.stdout)
            self.assertIn("Decks scanned:", result.stdout)


class TestFindDuplicateCardsNoDecks(unittest.TestCase):
    """No decks found — informative message."""

    def test_no_decks_found_message(self):
        with tempfile.TemporaryDirectory() as root:
            # Root exists but has no */learning/cards.md structure
            result = _run(root)

            self.assertEqual(result.returncode, 0)
            self.assertIn("No decks found", result.stdout)


class TestFindDuplicateCardsEmptyRoot(unittest.TestCase):
    """Empty root directory."""

    def test_empty_root_directory(self):
        with tempfile.TemporaryDirectory() as root:
            result = _run(root)

            self.assertEqual(result.returncode, 0)
            self.assertIn("No decks found", result.stdout)

    def test_nonexistent_root_exits_with_error(self):
        result = _run("/tmp/nonexistent_root_12345678")

        self.assertEqual(result.returncode, 1)
        self.assertIn("does not exist", result.stderr)


class TestFindDuplicateCardsExitCode(unittest.TestCase):
    """Exit code is always 0 for valid roots (report tool, not CI gate)."""

    def test_exit_zero_with_duplicates(self):
        with tempfile.TemporaryDirectory() as root:
            deck_dir = Path(root) / "topic-a" / "learning"
            deck_dir.mkdir(parents=True)
            (deck_dir / "cards.md").write_text(
                _make_cards_md([
                    (1, "Same question", False),
                    (2, "Same question", False),
                ])
            )

            result = _run(root)
            self.assertEqual(result.returncode, 0)

    def test_exit_zero_without_duplicates(self):
        with tempfile.TemporaryDirectory() as root:
            deck_dir = Path(root) / "topic-a" / "learning"
            deck_dir.mkdir(parents=True)
            (deck_dir / "cards.md").write_text(
                _make_cards_md([
                    (1, "Question A", False),
                    (2, "Question B", False),
                ])
            )

            result = _run(root)
            self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
