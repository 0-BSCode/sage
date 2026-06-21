#!/usr/bin/env python3
"""Tests for the Assessment Engine.

Covers: AdaptiveSelector, QuestionBank, KnowledgeMapReader, CLI end-to-end.
Run: python3 -m pytest tools/assessment/test_assessment_engine.py -v
  or: python3 -m unittest tools/assessment/test_assessment_engine.py -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure the assessment engine module is importable
sys.path.insert(0, str(Path(__file__).parent))
from assessment_engine import (
    AdaptiveSelector,
    KnowledgeMapReader,
    MarkdownFormatter,
    QuestionBank,
    MASTERY_TO_BASE_DIFFICULTY,
    MASTERY_TO_TYPES,
    MASTERY_ORDER,
    QUESTION_TYPES,
)

ENGINE_PATH = str(Path(__file__).parent / "assessment_engine.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_KNOWLEDGE_MAP = """\
# Knowledge Map

| Concept | Status | Last Tested | Notes |
|---------|--------|-------------|-------|
| closures | developing | 2026-02-10 | Needs more practice |
| useState | solid | 2026-02-11 | Good understanding |
| useEffect | introduced | 2026-02-08 | Just started |
| useRef | not started | — | Not yet covered |
| useMemo | mastered | 2026-02-12 | Strong |
"""


def make_topic_dir(tmpdir: str, with_km: bool = True, km_text: str = SAMPLE_KNOWLEDGE_MAP) -> Path:
    """Create a learning/<topic>/ directory structure."""
    topic_dir = Path(tmpdir) / "learning" / "test-topic"
    topic_dir.mkdir(parents=True, exist_ok=True)
    if with_km:
        (topic_dir / "knowledge-map.md").write_text(km_text)
    return topic_dir


def make_bank_with_questions(topic_dir: Path, questions: list, today: str = "2026-02-12") -> dict:
    """Create a bank with pre-populated questions."""
    km = KnowledgeMapReader.read_from_path(topic_dir)
    bank = QuestionBank.create("test-topic", km, today)
    for q in questions:
        QuestionBank.add_question(
            bank, q["concept"], q["difficulty"], q["question_type"],
            q.get("question_text", f"Test question about {q['concept']}"),
            q.get("expected_answer_summary", "Expected answer"),
            q.get("tags"), today
        )
    QuestionBank.save(QuestionBank.bank_path(topic_dir), bank)
    return bank


# ---------------------------------------------------------------------------
# TestKnowledgeMapReader
# ---------------------------------------------------------------------------

class TestKnowledgeMapReader(unittest.TestCase):

    def test_parse_standard_table(self):
        concepts = KnowledgeMapReader.parse(SAMPLE_KNOWLEDGE_MAP)
        self.assertEqual(len(concepts), 5)
        self.assertIn("closures", concepts)
        self.assertEqual(concepts["closures"]["status"], "developing")
        self.assertEqual(concepts["useState"]["status"], "solid")

    def test_parse_all_status_levels(self):
        concepts = KnowledgeMapReader.parse(SAMPLE_KNOWLEDGE_MAP)
        statuses = {c["status"] for c in concepts.values()}
        self.assertEqual(statuses, {"developing", "solid", "introduced", "not started", "mastered"})

    def test_parse_empty_map(self):
        text = "# Knowledge Map\n\nNo concepts yet.\n"
        concepts = KnowledgeMapReader.parse(text)
        self.assertEqual(concepts, {})

    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "nonexistent"
            concepts = KnowledgeMapReader.read_from_path(p)
            self.assertEqual(concepts, {})

    def test_parse_ignores_header_and_separator(self):
        text = """\
| Concept | Status | Last Tested | Notes |
|---------|--------|-------------|-------|
| foo | developing | 2026-01-01 | test |
"""
        concepts = KnowledgeMapReader.parse(text)
        self.assertEqual(len(concepts), 1)
        self.assertIn("foo", concepts)

    def test_parse_ignores_invalid_status(self):
        text = """\
