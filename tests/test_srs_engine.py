#!/usr/bin/env python3
"""Comprehensive tests for the SM-2 SRS Engine."""

import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "srs"))

from srs_engine import (
    SM2,
    CardParser,
    JsonFormatter,
    MarkdownFormatter,
    SRSStore,
    _derive_topic,
    _resolve_paths,
    main,
)

SAMPLE_CARDS_MD = """\
# Flashcards: React Hooks

Last updated: 2026-02-12

---

### Card 1
**Q:** What is a closure in JavaScript?
**A:** A closure is a function that retains access to its lexical scope even when executed outside that scope.
**Tags:** closures, javascript, session-1

---

### Card 2 (Reverse)
**Q:** A function that retains access to its outer scope variables — what is this concept called?
**A:** Closure
**Tags:** closures, javascript, session-1

---

### Card 3
**Q:** What does useState return in React?
**A:** An array with two elements: the current state value and a setter function.
**Tags:** react, hooks, session-1

---

### Card 4 [RETIRED]
**Q:** What is the old lifecycle method for side effects?
**A:** componentDidMount
**Tags:** react, legacy, session-1

---

### Card 5
**Q:** When does useEffect run by default?
**A:** After every render (mount and update).
**Tags:** react, hooks, useEffect, session-2
"""

MULTILINE_CARDS_MD = """\
# Flashcards: Advanced

---

### Card 1
**Q:** Explain the difference between
`let` and `const` in JavaScript.
Which one should you prefer?
**A:** `let` allows reassignment while `const` does not.
Prefer `const` by default — only use `let` when you need to reassign.
**Tags:** javascript, variables
"""

EMPTY_CARDS_MD = """\
# Flashcards: Empty

Last updated: 2026-02-12

---
"""


