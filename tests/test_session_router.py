#!/usr/bin/env python3
"""Tests for session_router.py — verb dispatch and discovery predicates.

Covers:
- unknown / legacy verbs return mode 'unknown_verb' with guidance
- learn discovery (resume picker) is journal-based
- archive discovery (picker + resolution) is plan-based, so a plan-only
  project (initialized, never a session) is archivable
- learn on a plan-only project routes to 'fresh'; on a journal project to 'resume'
- archive on a project with neither plan nor journal -> 'archive_no_match'
- bare verbs open the picker with the correct 'action' and predicate
"""

import os
import tempfile
import unittest
from pathlib import Path

import session_router as sr


class RouterTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._prev_env = os.environ.get("SAGE_LEARNING_ROOT")
        os.environ["SAGE_LEARNING_ROOT"] = str(self.root)

    def tearDown(self):
        if self._prev_env is None:
            os.environ.pop("SAGE_LEARNING_ROOT", None)
        else:
            os.environ["SAGE_LEARNING_ROOT"] = self._prev_env
        self.tmp.cleanup()

    def _make(self, slug, plan=False, journal=False):
        learning = self.root / slug / "learning"
        learning.mkdir(parents=True, exist_ok=True)
        if plan:
            (learning / "plan.md").write_text("# Plan\n")
        if journal:
            jdir = learning / "journal"
            jdir.mkdir(exist_ok=True)
            (jdir / "index.md").write_text("| 1 | 2026-07-10 |\n")


class TestVerbDispatch(RouterTestCase):
    def test_legacy_bare_topic_is_unknown_verb(self):
        out = sr.route("/sage", "react hooks")
        self.assertEqual(out["mode"], "unknown_verb")

    def test_legacy_keyword_suggests_learn(self):
        out = sr.route("/sage", "continue")
        self.assertEqual(out["mode"], "unknown_verb")
        self.assertEqual(out["suggestion"], "learn")


class TestDiscoveryPredicates(RouterTestCase):
    def test_learn_picker_is_journal_based(self):
        self._make("has-journal", plan=True, journal=True)
        self._make("plan-only", plan=True, journal=False)
        out = sr.route("/sage", "learn")
        slugs = {p["slug"] for p in out["projects"]}
        self.assertEqual(out["action"], "learn")
        self.assertIn("has-journal", slugs)
        self.assertNotIn("plan-only", slugs)

    def test_archive_picker_is_plan_based(self):
        self._make("has-journal", plan=True, journal=True)
        self._make("plan-only", plan=True, journal=False)
        self._make("empty-dir", plan=False, journal=False)
        out = sr.route("/sage", "archive")
        slugs = {p["slug"] for p in out["projects"]}
        self.assertEqual(out["action"], "archive")
        self.assertIn("has-journal", slugs)
        self.assertIn("plan-only", slugs)      # initialized but never started
        self.assertNotIn("empty-dir", slugs)   # not a real project


class TestResolution(RouterTestCase):
    def test_archive_plan_only_project_matches(self):
        self._make("plan-only", plan=True, journal=False)
        out = sr.route("/sage", "archive plan-only")
        self.assertEqual(out["mode"], "archive")
        self.assertEqual(out["slug"], "plan-only")

    def test_archive_no_plan_no_match(self):
        self._make("empty-dir", plan=False, journal=False)
        out = sr.route("/sage", "archive empty-dir")
        self.assertEqual(out["mode"], "archive_no_match")

    def test_archive_no_match_suggests_close_slug(self):
        self._make("react-hooks", plan=True)
        out = sr.route("/sage", "archive raect-hooks")
        self.assertEqual(out["mode"], "archive_no_match")
        self.assertEqual(out["suggestion"], "react-hooks")

    def test_learn_plan_only_is_fresh(self):
        self._make("plan-only", plan=True, journal=False)
        out = sr.route("/sage", "learn plan-only")
        self.assertEqual(out["mode"], "fresh")

    def test_learn_journal_is_resume(self):
        self._make("has-journal", plan=True, journal=True)
        out = sr.route("/sage", "learn has-journal")
        self.assertEqual(out["mode"], "resume")


if __name__ == "__main__":
    unittest.main()
