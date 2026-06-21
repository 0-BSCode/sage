#!/usr/bin/env python3
"""Tests for migrations/backfill_introduced.py.

Covers:
- Backfill from changelog source (earliest session)
- Backfill from journal index scan (substring match)
- Backfill fallback to S1 when no source found
- Prior concepts get 'prior' as introduced value
- Already-migrated tables are skipped
- Dry-run does not write changes
- Apply mode writes the Introduced column
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "migrations" / "backfill_introduced.py"

KMAP_BASIC = """\
# Knowledge Map — Test

| Concept | Status | Last Tested | Notes |
|---------|--------|-------------|-------|
| Alpha | Solid | S5 | Good |
| Beta | Developing | S3 | WIP |
| Gamma | Prior (from other-project) | S1 | Cross-ref |
"""

CHANGELOG = """\
## Status Changelog

| Date | Concept | From | To | Session |
|------|---------|------|----|---------|
| 2026-01-10 | Alpha | Introduced | Developing | 2 |
| 2026-01-15 | Alpha | Developing | Solid | 5 |
"""

JOURNAL_INDEX = """\
# Session Index

| # | Date | Type | Focus | Reviews | Avg Grade | Summary | File |
|---|------|------|-------|---------|-----------|---------|------|
| 1 | 2026-01-01 | deep | Intro concepts | — | — | Started with basics | session-01.md |
| 3 | 2026-01-08 | deep | Beta deep dive | — | — | Covered Beta in depth | session-03.md |
"""

KMAP_ALREADY_MIGRATED = """\
# Knowledge Map

| Concept | Status | Introduced | Last Tested | Notes |
|---------|--------|------------|-------------|-------|
| Alpha | Solid | S1 | S5 | Done |
"""


def run_script(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


class BackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="backfill_"))
        self.learning = self.tmp / "learning"
        self.learning.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _setup_project(self, kmap: str = KMAP_BASIC,
                       changelog: str = "", journal: str = "") -> None:
        (self.learning / "knowledge-map.md").write_text(kmap)
        if changelog:
            # Append changelog to kmap
            current = (self.learning / "knowledge-map.md").read_text()
            (self.learning / "knowledge-map.md").write_text(current + "\n" + changelog)
        if journal:
            journal_dir = self.learning / "journal"
            journal_dir.mkdir(exist_ok=True)
            (journal_dir / "index.md").write_text(journal)

    def test_dry_run_does_not_write(self) -> None:
        self._setup_project(changelog=CHANGELOG, journal=JOURNAL_INDEX)
        original = (self.learning / "knowledge-map.md").read_text()
        result = run_script(str(self.learning))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dry run", result.stdout.lower())
        after = (self.learning / "knowledge-map.md").read_text()
        self.assertEqual(original, after)

    def test_apply_writes_introduced_column(self) -> None:
        self._setup_project(changelog=CHANGELOG, journal=JOURNAL_INDEX)
        result = run_script(str(self.learning), "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.learning / "knowledge-map.md").read_text()
        self.assertIn("| Concept | Status | Introduced |", body)

    def test_changelog_source_uses_earliest_session(self) -> None:
        self._setup_project(changelog=CHANGELOG, journal=JOURNAL_INDEX)
        run_script(str(self.learning), "--apply")
        body = (self.learning / "knowledge-map.md").read_text()
        # Alpha first appears in changelog at session 2
        self.assertIn("| Alpha | Solid | S2 |", body)

    def test_journal_source_substring_match(self) -> None:
        self._setup_project(changelog=CHANGELOG, journal=JOURNAL_INDEX)
        run_script(str(self.learning), "--apply")
        body = (self.learning / "knowledge-map.md").read_text()
        # Beta mentioned in journal session 3 Focus column
        self.assertIn("| Beta | Developing | S3 |", body)

    def test_fallback_to_s1(self) -> None:
        # No changelog, no journal — everything falls back to S1
        self._setup_project()
        run_script(str(self.learning), "--apply")
        body = (self.learning / "knowledge-map.md").read_text()
        # Alpha has no source → S1
        self.assertIn("| Alpha | Solid | S1 |", body)

    def test_prior_concepts_get_prior(self) -> None:
        self._setup_project(changelog=CHANGELOG, journal=JOURNAL_INDEX)
        run_script(str(self.learning), "--apply")
        body = (self.learning / "knowledge-map.md").read_text()
        self.assertIn("| Gamma | Prior (from other-project) | prior |", body)

    def test_already_migrated_skipped(self) -> None:
        self._setup_project(kmap=KMAP_ALREADY_MIGRATED)
        result = run_script(str(self.learning))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already migrated", result.stdout.lower())

    def test_summary_counts_sources(self) -> None:
        self._setup_project(changelog=CHANGELOG, journal=JOURNAL_INDEX)
        result = run_script(str(self.learning))
        self.assertIn("From changelog:", result.stdout)
        self.assertIn("From journal:", result.stdout)
        self.assertIn("Prior:", result.stdout)


if __name__ == "__main__":
    unittest.main()