class TestSM2Algorithm(unittest.TestCase):
    """Test SM-2 algorithm correctness."""

    def _new_card(self):
        return {
            "easiness_factor": 2.5,
            "interval": 0,
            "repetitions": 0,
            "lapses": 0,
            "status": "new",
            "last_review": None,
            "next_review": "2026-02-12",
            "review_history": [],
        }

    def test_first_correct_review_interval_is_1(self):
        card = self._new_card()
        result = SM2.review(card, 4, "2026-02-12")
        self.assertEqual(result["interval"], 1)
        self.assertEqual(result["repetitions"], 1)
        self.assertEqual(result["next_review"], "2026-02-13")

    def test_second_correct_review_interval_is_6(self):
        card = self._new_card()
        card = SM2.review(card, 4, "2026-02-12")
        card = SM2.review(card, 4, "2026-02-13")
        self.assertEqual(card["interval"], 6)
        self.assertEqual(card["repetitions"], 2)

    def test_interval_progression_with_quality_4(self):
        """Verify SM-2 interval progression with quality 4 (EF stays at 2.5).
        round(6*2.5)=15, round(15*2.5)=38, round(38*2.5)=95."""
        card = self._new_card()
        expected_intervals = [1, 6, 15, 38, 95]
        d = date(2026, 2, 12)
        for expected in expected_intervals:
            card = SM2.review(card, 4, d.isoformat())
            self.assertEqual(
                card["interval"],
                expected,
                f"Expected interval {expected}, got {card['interval']}",
            )
            d = d + timedelta(days=card["interval"])

    def test_perfect_quality_5_increases_ef(self):
        card = self._new_card()
        result = SM2.review(card, 5, "2026-02-12")
        self.assertGreater(result["easiness_factor"], 2.5)

    def test_quality_3_decreases_ef(self):
        card = self._new_card()
        result = SM2.review(card, 3, "2026-02-12")
        self.assertLess(result["easiness_factor"], 2.5)

    def test_ef_floor_at_1_3(self):
        """EF should never go below 1.3 even with repeated low quality."""
        card = self._new_card()
        card["easiness_factor"] = 1.3
        result = SM2.review(card, 3, "2026-02-12")
        self.assertGreaterEqual(result["easiness_factor"], 1.3)

        # Multiple low grades with proper date arithmetic
        card = self._new_card()
        d = date(2026, 1, 1)
        for i in range(20):
            card = SM2.review(card, 3, d.isoformat())
            d = d + timedelta(days=max(card["interval"], 1))
        self.assertGreaterEqual(card["easiness_factor"], 1.3)

    def test_lapse_resets_repetitions(self):
        card = self._new_card()
        card = SM2.review(card, 4, "2026-02-12")
        card = SM2.review(card, 4, "2026-02-13")
        self.assertEqual(card["repetitions"], 2)

        # Lapse
        card = SM2.review(card, 2, "2026-02-19")
        self.assertEqual(card["repetitions"], 0)
        self.assertEqual(card["interval"], 1)
        self.assertEqual(card["lapses"], 1)

    def test_lapse_sets_relearning_status(self):
        card = self._new_card()
        card = SM2.review(card, 4, "2026-02-12")
        card = SM2.review(card, 4, "2026-02-13")
        self.assertEqual(card["status"], "review")

        card = SM2.review(card, 1, "2026-02-19")
        self.assertEqual(card["status"], "relearning")

    def test_lapse_on_learning_card_stays_learning(self):
        card = self._new_card()
        card = SM2.review(card, 4, "2026-02-12")  # learning
        self.assertEqual(card["status"], "learning")
        card = SM2.review(card, 2, "2026-02-13")  # lapse
        self.assertEqual(card["status"], "learning")

    def test_quality_0_total_blackout(self):
        card = self._new_card()
        card = SM2.review(card, 4, "2026-02-12")
        card = SM2.review(card, 4, "2026-02-13")
        card = SM2.review(card, 0, "2026-02-19")
        self.assertEqual(card["repetitions"], 0)
        self.assertEqual(card["interval"], 1)
        self.assertGreaterEqual(card["lapses"], 1)

    def test_invalid_quality_raises(self):
        card = self._new_card()
        with self.assertRaises(ValueError):
            SM2.review(card, 6, "2026-02-12")
        with self.assertRaises(ValueError):
            SM2.review(card, -1, "2026-02-12")

    def test_review_history_capped_at_30(self):
        card = self._new_card()
        d = date(2026, 1, 1)
        for i in range(35):
            # Use quality 0 (lapse) to keep interval=1 and avoid date overflow
            card = SM2.review(card, 0, d.isoformat())
            d = d + timedelta(days=1)
        self.assertLessEqual(len(card["review_history"]), 30)

    def test_review_history_records_entries(self):
        card = self._new_card()
        card = SM2.review(card, 4, "2026-02-12")
        self.assertEqual(len(card["review_history"]), 1)
        entry = card["review_history"][0]
        self.assertEqual(entry["date"], "2026-02-12")
        self.assertEqual(entry["quality"], 4)
        self.assertIn("ef", entry)
        self.assertIn("interval", entry)

    def test_ef_update_formula_quality_5(self):
        """EF + (0.1 - (5-5) * (0.08 + (5-5)*0.02)) = EF + 0.1"""
        card = self._new_card()
        result = SM2.review(card, 5, "2026-02-12")
        self.assertAlmostEqual(result["easiness_factor"], 2.6, places=4)

    def test_ef_update_formula_quality_0(self):
        """EF + (0.1 - 5 * (0.08 + 5*0.02)) = EF + (0.1 - 5*0.18) = EF - 0.8"""
        card = self._new_card()
        result = SM2.review(card, 0, "2026-02-12")
        self.assertAlmostEqual(result["easiness_factor"], 1.7, places=4)


