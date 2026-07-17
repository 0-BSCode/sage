#!/usr/bin/env python3
"""Tests for archive_project.py.

Covers:
- parse_index removes the archived project's own row
- parse_index strips inbound Overlaps-With references
- parse_index preserves title / blockquote / header / separator / other rows
- parse_index handles em-dash and empty overlap placeholders
- parse_index is idempotent for an absent slug
- next_archive_dir returns the base name when free, numeric suffix on collision
- archive_project moves the whole project tree under .archive/
- archive_project co-locates the cross-ref shard as cross-refs.md
- archive_project writes archive-meta.json with correct stash + provenance
- archive_project scrubs INDEX.md
- archive_project works with no cross-refs registry at all
- archive_project uses a numeric suffix when .archive/<slug> already exists
- archive_project raises on a non-existent project (never half-moves)
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

import archive_project as ap


SAMPLE_INDEX = """\
# Cross-Reference Index

> When running a session for project X, load `cross-refs/X.md` plus every
> file in the "Overlaps With" column.

| Project | Overlaps With |
|---|---|
| alpha | beta, gamma |
| beta | alpha |
| gamma | alpha, delta |
| delta | — |
"""


class TestParseIndex(unittest.TestCase):
    def test_removes_own_row(self):
        new_text, frags = ap.parse_index(SAMPLE_INDEX, "alpha")
        self.assertNotIn("| alpha |", new_text)
        self.assertIsNotNone(frags["own_row"])
        self.assertEqual(frags["own_overlaps"], ["beta", "gamma"])

    def test_strips_inbound_references(self):
        new_text, frags = ap.parse_index(SAMPLE_INDEX, "alpha")
        # beta only overlapped alpha → now empty placeholder
        self.assertIn("| beta | — |", new_text)
        # gamma overlapped alpha, delta → alpha gone, delta kept
        self.assertIn("| gamma | delta |", new_text)
        inbound = {i["project"] for i in frags["inbound"]}
        self.assertEqual(inbound, {"beta", "gamma"})

    def test_preserves_structure(self):
        new_text, _ = ap.parse_index(SAMPLE_INDEX, "alpha")
        self.assertIn("# Cross-Reference Index", new_text)
        self.assertIn("> When running a session", new_text)
        self.assertIn("| Project | Overlaps With |", new_text)
        self.assertIn("|---|---|", new_text)
        # untouched row survives verbatim
        self.assertIn("| delta | — |", new_text)

    def test_absent_slug_is_noop(self):
        new_text, frags = ap.parse_index(SAMPLE_INDEX, "nonexistent")
        self.assertEqual(new_text, SAMPLE_INDEX)
        self.assertIsNone(frags["own_row"])
        self.assertEqual(frags["inbound"], [])

    def test_split_overlaps_placeholders(self):
        for placeholder in ("—", "-", "", "  "):
            self.assertEqual(ap._split_overlaps(placeholder), [])
        self.assertEqual(ap._split_overlaps("a, b ,c"), ["a", "b", "c"])


class TestNextArchiveDir(unittest.TestCase):
    def test_free_returns_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, ".archive")
            os.makedirs(base)
            self.assertEqual(ap.next_archive_dir(base, "alpha"),
                             os.path.join(base, "alpha"))

    def test_collision_suffixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, ".archive")
            os.makedirs(os.path.join(base, "alpha"))
            self.assertEqual(ap.next_archive_dir(base, "alpha"),
                             os.path.join(base, "alpha-2"))
            os.makedirs(os.path.join(base, "alpha-2"))
            self.assertEqual(ap.next_archive_dir(base, "alpha"),
                             os.path.join(base, "alpha-3"))


class TestArchiveProject(unittest.TestCase):
    def _make_root(self, tmp, with_cross_refs=True):
        root = Path(tmp)
        # Project tree
        jdir = root / "alpha" / "learning" / "journal"
        jdir.mkdir(parents=True)
        (jdir / "index.md").write_text("| 1 | 2026-07-10 |\n")
        (root / "alpha" / "learning" / "plan.md").write_text("plan\n")
        if with_cross_refs:
            cr = root / "cross-refs"
            cr.mkdir()
            (cr / "INDEX.md").write_text(SAMPLE_INDEX)
            (cr / "alpha.md").write_text("# Cross-References: alpha\n")
        return root

    def test_moves_project_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp)
            ap.archive_project(str(root), "alpha", date="2026-07-17")
            self.assertFalse((root / "alpha").exists())
            moved = root / ".archive" / "alpha"
            self.assertTrue(moved.is_dir())
            self.assertTrue((moved / "learning" / "journal" / "index.md").is_file())
            self.assertTrue((moved / "learning" / "plan.md").is_file())

    def test_colocates_shard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp)
            summary = ap.archive_project(str(root), "alpha", date="2026-07-17")
            self.assertTrue((root / ".archive" / "alpha" / "cross-refs.md").is_file())
            self.assertFalse((root / "cross-refs" / "alpha.md").exists())
            self.assertTrue(summary["shard_archived"])

    def test_writes_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp)
            ap.archive_project(str(root), "alpha", date="2026-07-17")
            meta = json.loads(
                (root / ".archive" / "alpha" / "archive-meta.json").read_text()
            )
            self.assertEqual(meta["original_slug"], "alpha")
            self.assertEqual(meta["archived_date"], "2026-07-17")
            self.assertEqual(meta["archived_dir"], "alpha")
            self.assertEqual(meta["inbound_ref_count"], 2)
            self.assertTrue(meta["shard_archived"])
            self.assertEqual(meta["index"]["own_overlaps"], ["beta", "gamma"])

    def test_scrubs_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp)
            summary = ap.archive_project(str(root), "alpha", date="2026-07-17")
            index_text = (root / "cross-refs" / "INDEX.md").read_text()
            self.assertNotIn("alpha", index_text)
            self.assertIn("| beta | — |", index_text)
            self.assertIn("| gamma | delta |", index_text)
            self.assertEqual(sorted(summary["inbound_refs_scrubbed"]),
                             ["beta", "gamma"])

    def test_no_cross_refs_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp, with_cross_refs=False)
            summary = ap.archive_project(str(root), "alpha", date="2026-07-17")
            self.assertTrue((root / ".archive" / "alpha").is_dir())
            self.assertFalse(summary["shard_archived"])
            self.assertFalse(summary["index_own_row_removed"])
            meta = json.loads(
                (root / ".archive" / "alpha" / "archive-meta.json").read_text()
            )
            self.assertEqual(meta["inbound_ref_count"], 0)

    def test_collision_uses_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp)
            # Pre-existing archive of a prior generation.
            (root / ".archive" / "alpha").mkdir(parents=True)
            summary = ap.archive_project(str(root), "alpha", date="2026-07-17")
            self.assertTrue((root / ".archive" / "alpha-2").is_dir())
            self.assertEqual(summary["archived_dir"], str(root / ".archive" / "alpha-2"))

    def test_missing_project_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                ap.archive_project(tmp, "ghost", date="2026-07-17")


class TestPlanArchive(unittest.TestCase):
    """The plan is what the coach's confirmation prompt is built from, so it
    must be exact and must not touch disk."""

    def _make_root(self, tmp, with_cross_refs=True):
        root = Path(tmp)
        jdir = root / "alpha" / "learning" / "journal"
        jdir.mkdir(parents=True)
        (jdir / "index.md").write_text("| 1 | 2026-07-10 |\n")
        if with_cross_refs:
            cr = root / "cross-refs"
            cr.mkdir()
            (cr / "INDEX.md").write_text(SAMPLE_INDEX)
            (cr / "alpha.md").write_text("# Cross-References: alpha\n")
        return root

    def test_dry_run_touches_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp)
            before = sorted(p.relative_to(root).as_posix()
                            for p in root.rglob("*"))
            index_before = (root / "cross-refs" / "INDEX.md").read_text()

            ap.plan_archive(str(root), "alpha")

            after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertEqual(index_before,
                             (root / "cross-refs" / "INDEX.md").read_text())
            # planning must not even create .archive/
            self.assertFalse((root / ".archive").exists())

    def test_plan_reports_exact_inbound_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp)
            plan = ap.plan_archive(str(root), "alpha")
            self.assertEqual(plan["inbound_ref_count"], 2)
            self.assertEqual(sorted(plan["inbound_refs_scrubbed"]),
                             ["beta", "gamma"])
            self.assertTrue(plan["shard_archived"])
            self.assertTrue(plan["index_own_row_removed"])

    def test_plan_predicts_suffixed_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp)
            (root / ".archive" / "alpha").mkdir(parents=True)
            plan = ap.plan_archive(str(root), "alpha")
            self.assertEqual(plan["archived_dir"],
                             str(root / ".archive" / "alpha-2"))

    def test_plan_matches_execution(self):
        """A dry-run must predict exactly what archiving then does."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp)
            plan = ap._summary(ap.plan_archive(str(root), "alpha"), "dry_run")
            actual = ap.archive_project(str(root), "alpha", date="2026-07-17")
            self.assertEqual(plan["status"], "dry_run")
            self.assertEqual(actual["status"], "archived")
            for key in ap.SUMMARY_KEYS:
                self.assertEqual(plan[key], actual[key], f"mismatch on {key}")

    def test_plan_no_cross_refs_reports_no_shard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp, with_cross_refs=False)
            plan = ap.plan_archive(str(root), "alpha")
            self.assertFalse(plan["shard_archived"])
            self.assertFalse(plan["index_own_row_removed"])
            self.assertEqual(plan["inbound_ref_count"], 0)

    def test_plan_missing_project_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                ap.plan_archive(tmp, "ghost")

    def test_summary_strips_internals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._make_root(tmp)
            summary = ap._summary(ap.plan_archive(str(root), "alpha"), "dry_run")
            self.assertFalse([k for k in summary if k.startswith("_")])


if __name__ == "__main__":
    unittest.main()