| Concept | Status | Last Tested | Notes |
|---------|--------|-------------|-------|
| foo | invalid_status | 2026-01-01 | test |
| bar | solid | 2026-01-01 | test |
"""
        concepts = KnowledgeMapReader.parse(text)
        self.assertEqual(len(concepts), 1)
        self.assertIn("bar", concepts)


# ---------------------------------------------------------------------------
# TestQuestionBank
# ---------------------------------------------------------------------------

class TestQuestionBank(unittest.TestCase):

    def test_create_empty_bank(self):
        bank = QuestionBank.create("test-topic", {"foo": {"status": "introduced"}}, "2026-02-12")
        self.assertEqual(bank["version"], "1.0")
        self.assertEqual(bank["topic"], "test-topic")
        self.assertEqual(bank["questions"], {})
        self.assertIn("foo", bank["coverage"])
        self.assertEqual(bank["coverage"]["foo"]["total_questions"], 0)

    def test_add_question_assigns_sequential_id(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        qid1 = QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q1?", "A1")
        qid2 = QuestionBank.add_question(bank, "foo", 3, "application", "Q2?", "A2")
        qid3 = QuestionBank.add_question(bank, "bar", 1, "free_recall", "Q3?", "A3")
        self.assertEqual(qid1, "q-1")
        self.assertEqual(qid2, "q-2")
        self.assertEqual(qid3, "q-3")

    def test_add_question_populates_fields(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        QuestionBank.add_question(bank, "closures", 3, "application",
                                  "Explain closures", "A closure captures...",
                                  ["js", "closures"], "2026-02-12")
        q = bank["questions"]["q-1"]
        self.assertEqual(q["concept"], "closures")
        self.assertEqual(q["difficulty"], 3)
        self.assertEqual(q["question_type"], "application")
        self.assertEqual(q["question_text"], "Explain closures")
        self.assertEqual(q["times_asked"], 0)
        self.assertEqual(q["success_rate"], 0.0)
        self.assertFalse(q["retired"])
        self.assertEqual(q["tags"], ["js", "closures"])

    def test_add_batch_multiple_questions(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        for i in range(5):
            QuestionBank.add_question(bank, "concept", i % 5 + 1, "free_recall",
                                      f"Q{i}?", f"A{i}")
        self.assertEqual(len(bank["questions"]), 5)
        self.assertIn("q-5", bank["questions"])

    def test_record_result_updates_stats(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q?", "A")
        QuestionBank.record_result(bank, "q-1", 1, session=1, quality="strong",
                                   notes="Good", today="2026-02-12")
        q = bank["questions"]["q-1"]
        self.assertEqual(q["times_asked"], 1)
        self.assertEqual(q["times_correct"], 1)
        self.assertEqual(q["success_rate"], 1.0)
        self.assertEqual(q["last_asked"], "2026-02-12")

    def test_record_result_updates_success_rate(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q?", "A")
        QuestionBank.record_result(bank, "q-1", 1, today="2026-02-12")
        QuestionBank.record_result(bank, "q-1", 0, today="2026-02-13")
        q = bank["questions"]["q-1"]
        self.assertEqual(q["times_asked"], 2)
        self.assertEqual(q["times_correct"], 1)
        self.assertAlmostEqual(q["success_rate"], 0.5, places=2)

    def test_record_result_appends_history(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q?", "A")
        QuestionBank.record_result(bank, "q-1", 1, session=1, quality="strong",
                                   notes="Nailed it", today="2026-02-12")
        QuestionBank.record_result(bank, "q-1", 0, session=2, quality="wrong",
                                   notes="Missed it", today="2026-02-13")
        q = bank["questions"]["q-1"]
        self.assertEqual(len(q["result_history"]), 2)
        self.assertEqual(q["result_history"][0]["score"], 1)
        self.assertEqual(q["result_history"][1]["score"], 0)

    def test_result_history_capped_at_30(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q?", "A")
        for i in range(35):
            QuestionBank.record_result(bank, "q-1", i % 2, today="2026-02-12")
        q = bank["questions"]["q-1"]
        self.assertEqual(len(q["result_history"]), 30)

    def test_coverage_tracking_updated_on_add(self):
        bank = QuestionBank.create("test", {"foo": {"status": "introduced"}}, "2026-02-12")
        QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q?", "A")
        QuestionBank.add_question(bank, "foo", 3, "application", "Q2?", "A2")
        cov = bank["coverage"]["foo"]
        self.assertEqual(cov["total_questions"], 2)
        self.assertEqual(cov["questions_by_difficulty"], {"2": 1, "3": 1})
        self.assertEqual(cov["questions_by_type"], {"conceptual": 1, "application": 1})

    def test_coverage_tracking_updated_on_record(self):
        bank = QuestionBank.create("test", {"foo": {"status": "introduced"}}, "2026-02-12")
        QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q?", "A")
        QuestionBank.record_result(bank, "q-1", 1, today="2026-02-12")
        cov = bank["coverage"]["foo"]
        self.assertEqual(cov["last_assessed"], "2026-02-12")
        self.assertEqual(cov["assessment_count"], 1)

    def test_coverage_auto_created_for_new_concept(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        QuestionBank.add_question(bank, "new_concept", 1, "free_recall", "Q?", "A")
        self.assertIn("new_concept", bank["coverage"])
        self.assertEqual(bank["coverage"]["new_concept"]["total_questions"], 1)

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            bank = QuestionBank.create("test-topic", {"foo": {"status": "introduced"}}, "2026-02-12")
            QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q?", "A", today="2026-02-12")
            bp = QuestionBank.bank_path(topic_dir)
            QuestionBank.save(bp, bank)
            loaded = QuestionBank.load(bp)
            self.assertEqual(loaded["questions"]["q-1"]["question_text"], "Q?")
            self.assertEqual(loaded["coverage"]["foo"]["total_questions"], 1)

    def test_next_id_empty_bank(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        self.assertEqual(QuestionBank.next_id(bank), "q-1")

    def test_next_id_after_adds(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        QuestionBank.add_question(bank, "a", 1, "free_recall", "Q1?", "A1")
        QuestionBank.add_question(bank, "b", 2, "conceptual", "Q2?", "A2")
        self.assertEqual(QuestionBank.next_id(bank), "q-3")

    def test_calibrate_from_results(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        # Add questions at different difficulties
        QuestionBank.add_question(bank, "easy", 1, "free_recall", "Q1?", "A1")
        QuestionBank.add_question(bank, "hard", 4, "analysis", "Q2?", "A2")
        # Easy one: correct. Hard one: incorrect.
        QuestionBank.record_result(bank, "q-1", 1, today="2026-02-12")
        QuestionBank.record_result(bank, "q-2", 0, today="2026-02-12")
        level = QuestionBank.calibrate(bank)
        # Easy correct (d=1, weight=1, contributes 1*1=1), hard incorrect (d=4, weight=4, contributes 0)
        # total_weighted=1, total_weight=1+16=17... wait, let me re-check the algorithm
        # weight = difficulty, if correct: total_weighted += difficulty * weight = d^2
        # q-1: d=1, correct => weighted += 1*1=1, weight += 1
        # q-2: d=4, incorrect => weighted += 0, weight += 4
        # level = 1/5 = 0.2 -> clamped to 1.0
        self.assertEqual(level, 1.0)

    def test_calibrate_all_correct_high_difficulty(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        QuestionBank.add_question(bank, "hard", 5, "transfer", "Q?", "A")
        QuestionBank.record_result(bank, "q-1", 1, today="2026-02-12")
        level = QuestionBank.calibrate(bank)
        # d=5, correct => weighted += 25, weight += 5 => 25/5 = 5.0
        self.assertEqual(level, 5.0)

    def test_calibrate_no_results(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q?", "A")
        level = QuestionBank.calibrate(bank)
        self.assertEqual(level, 3.0)  # default when no results


# ---------------------------------------------------------------------------
# TestAdaptiveSelector
# ---------------------------------------------------------------------------

class TestAdaptiveSelector(unittest.TestCase):

    def _make_bank_and_km(self, tmpdir):
        topic_dir = make_topic_dir(tmpdir)
        km = KnowledgeMapReader.read_from_path(topic_dir)
        bank = QuestionBank.create("test-topic", km, "2026-02-12")
        return bank, km, topic_dir

    def test_concept_priority_never_assessed_gets_max_recency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            # useRef has never been assessed and has no questions
            priority = AdaptiveSelector.concept_priority("useRef", bank, "not started", "2026-02-12")
            # recency=5.0 (never assessed) + weakness=0.0 (no questions) + coverage=2.0 (< 3 questions)
            self.assertAlmostEqual(priority, 7.0, places=1)

    def test_concept_priority_recent_assessment_gets_low_recency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            # Manually set last_assessed to today
            bank["coverage"]["useState"] = {
                "total_questions": 5,
                "questions_by_difficulty": {},
                "questions_by_type": {},
                "last_assessed": "2026-02-12",
                "assessment_count": 3,
            }
            priority = AdaptiveSelector.concept_priority("useState", bank, "solid", "2026-02-12")
            # recency=0.0 (assessed today) + weakness=0.0 (no asked questions) + coverage=0.0 (>=5)
            self.assertAlmostEqual(priority, 0.0, places=1)

    def test_weakness_weight_low_success_rate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, topic_dir = self._make_bank_and_km(tmpdir)
            # Add a question for closures with low success
            QuestionBank.add_question(bank, "closures", 2, "conceptual", "Q?", "A", today="2026-02-12")
            QuestionBank.record_result(bank, "q-1", 0, today="2026-02-12")
            QuestionBank.record_result(bank, "q-1", 0, today="2026-02-12")
            # success_rate = 0.0 < 0.5 => weakness_weight = 3.0
            priority = AdaptiveSelector.concept_priority("closures", bank, "developing", "2026-02-12")
            # recency from coverage last_assessed = today => 0/7=0.0
            # weakness = 3.0 (avg success 0.0 < 0.5)
            # coverage: total_questions for closures = 1 => coverage_weight = 2.0
            # Actually, coverage uses the coverage dict, not question count
            self.assertGreaterEqual(priority, 3.0)  # weakness alone is 3.0

    def test_weakness_weight_high_success_rate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            QuestionBank.add_question(bank, "useState", 3, "application", "Q?", "A", today="2026-02-12")
            QuestionBank.record_result(bank, "q-1", 1, today="2026-02-12")
            QuestionBank.record_result(bank, "q-1", 1, today="2026-02-12")
            QuestionBank.record_result(bank, "q-1", 1, today="2026-02-12")
            priority = AdaptiveSelector.concept_priority("useState", bank, "solid", "2026-02-12")
            # success_rate = 1.0 >= 0.7 => weakness = 0.0
            # Check weakness doesn't contribute
            # recency depends on coverage last_assessed
            cov_priority = priority  # just check weakness is 0
            self.assertLess(cov_priority, 7.0)  # should be much less than never-assessed

    def test_coverage_weight_few_questions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            # useEffect has 0 questions => coverage_weight = 2.0
            p1 = AdaptiveSelector.concept_priority("useEffect", bank, "introduced", "2026-02-12")
            # Add 3 questions
            for i in range(3):
                QuestionBank.add_question(bank, "useEffect", 1, "free_recall",
                                          f"Q{i}?", f"A{i}", today="2026-02-12")
            p2 = AdaptiveSelector.concept_priority("useEffect", bank, "introduced", "2026-02-12")
            # After 3 questions, coverage_weight drops from 2.0 to 1.0
            self.assertGreater(p1, p2)

    def test_difficulty_from_mastery_status_mapping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            for mastery, expected_base in MASTERY_TO_BASE_DIFFICULTY.items():
                diff = AdaptiveSelector.target_difficulty("test", bank, mastery)
                self.assertEqual(diff, expected_base,
                                 f"Mastery '{mastery}' should give difficulty {expected_base}")

    def test_difficulty_adjustment_all_correct_increases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            QuestionBank.add_question(bank, "closures", 2, "conceptual", "Q?", "A", today="2026-02-10")
            QuestionBank.record_result(bank, "q-1", 1, today="2026-02-10")
            QuestionBank.record_result(bank, "q-1", 1, today="2026-02-11")
            QuestionBank.record_result(bank, "q-1", 1, today="2026-02-12")
            # developing base=2, all 3 correct => +1 = 3
            diff = AdaptiveSelector.target_difficulty("closures", bank, "developing")
            self.assertEqual(diff, 3)

    def test_difficulty_adjustment_all_wrong_decreases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            QuestionBank.add_question(bank, "closures", 2, "conceptual", "Q?", "A", today="2026-02-10")
            QuestionBank.record_result(bank, "q-1", 0, today="2026-02-10")
            QuestionBank.record_result(bank, "q-1", 0, today="2026-02-11")
            QuestionBank.record_result(bank, "q-1", 0, today="2026-02-12")
            # developing base=2, all 3 wrong => -1 = 1
            diff = AdaptiveSelector.target_difficulty("closures", bank, "developing")
            self.assertEqual(diff, 1)

    def test_difficulty_clamped_to_1_5_range(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            # not_started base=1, all wrong => 1-1=0 => clamped to 1
            QuestionBank.add_question(bank, "useRef", 1, "free_recall", "Q?", "A", today="2026-02-10")
            QuestionBank.record_result(bank, "q-1", 0, today="2026-02-10")
            QuestionBank.record_result(bank, "q-1", 0, today="2026-02-11")
            QuestionBank.record_result(bank, "q-1", 0, today="2026-02-12")
            diff = AdaptiveSelector.target_difficulty("useRef", bank, "not started")
            self.assertEqual(diff, 1)  # clamped at 1, not 0

            # mastered base=4, all correct => 4+1=5 => at max
            QuestionBank.add_question(bank, "useMemo", 4, "transfer", "Q2?", "A2", today="2026-02-10")
            QuestionBank.record_result(bank, "q-2", 1, today="2026-02-10")
            QuestionBank.record_result(bank, "q-2", 1, today="2026-02-11")
            QuestionBank.record_result(bank, "q-2", 1, today="2026-02-12")
            diff = AdaptiveSelector.target_difficulty("useMemo", bank, "mastered")
            self.assertEqual(diff, 5)

    def test_question_type_matches_mastery_level(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            for mastery, valid_types in MASTERY_TO_TYPES.items():
                qtype = AdaptiveSelector.select_question_type(mastery, bank, "test_concept")
                self.assertIn(qtype, valid_types,
                              f"Type '{qtype}' not valid for mastery '{mastery}'")

    def test_prefer_unasked_questions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            # Add two questions for closures, ask one
            QuestionBank.add_question(bank, "closures", 2, "conceptual",
                                      "Asked question", "A1", today="2026-02-10")
            QuestionBank.add_question(bank, "closures", 2, "conceptual",
                                      "Unasked question", "A2", today="2026-02-10")
            QuestionBank.record_result(bank, "q-1", 1, today="2026-02-11")

            result = AdaptiveSelector.select_from_bank(bank, "closures", 2, "conceptual", "2026-02-12")
            self.assertIsNotNone(result)
            self.assertEqual(result["question_id"], "q-2")  # prefer unasked

    def test_prefer_oldest_asked_questions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            # Two questions, both asked, but at different times
            QuestionBank.add_question(bank, "closures", 2, "conceptual",
                                      "Old question", "A1", today="2026-02-10")
            QuestionBank.add_question(bank, "closures", 2, "conceptual",
                                      "New question", "A2", today="2026-02-10")
            QuestionBank.record_result(bank, "q-1", 1, today="2026-02-01")
            QuestionBank.record_result(bank, "q-2", 1, today="2026-02-11")

            result = AdaptiveSelector.select_from_bank(bank, "closures", 2, "conceptual", "2026-02-12")
            self.assertIsNotNone(result)
            self.assertEqual(result["question_id"], "q-1")  # older last_asked

    def test_generate_recommendation_when_bank_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            recs = AdaptiveSelector.select(bank, km, "2026-02-12", count=1)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["action"], "generate")  # no questions in bank

    def test_generate_recommendation_when_no_matching_difficulty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            # Add a question at difficulty 5 for an introduced concept (target difficulty = 1)
            QuestionBank.add_question(bank, "useEffect", 5, "free_recall",
                                      "Expert question", "A", today="2026-02-10")
            recs = AdaptiveSelector.select(bank, km, "2026-02-12", count=1,
                                           filter_concept="useEffect")
            self.assertEqual(len(recs), 1)
            # Difficulty 5 is too far from target 1 (diff > 1), so generate
            self.assertEqual(recs[0]["action"], "generate")

    def test_select_returns_ask_for_matching_question(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            # useEffect is introduced => target difficulty 1, valid types: free_recall, conceptual
            # Add both types so whichever the selector picks, there's a match
            QuestionBank.add_question(bank, "useEffect", 1, "free_recall",
                                      "Explain useEffect", "useEffect runs...",
                                      today="2026-02-10")
            QuestionBank.add_question(bank, "useEffect", 1, "conceptual",
                                      "Why does useEffect run after render?",
                                      "React defers side effects...",
                                      today="2026-02-10")
            recs = AdaptiveSelector.select(bank, km, "2026-02-12", count=1,
                                           filter_concept="useEffect")
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["action"], "ask")

    def test_select_multiple_distributes_across_concepts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            recs = AdaptiveSelector.select(bank, km, "2026-02-12", count=3)
            self.assertEqual(len(recs), 3)
            concepts = [r["concept"] for r in recs]
            # Should pick different concepts (all are generate since bank is empty)
            self.assertEqual(len(set(concepts)), 3)

    def test_select_with_concept_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            recs = AdaptiveSelector.select(bank, km, "2026-02-12", count=2,
                                           filter_concept="closures")
            # With filter, all recs should be for closures
            for r in recs:
                self.assertEqual(r["concept"], "closures")

    def test_select_empty_knowledge_map(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bank = QuestionBank.create("test", {}, "2026-02-12")
            recs = AdaptiveSelector.select(bank, {}, "2026-02-12", count=3)
            self.assertEqual(recs, [])

    def test_select_min_mastery_excludes_below_threshold(self):
        """--min-mastery developing should exclude 'not started' and 'introduced'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            # km has: closures=developing, useState=solid, useEffect=introduced,
            #         useRef=not started, useMemo=mastered
            recs = AdaptiveSelector.select(bank, km, "2026-02-12", count=5,
                                           min_mastery="developing")
            selected_concepts = {r["concept"] for r in recs}
            # Should only include developing, solid, mastered
            self.assertTrue(selected_concepts <= {"closures", "useState", "useMemo"})
            self.assertNotIn("useRef", selected_concepts)
            self.assertNotIn("useEffect", selected_concepts)

    def test_select_min_mastery_all_below_returns_empty(self):
        """--min-mastery with only below-threshold concepts returns empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            km = {"concept_a": {"status": "not started"},
                  "concept_b": {"status": "introduced"}}
            bank = QuestionBank.create("test", km, "2026-02-12")
            recs = AdaptiveSelector.select(bank, km, "2026-02-12", count=3,
                                           min_mastery="developing")
            self.assertEqual(recs, [])

    def test_select_without_min_mastery_includes_all(self):
        """select without --min-mastery should behave as before (no regression)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            recs = AdaptiveSelector.select(bank, km, "2026-02-12", count=5)
            selected_concepts = {r["concept"] for r in recs}
            # Should include all 5 concepts
            self.assertEqual(len(selected_concepts), 5)

    def test_select_min_mastery_introduced_only_excludes_not_started(self):
        """--min-mastery introduced should only exclude 'not started'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bank, km, _ = self._make_bank_and_km(tmpdir)
            recs = AdaptiveSelector.select(bank, km, "2026-02-12", count=5,
                                           min_mastery="introduced")
            selected_concepts = {r["concept"] for r in recs}
            self.assertNotIn("useRef", selected_concepts)  # not started
            self.assertIn("useEffect", selected_concepts)  # introduced


# ---------------------------------------------------------------------------
# TestFormatters
# ---------------------------------------------------------------------------

class TestFormatters(unittest.TestCase):

    def test_coverage_format(self):
        bank = QuestionBank.create("test", {"foo": {"status": "introduced"}}, "2026-02-12")
        QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q?", "A", today="2026-02-12")
        output = MarkdownFormatter.coverage(bank)
        self.assertIn("Assessment Coverage", output)
        self.assertIn("foo", output)
        self.assertIn("1", output)  # 1 question

    def test_stats_format(self):
        bank = QuestionBank.create("test", {}, "2026-02-12")
        QuestionBank.add_question(bank, "foo", 2, "conceptual", "Q?", "A", today="2026-02-12")
        QuestionBank.record_result(bank, "q-1", 1, today="2026-02-12")
        output = MarkdownFormatter.stats(bank)
        self.assertIn("Assessment Statistics", output)
        self.assertIn("1", output)

    def test_select_list_empty(self):
        output = MarkdownFormatter.select_list([])
        self.assertIn("No questions", output)

    def test_select_list_with_ask_and_generate(self):
        recs = [
            {"action": "ask", "question_id": "q-1", "concept": "foo",
             "difficulty": 2, "question_type": "conceptual",
             "question_text": "What is foo?", "expected_answer_summary": "Foo is..."},
            {"action": "generate", "concept": "bar", "difficulty": 3,
             "question_type": "application"},
        ]
        output = MarkdownFormatter.select_list(recs)
        self.assertIn("q-1", output)
        self.assertIn("GENERATE", output)
        self.assertIn("bar", output)


# ---------------------------------------------------------------------------
# TestCLIEndToEnd
# ---------------------------------------------------------------------------

class TestCLIEndToEnd(unittest.TestCase):

    def _run_cmd(self, args: list, stdin_data: str = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, ENGINE_PATH] + args,
            capture_output=True, text=True,
            input=stdin_data,
        )

    def test_init_creates_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            result = self._run_cmd(["init", str(topic_dir)])
            self.assertEqual(result.returncode, 0)
            self.assertTrue((topic_dir / "questions.json").exists())
            self.assertIn("Initialized", result.stdout)

    def test_init_reads_knowledge_map_concepts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            result = self._run_cmd(["init", str(topic_dir), "--json"])
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["concepts"], 5)  # 5 concepts in sample km

    def test_init_refuses_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            result = self._run_cmd(["init", str(topic_dir)])
            self.assertIn("already exists", result.stdout)

    def test_init_with_force_overwrites(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            result = self._run_cmd(["init", str(topic_dir), "--force"])
            self.assertEqual(result.returncode, 0)
            self.assertIn("Initialized", result.stdout)

    def test_add_persists_question(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            result = self._run_cmd([
                "add", str(topic_dir),
                "--concept", "closures",
                "--difficulty", "2",
                "--type", "conceptual",
                "--text", "What is a closure?",
                "--answer", "A closure captures variables from its enclosing scope.",
            ])
            self.assertEqual(result.returncode, 0)
            self.assertIn("q-1", result.stdout)

            # Verify it's in the bank
            bank = QuestionBank.load(QuestionBank.bank_path(topic_dir))
            self.assertIn("q-1", bank["questions"])

    def test_add_with_json_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            result = self._run_cmd([
                "add", str(topic_dir),
                "--concept", "closures",
                "--difficulty", "2",
                "--type", "conceptual",
                "--text", "What is a closure?",
                "--answer", "A closure captures...",
                "--json",
            ])
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["question_id"], "q-1")

    def test_add_batch_from_stdin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            batch = json.dumps([
                {"concept": "closures", "difficulty": 2, "question_type": "conceptual",
                 "question_text": "Q1?", "expected_answer_summary": "A1"},
                {"concept": "useState", "difficulty": 3, "question_type": "application",
                 "question_text": "Q2?", "expected_answer_summary": "A2"},
            ])
            result = self._run_cmd(["add-batch", str(topic_dir), "--json"], stdin_data=batch)
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["count"], 2)

    def test_select_returns_recommendations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            result = self._run_cmd(["select", str(topic_dir), "--count", "2", "--json"])
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["count"], 2)
            self.assertEqual(len(data["recommendations"]), 2)

    def test_select_with_concept_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            result = self._run_cmd(["select", str(topic_dir), "--concept", "closures", "--json"])
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            for r in data["recommendations"]:
                self.assertEqual(r["concept"], "closures")

    def test_select_with_min_mastery_cli(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            result = self._run_cmd([
                "select", str(topic_dir),
                "--min-mastery", "developing", "--count", "5", "--json",
            ])
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            for r in data["recommendations"]:
                # Should only have developing, solid, or mastered concepts
                self.assertIn(r["concept"], ["closures", "useState", "useMemo"])

    def test_record_updates_bank(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            self._run_cmd([
                "add", str(topic_dir),
                "--concept", "closures", "--difficulty", "2",
                "--type", "conceptual", "--text", "Q?", "--answer", "A",
            ])
            result = self._run_cmd([
                "record", str(topic_dir), "q-1", "1",
                "--session", "1", "--quality", "strong", "--notes", "Nailed it",
            ])
            self.assertEqual(result.returncode, 0)
            self.assertIn("correct", result.stdout)

            bank = QuestionBank.load(QuestionBank.bank_path(topic_dir))
            self.assertEqual(bank["questions"]["q-1"]["times_asked"], 1)
            self.assertEqual(bank["questions"]["q-1"]["times_correct"], 1)

    def test_record_with_json_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            self._run_cmd([
                "add", str(topic_dir),
                "--concept", "closures", "--difficulty", "2",
                "--type", "conceptual", "--text", "Q?", "--answer", "A",
            ])
            result = self._run_cmd([
                "record", str(topic_dir), "q-1", "0",
                "--quality", "wrong", "--json",
            ])
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertEqual(data["score"], 0)
            self.assertEqual(data["quality"], "wrong")

    def test_coverage_report_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            self._run_cmd([
                "add", str(topic_dir),
                "--concept", "closures", "--difficulty", "2",
                "--type", "conceptual", "--text", "Q?", "--answer", "A",
            ])
            result = self._run_cmd(["coverage", str(topic_dir)])
            self.assertEqual(result.returncode, 0)
            self.assertIn("Coverage", result.stdout)
            self.assertIn("closures", result.stdout)

    def test_stats_report_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            result = self._run_cmd(["stats", str(topic_dir)])
            self.assertEqual(result.returncode, 0)
            self.assertIn("Statistics", result.stdout)

    def test_calibrate_recomputes_level(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            self._run_cmd([
                "add", str(topic_dir),
                "--concept", "closures", "--difficulty", "3",
                "--type", "application", "--text", "Q?", "--answer", "A",
            ])
            self._run_cmd(["record", str(topic_dir), "q-1", "1", "--quality", "strong"])
            result = self._run_cmd(["calibrate", str(topic_dir)])
            self.assertEqual(result.returncode, 0)
            self.assertIn("level", result.stdout)

    def test_calibrate_json_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            self._run_cmd([
                "add", str(topic_dir),
                "--concept", "closures", "--difficulty", "3",
                "--type", "application", "--text", "Q?", "--answer", "A",
            ])
            self._run_cmd(["record", str(topic_dir), "q-1", "1"])
            result = self._run_cmd(["calibrate", str(topic_dir), "--json"])
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)
            self.assertIn("level", data)

    def test_full_workflow_init_add_select_record(self):
        """End-to-end: init -> add -> select -> record -> stats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)

            # Init
            r = self._run_cmd(["init", str(topic_dir)])
            self.assertEqual(r.returncode, 0)

            # Add questions
            for i, (concept, diff, qtype) in enumerate([
                ("closures", 2, "conceptual"),
                ("closures", 2, "application"),
                ("useState", 3, "analysis"),
            ]):
                r = self._run_cmd([
                    "add", str(topic_dir),
                    "--concept", concept, "--difficulty", str(diff),
                    "--type", qtype, "--text", f"Question {i+1}?",
                    "--answer", f"Answer {i+1}",
                ])
                self.assertEqual(r.returncode, 0)

            # Select
            r = self._run_cmd(["select", str(topic_dir), "--count", "2", "--json"])
            self.assertEqual(r.returncode, 0)
            recs = json.loads(r.stdout)
            self.assertGreater(len(recs["recommendations"]), 0)

            # Record results
            r = self._run_cmd(["record", str(topic_dir), "q-1", "1",
                               "--quality", "strong", "--session", "1"])
            self.assertEqual(r.returncode, 0)

            r = self._run_cmd(["record", str(topic_dir), "q-2", "0",
                               "--quality", "wrong", "--session", "1"])
            self.assertEqual(r.returncode, 0)

            # Stats
            r = self._run_cmd(["stats", str(topic_dir), "--json"])
            self.assertEqual(r.returncode, 0)
            stats = json.loads(r.stdout)
            self.assertEqual(stats["total"], 3)
            self.assertEqual(stats["total_assessments"], 2)

            # Coverage
            r = self._run_cmd(["coverage", str(topic_dir), "--json"])
            self.assertEqual(r.returncode, 0)
            cov = json.loads(r.stdout)
            self.assertIn("closures", cov["coverage"])

    def test_record_invalid_question_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)
            self._run_cmd(["init", str(topic_dir)])
            result = self._run_cmd(["record", str(topic_dir), "q-999", "1"])
            self.assertIn("not found", result.stdout)

    def test_json_output_all_commands(self):
        """Verify --json produces valid JSON for all commands that support it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            topic_dir = make_topic_dir(tmpdir)

            # init --json
            r = self._run_cmd(["init", str(topic_dir), "--json"])
            json.loads(r.stdout)  # must parse

            # add --json
            r = self._run_cmd([
                "add", str(topic_dir),
                "--concept", "closures", "--difficulty", "2",
                "--type", "conceptual", "--text", "Q?", "--answer", "A",
                "--json",
            ])
            json.loads(r.stdout)

            # select --json
            r = self._run_cmd(["select", str(topic_dir), "--json"])
            json.loads(r.stdout)

            # record --json
            r = self._run_cmd(["record", str(topic_dir), "q-1", "1", "--json"])
            json.loads(r.stdout)

            # coverage --json
            r = self._run_cmd(["coverage", str(topic_dir), "--json"])
            json.loads(r.stdout)

            # stats --json
            r = self._run_cmd(["stats", str(topic_dir), "--json"])
            json.loads(r.stdout)

            # calibrate --json
            r = self._run_cmd(["calibrate", str(topic_dir), "--json"])
            json.loads(r.stdout)


if __name__ == "__main__":
    unittest.main()