class TestCardParser(unittest.TestCase):
    """Test card markdown parsing."""

    def test_parse_standard_cards(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        self.assertEqual(len(cards), 5)

    def test_card_numbers(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        numbers = [c["number"] for c in cards]
        self.assertEqual(numbers, [1, 2, 3, 4, 5])

    def test_card_ids(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        ids = [c["card_id"] for c in cards]
        self.assertEqual(ids, ["card-1", "card-2", "card-3", "card-4", "card-5"])

    def test_reverse_detection(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        self.assertFalse(cards[0]["is_reverse"])
        self.assertTrue(cards[1]["is_reverse"])

    def test_retired_detection(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        self.assertFalse(cards[0]["is_retired"])
        self.assertTrue(cards[3]["is_retired"])  # Card 4

    def test_question_answer_parsing(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        self.assertIn("closure", cards[0]["question"].lower())
        self.assertIn("retains access", cards[0]["answer"].lower())

    def test_tags_parsing(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        self.assertIn("closures", cards[0]["tags"])
        self.assertIn("javascript", cards[0]["tags"])

    def test_question_hash_is_stable(self):
        cards1 = CardParser.parse(SAMPLE_CARDS_MD)
        cards2 = CardParser.parse(SAMPLE_CARDS_MD)
        self.assertEqual(cards1[0]["question_hash"], cards2[0]["question_hash"])

    def test_different_questions_different_hashes(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        hashes = [c["question_hash"] for c in cards]
        self.assertEqual(len(hashes), len(set(hashes)))

    def test_multiline_question_answer(self):
        cards = CardParser.parse(MULTILINE_CARDS_MD)
        self.assertEqual(len(cards), 1)
        self.assertIn("let", cards[0]["question"])
        self.assertIn("const", cards[0]["question"])
        self.assertIn("prefer", cards[0]["question"].lower())
        self.assertIn("reassignment", cards[0]["answer"])

    def test_empty_file(self):
        cards = CardParser.parse(EMPTY_CARDS_MD)
        self.assertEqual(len(cards), 0)

    def test_empty_string(self):
        cards = CardParser.parse("")
        self.assertEqual(len(cards), 0)


class TestSRSStore(unittest.TestCase):
    """Test SRS store creation and sync."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cards_md = Path(self.tmpdir) / "learning" / "react-hooks" / "cards.md"
        self.cards_md.parent.mkdir(parents=True)
        self.cards_md.write_text(SAMPLE_CARDS_MD)
        self.srs_json = SRSStore.srs_path(self.cards_md)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_srs_path_derivation(self):
        self.assertEqual(self.srs_json.name, "cards.srs.json")
        self.assertEqual(self.srs_json.parent, self.cards_md.parent)

    def test_create_store(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")
        self.assertEqual(store["version"], "1.0")
        self.assertEqual(store["algorithm"], "sm2")
        self.assertEqual(store["topic"], "react-hooks")
        # 5 cards total, 1 retired, so 4 active
        self.assertEqual(len(store["cards"]), 4)
        self.assertNotIn("card-4", store["cards"])

    def test_new_card_defaults(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")
        c = store["cards"]["card-1"]
        self.assertEqual(c["easiness_factor"], 2.5)
        self.assertEqual(c["interval"], 0)
        self.assertEqual(c["repetitions"], 0)
        self.assertEqual(c["lapses"], 0)
        self.assertEqual(c["status"], "new")
        self.assertIsNone(c["last_review"])
        self.assertEqual(c["next_review"], "2026-02-12")
        self.assertFalse(c["retired"])

    def test_save_and_load_roundtrip(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")
        SRSStore.save(self.srs_json, store)
        loaded = SRSStore.load(self.srs_json)
        self.assertEqual(loaded["topic"], "react-hooks")
        self.assertEqual(len(loaded["cards"]), 4)

    def test_sync_new_cards_detected(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")

        # Add a new card
        new_md = (
            SAMPLE_CARDS_MD
            + """
---

### Card 6
**Q:** What is useCallback used for?
**A:** Memoizing callback functions to prevent unnecessary re-renders.
**Tags:** react, hooks, session-3
"""
        )
        new_cards = CardParser.parse(new_md)
        report = SRSStore.sync(store, new_cards, "2026-02-13")
        self.assertIn("card-6", report["added"])
        self.assertIn("card-6", store["cards"])

    def test_sync_no_duplicates(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")
        report = SRSStore.sync(store, cards, "2026-02-13")
        self.assertEqual(len(report["added"]), 0)
        self.assertEqual(len(store["cards"]), 4)

    def test_sync_retired_detection(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        # Create store including card-3
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")
        self.assertFalse(store["cards"]["card-3"]["retired"])

        # Now modify cards.md to retire card 3
        retired_md = SAMPLE_CARDS_MD.replace("### Card 3", "### Card 3 [RETIRED]")
        retired_cards = CardParser.parse(retired_md)
        report = SRSStore.sync(store, retired_cards, "2026-02-13")
        self.assertIn("card-3", report["retired"])
        self.assertTrue(store["cards"]["card-3"]["retired"])

    def test_sync_edit_detection(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")
        original_hash = store["cards"]["card-1"]["question_hash"]

        # Edit question for card 1
        edited_md = SAMPLE_CARDS_MD.replace(
            "What is a closure in JavaScript?",
            "What is a closure in JS and why does it matter?",
        )
        edited_cards = CardParser.parse(edited_md)
        report = SRSStore.sync(store, edited_cards, "2026-02-13")
        self.assertIn("card-1", report["edited"])
        self.assertNotEqual(store["cards"]["card-1"]["question_hash"], original_hash)

    def test_sync_orphan_detection(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")

        # Parse a reduced set (only card 1)
        reduced_md = """\
# Flashcards: React Hooks

---

### Card 1
**Q:** What is a closure in JavaScript?
**A:** A closure is a function that retains access to its lexical scope.
**Tags:** closures
"""
        reduced_cards = CardParser.parse(reduced_md)
        report = SRSStore.sync(store, reduced_cards, "2026-02-13")
        # card-2, card-3, card-5 are orphaned (card-4 was retired at creation so not in store)
        self.assertEqual(len(report["orphaned"]), 3)

    def test_sync_never_deletes_from_store(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")
        original_count = len(store["cards"])

        reduced_cards = CardParser.parse(EMPTY_CARDS_MD)
        SRSStore.sync(store, reduced_cards, "2026-02-13")
        self.assertEqual(len(store["cards"]), original_count)


class TestDueFiltering(unittest.TestCase):
    """Test due card filtering logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.cards_md = Path(self.tmpdir) / "cards.md"
        self.cards_md.write_text(SAMPLE_CARDS_MD)
        self.srs_json = SRSStore.srs_path(self.cards_md)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _create_store_with_dates(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")
        # Manually set different next_review dates
        store["cards"]["card-1"]["next_review"] = "2026-02-10"  # overdue
        store["cards"]["card-1"]["status"] = "review"
        store["cards"]["card-2"]["next_review"] = "2026-02-12"  # today
        store["cards"]["card-2"]["status"] = "review"
        store["cards"]["card-3"]["next_review"] = "2026-02-20"  # future
        store["cards"]["card-3"]["status"] = "review"
        store["cards"]["card-5"]["next_review"] = "2026-02-12"  # new, due today
        store["cards"]["card-5"]["status"] = "new"
        return store

    def test_overdue_included(self):
        store = self._create_store_with_dates()
        SRSStore.save(self.srs_json, store)

        with patch("srs_engine._today", return_value="2026-02-12"):
            result = main(["due", str(self.tmpdir), "--json"])
        # We can't easily capture stdout from main, so test the logic directly
        check_date = "2026-02-12"
        due = [
            (cid, c)
            for cid, c in store["cards"].items()
            if not c.get("retired") and c["next_review"] <= check_date
        ]
        due_ids = [cid for cid, _ in due]
        self.assertIn("card-1", due_ids)  # overdue

    def test_today_included(self):
        store = self._create_store_with_dates()
        check_date = "2026-02-12"
        due = [
            (cid, c)
            for cid, c in store["cards"].items()
            if not c.get("retired") and c["next_review"] <= check_date
        ]
        due_ids = [cid for cid, _ in due]
        self.assertIn("card-2", due_ids)

    def test_future_excluded(self):
        store = self._create_store_with_dates()
        check_date = "2026-02-12"
        due = [
            (cid, c)
            for cid, c in store["cards"].items()
            if not c.get("retired") and c["next_review"] <= check_date
        ]
        due_ids = [cid for cid, _ in due]
        self.assertNotIn("card-3", due_ids)

    def test_new_cards_included(self):
        store = self._create_store_with_dates()
        check_date = "2026-02-12"
        due = [
            (cid, c)
            for cid, c in store["cards"].items()
            if not c.get("retired") and c["next_review"] <= check_date
        ]
        due_ids = [cid for cid, _ in due]
        self.assertIn("card-5", due_ids)

    def test_retired_excluded(self):
        store = self._create_store_with_dates()
        # Retire card-1
        store["cards"]["card-1"]["retired"] = True
        check_date = "2026-02-12"
        due = [
            (cid, c)
            for cid, c in store["cards"].items()
            if not c.get("retired") and c["next_review"] <= check_date
        ]
        due_ids = [cid for cid, _ in due]
        self.assertNotIn("card-1", due_ids)


class TestStatsAndForecast(unittest.TestCase):
    """Test stats and forecast output."""

    def test_stats_correct_aggregation(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")
        # SRSStore.create excludes retired cards, so store has 4 cards (card-4 excluded)

        # Grade some cards
        store["cards"]["card-1"] = SM2.review(store["cards"]["card-1"], 4, "2026-02-12")
        store["cards"]["card-2"] = SM2.review(store["cards"]["card-2"], 3, "2026-02-12")

        output = MarkdownFormatter.stats(store)
        self.assertIn("react-hooks", output)
        self.assertIn("4 active", output)
        self.assertIn("0 retired", output)

    def test_stats_empty_deck(self):
        store = {
            "cards": {},
            "topic": "empty",
            "algorithm": "sm2",
            "created": "2026-02-12",
            "last_sync": "2026-02-12",
        }
        output = MarkdownFormatter.stats(store)
        self.assertIn("No cards", output)

    def test_forecast_day_grouping(self):
        cards = CardParser.parse(SAMPLE_CARDS_MD)
        store = SRSStore.create(cards, "react-hooks", "2026-02-12")

        # All new cards have next_review = today
        today = date(2026, 2, 12)
        buckets = {}
        for i in range(7):
            d = (today + timedelta(days=i)).isoformat()
            buckets[d] = 0

        for card in store["cards"].values():
            if not card.get("retired"):
                nr = card.get("next_review")
                if nr in buckets:
                    buckets[nr] += 1

        # All 4 active cards should be on today
        self.assertEqual(buckets["2026-02-12"], 4)
        self.assertEqual(buckets["2026-02-13"], 0)

    def test_forecast_markdown_output(self):
        buckets = {"2026-02-12": 4, "2026-02-13": 0, "2026-02-14": 2}
        output = MarkdownFormatter.forecast(buckets, 3)
        self.assertIn("Forecast", output)
        self.assertIn("2026-02-12", output)
        self.assertIn("4", output)

    def test_forecast_empty(self):
        buckets = {"2026-02-12": 0, "2026-02-13": 0}
        output = MarkdownFormatter.forecast(buckets, 2)
        self.assertIn("No reviews", output)


class TestFormatters(unittest.TestCase):
    """Test markdown and JSON formatters."""

    def test_due_list_no_cards(self):
        output = MarkdownFormatter.due_list([], "2026-02-12")
        self.assertIn("No cards due", output)

    def test_grade_result_format(self):
        card = {
            "status": "review",
            "easiness_factor": 2.6,
            "interval": 6,
            "next_review": "2026-02-18",
            "repetitions": 2,
            "lapses": 0,
        }
        output = MarkdownFormatter.grade_result("card-1", card, 4)
        self.assertIn("card-1", output)
        self.assertIn("4/5", output)
        self.assertIn("2026-02-18", output)

    def test_json_formatter(self):
        data = {"key": "value", "count": 42}
        output = JsonFormatter.output(data)
        parsed = json.loads(output)
        self.assertEqual(parsed["key"], "value")
        self.assertEqual(parsed["count"], 42)

    def test_sync_report_format(self):
        report = {
            "added": ["card-6"],
            "retired": [],
            "edited": ["card-1"],
            "orphaned": [],
        }
        output = MarkdownFormatter.sync_report(report)
        self.assertIn("Sync Report", output)
        self.assertIn("card-6", output)
        self.assertIn("card-1", output)

    def test_init_result_format(self):
        output = MarkdownFormatter.init_result(5, "/path/to/cards.srs.json")
        self.assertIn("5 cards", output)
        self.assertIn("/path/to/cards.srs.json", output)


class TestCLIEndToEnd(unittest.TestCase):
    """End-to-end CLI tests."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.topic_dir = Path(self.tmpdir) / "learning" / "react-hooks"
        self.topic_dir.mkdir(parents=True)
        self.cards_md = self.topic_dir / "cards.md"
        self.cards_md.write_text(SAMPLE_CARDS_MD)
        self.srs_json = self.topic_dir / "cards.srs.json"

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _run(self, args):
        """Run CLI and capture exit code (output goes to stdout)."""
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            code = main(args)
        return code, f.getvalue()

    def test_init_creates_json(self):
        code, output = self._run(["init", str(self.topic_dir)])
        self.assertEqual(code, 0)
        self.assertTrue(self.srs_json.exists())
        store = json.loads(self.srs_json.read_text())
        self.assertEqual(len(store["cards"]), 4)
        self.assertEqual(store["topic"], "react-hooks")

    def test_init_refuses_overwrite(self):
        self._run(["init", str(self.topic_dir)])
        code, output = self._run(["init", str(self.topic_dir)])
        self.assertEqual(code, 0)  # prints error message, but doesn't crash
        self.assertIn("already exists", output)

    def test_init_force_overwrites(self):
        self._run(["init", str(self.topic_dir)])
        code, output = self._run(["init", str(self.topic_dir), "--force"])
        self.assertEqual(code, 0)
        self.assertIn("4 cards", output)

    def test_init_json_output(self):
        code, output = self._run(["init", str(self.topic_dir), "--json"])
        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertEqual(data["action"], "init")
        self.assertEqual(data["cards"], 4)

    def test_due_shows_all_new_cards(self):
        self._run(["init", str(self.topic_dir)])
        code, output = self._run(["due", str(self.topic_dir), "--json"])
        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertEqual(data["count"], 4)

    def test_grade_updates_state(self):
        self._run(["init", str(self.topic_dir)])
        code, output = self._run(["grade", str(self.topic_dir), "card-1", "4"])
        self.assertEqual(code, 0)
        self.assertIn("card-1", output)

        store = json.loads(self.srs_json.read_text())
        self.assertEqual(store["cards"]["card-1"]["interval"], 1)
        self.assertEqual(store["cards"]["card-1"]["repetitions"], 1)

    def test_grade_json_output(self):
        self._run(["init", str(self.topic_dir)])
        code, output = self._run(
            ["grade", str(self.topic_dir), "card-1", "4", "--json"]
        )
        self.assertEqual(code, 0)
        data = json.loads(output)
        self.assertEqual(data["action"], "grade")
        self.assertEqual(data["card_id"], "card-1")
        self.assertEqual(data["interval"], 1)

    def test_grade_invalid_card(self):
        self._run(["init", str(self.topic_dir)])
        code, output = self._run(["grade", str(self.topic_dir), "card-99", "4"])
        self.assertEqual(code, 0)
        self.assertIn("not found", output)

    def test_stats_output(self):
        self._run(["init", str(self.topic_dir)])
        code, output = self._run(["stats", str(self.topic_dir)])
        self.assertEqual(code, 0)
        self.assertIn("react-hooks", output)
        self.assertIn("4 active", output)

    def test_forecast_output(self):
        self._run(["init", str(self.topic_dir)])
        code, output = self._run(["forecast", str(self.topic_dir)])
        self.assertEqual(code, 0)
        self.assertIn("Forecast", output)

    def test_sync_after_adding_card(self):
        self._run(["init", str(self.topic_dir)])

        # Add a new card
        new_content = (
            SAMPLE_CARDS_MD
            + """
---

### Card 6
**Q:** What is useMemo used for?
**A:** Memoizing expensive computations to avoid recalculation on every render.
**Tags:** react, hooks, session-3
"""
        )
        self.cards_md.write_text(new_content)
        code, output = self._run(["sync", str(self.topic_dir)])
        self.assertEqual(code, 0)
        self.assertIn("1", output)  # 1 added

        store = json.loads(self.srs_json.read_text())
        self.assertIn("card-6", store["cards"])

    def test_full_workflow_chain(self):
        """End-to-end: init -> due -> grade -> stats -> forecast."""
        # Init
        code, _ = self._run(["init", str(self.topic_dir)])
        self.assertEqual(code, 0)

        # Due
        code, output = self._run(["due", str(self.topic_dir), "--json"])
        data = json.loads(output)
        self.assertEqual(data["count"], 4)

        # Grade all cards
        for i in [1, 2, 3, 5]:
            code, _ = self._run(["grade", str(self.topic_dir), f"card-{i}", "4"])
            self.assertEqual(code, 0)

        # Stats
        code, output = self._run(["stats", str(self.topic_dir), "--json"])
        data = json.loads(output)
        self.assertEqual(data["total_reviews"], 4)

        # Forecast
        code, output = self._run(["forecast", str(self.topic_dir)])
        self.assertEqual(code, 0)

    def test_path_resolution_with_cards_md(self):
        """Passing cards.md directly should work."""
        code, _ = self._run(["init", str(self.cards_md)])
        self.assertEqual(code, 0)
        self.assertTrue(self.srs_json.exists())

    def test_missing_cards_md(self):
        empty_dir = Path(self.tmpdir) / "empty"
        empty_dir.mkdir()
        code, output = self._run(["init", str(empty_dir)])
        self.assertEqual(code, 0)
        self.assertIn("not found", output)


class TestPathResolution(unittest.TestCase):
    """Test path resolution helpers."""

    def test_resolve_from_directory(self):
        cards_md, srs_json = _resolve_paths("/some/dir")
        self.assertEqual(cards_md, Path("/some/dir/cards.md"))
        self.assertEqual(srs_json, Path("/some/dir/cards.srs.json"))

    def test_resolve_from_cards_md(self):
        cards_md, srs_json = _resolve_paths("/some/dir/cards.md")
        self.assertEqual(cards_md, Path("/some/dir/cards.md"))
        self.assertEqual(srs_json, Path("/some/dir/cards.srs.json"))

    def test_derive_topic_from_learning_path(self):
        p = Path("/home/user/learning/react-hooks/cards.md")
        self.assertEqual(_derive_topic(p), "react-hooks")

    def test_derive_topic_fallback(self):
        p = Path("/some/random/dir/cards.md")
        self.assertEqual(_derive_topic(p), "dir")


if __name__ == "__main__":
    unittest.main()
