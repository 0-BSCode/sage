#!/usr/bin/env python3
"""Tests for coach_metrics.py — coach effectiveness metrics.

Covers:
- snapshot computes all 4 metrics from test data
- snapshot creates metrics/ directory, history.json, dashboard.md
- snapshot handles missing files gracefully
- snapshot with sparse data (mastery velocity = null)
- trends requires 2+ snapshots
- compare produces valid comparison output
- TTS uses Introduced column, not changelog for introduction session
- review efficiency excludes retired cards
- regression rate counts concepts once regardless of multiple regressions
- threshold flags trigger correctly
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tools" / "coach" / "coach_metrics.py"


def run_tool(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), *args],
        capture_output=True,
        text=True,
    )


def make_kmap(concepts: list, changelog: list = None) -> str:
    lines = [
        "# Knowledge Map",
        "",
        "| Concept | Status | Introduced | Last Tested | Notes |",
        "|---------|--------|------------|-------------|-------|",
    ]
    for c in concepts:
        lines.append(f"| {c['name']} | {c['status']} | {c['introduced']} | {c.get('tested', 'S1')} | {c.get('notes', '')} |")

    if changelog:
        lines.append("")
        lines.append("## Status Changelog")
        lines.append("")
        lines.append("| Date | Concept | From | To | Session |")
        lines.append("|------|---------|------|----|---------|")
        for cl in changelog:
            lines.append(f"| 2026-01-01 | {cl['concept']} | {cl['from']} | {cl['to']} | {cl['session']} |")

    return "\n".join(lines)


def make_srs(cards: dict) -> str:
    return json.dumps({
        "version": "1.0",
        "algorithm": "sm2",
        "topic": "test",
        "created": "2026-01-01",
        "last_sync": "2026-01-01",
        "cards": cards,
    })


def make_journal_index(sessions: int) -> str:
    lines = [
        "# Session Index",
        "",
        "| # | Date | Type | Focus | Reviews | Avg Grade | Summary | File |",
        "|---|------|------|-------|---------|-----------|---------|------|",
    ]
    for i in range(1, sessions + 1):
        lines.append(f"| {i} | 2026-01-{i:02d} | deep | Topic {i} | 0 | — | — | session-{i:02d}.md |")
    return "\n".join(lines)


class SnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="metrics_"))
        self.learning = self.tmp / "learning"
        self.learning.mkdir()
        journal = self.learning / "journal"
        journal.mkdir()
        (journal / "index.md").write_text(make_journal_index(10))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_snapshot_computes_all_metrics(self) -> None:
        concepts = [
            {"name": "A", "status": "Solid", "introduced": "S1"},
            {"name": "B", "status": "Solid", "introduced": "S2"},
            {"name": "C", "status": "Developing", "introduced": "S3"},
        ]
        changelog = [
            {"concept": "A", "from": "Developing", "to": "Solid", "session": 4},
            {"concept": "B", "from": "Developing", "to": "Solid", "session": 6},
        ]
        (self.learning / "knowledge-map.md").write_text(make_kmap(concepts, changelog))

        cards = {
            "card-1": {
                "retired": False,
                "review_history": [
                    {"date": "2026-01-05", "quality": 5, "ef": 2.6, "interval": 6},
                    {"date": "2026-01-06", "quality": 4, "ef": 2.6, "interval": 6},
                    {"date": "2026-01-07", "quality": 2, "ef": 2.3, "interval": 1},
                ],
            },
        }
        (self.learning / "cards.srs.json").write_text(make_srs(cards))

        result = run_tool("snapshot", str(self.learning))
        self.assertEqual(result.returncode, 0, result.stderr)

        data = json.loads(result.stdout)
        m = data["metrics"]

        self.assertEqual(m["time_to_solid_avg"], 3.5)  # (4-1 + 6-2) / 2
        self.assertAlmostEqual(m["review_efficiency"], 0.6667, places=3)  # 2/3
        self.assertEqual(m["regression_rate"], 0.0)
        self.assertEqual(m["total_concepts"], 3)

    def test_snapshot_creates_metrics_directory(self) -> None:
        concepts = [{"name": "X", "status": "Introduced", "introduced": "S1"}]
        (self.learning / "knowledge-map.md").write_text(make_kmap(concepts))

        run_tool("snapshot", str(self.learning))

        self.assertTrue((self.learning / "metrics").is_dir())
        self.assertTrue((self.learning / "metrics" / "history.json").exists())
        self.assertTrue((self.learning / "metrics" / "dashboard.md").exists())

    def test_snapshot_appends_to_history(self) -> None:
        concepts = [{"name": "X", "status": "Introduced", "introduced": "S1"}]
        (self.learning / "knowledge-map.md").write_text(make_kmap(concepts))

        run_tool("snapshot", str(self.learning))
        run_tool("snapshot", str(self.learning))

        history = json.loads((self.learning / "metrics" / "history.json").read_text())
        self.assertEqual(len(history), 2)

    def test_snapshot_sparse_data_mastery_velocity_null(self) -> None:
        concepts = [
            {"name": "A", "status": "Solid", "introduced": "S1"},
            {"name": "B", "status": "Solid", "introduced": "S2"},
        ]
        changelog = [
            {"concept": "A", "from": "Developing", "to": "Solid", "session": 3},
            {"concept": "B", "from": "Developing", "to": "Solid", "session": 4},
        ]
        (self.learning / "knowledge-map.md").write_text(make_kmap(concepts, changelog))

        result = run_tool("snapshot", str(self.learning))
        data = json.loads(result.stdout)
        self.assertIsNone(data["metrics"]["mastery_velocity_trend"])

    def test_snapshot_no_kmap(self) -> None:
        result = run_tool("snapshot", str(self.learning))
        self.assertEqual(result.returncode, 0)

    def test_regression_flag_triggers(self) -> None:
        concepts = [
            {"name": "A", "status": "Developing", "introduced": "S1"},
        ]
        changelog = [
            {"concept": "A", "from": "Introduced", "to": "Solid", "session": 3},
            {"concept": "A", "from": "Solid", "to": "Developing", "session": 5},
        ]
        (self.learning / "knowledge-map.md").write_text(make_kmap(concepts, changelog))

        result = run_tool("snapshot", str(self.learning))
        data = json.loads(result.stdout)
        self.assertEqual(len(data["metrics"]["regressions"]), 1)
        self.assertEqual(data["metrics"]["regressions"][0]["concept"], "A")

    def test_review_efficiency_excludes_retired(self) -> None:
        (self.learning / "knowledge-map.md").write_text(make_kmap([
            {"name": "X", "status": "Introduced", "introduced": "S1"},
        ]))
        cards = {
            "card-1": {
                "retired": False,
                "review_history": [{"date": "2026-01-01", "quality": 5, "ef": 2.6, "interval": 6}],
            },
            "card-2": {
                "retired": True,
                "review_history": [{"date": "2026-01-01", "quality": 1, "ef": 1.3, "interval": 1}],
            },
        }
        (self.learning / "cards.srs.json").write_text(make_srs(cards))

        result = run_tool("snapshot", str(self.learning))
        data = json.loads(result.stdout)
        self.assertEqual(data["metrics"]["review_efficiency"], 1.0)

    def test_review_efficiency_warning_below_60(self) -> None:
        (self.learning / "knowledge-map.md").write_text(make_kmap([
            {"name": "X", "status": "Introduced", "introduced": "S1"},
        ]))
        cards = {
            "card-1": {
                "retired": False,
                "review_history": [
                    {"date": "2026-01-01", "quality": 2, "ef": 2.0, "interval": 1},
                    {"date": "2026-01-02", "quality": 3, "ef": 2.0, "interval": 1},
                    {"date": "2026-01-03", "quality": 2, "ef": 2.0, "interval": 1},
                ],
            },
        }
        (self.learning / "cards.srs.json").write_text(make_srs(cards))

        result = run_tool("snapshot", str(self.learning))
        data = json.loads(result.stdout)
        warnings = [f for f in data["flags"] if f["status"] == "warning" and f["metric"] == "review_efficiency"]
        self.assertEqual(len(warnings), 1)


    def test_snapshot_ignores_table_format_legend(self) -> None:
        """Status Legend in table format should not be counted as concepts."""
        kmap = (
            "# Knowledge Map\n\n"
            "## Status Legend\n\n"
            "| Status | Definition |\n"
            "|---|---|\n"
            "| not started | Not covered yet |\n"
            "| introduced | Covered once |\n"
            "| solid | Reliable retrieval |\n\n"
            "| Concept | Status | Introduced | Last Tested | Notes |\n"
            "|---------|--------|------------|-------------|-------|\n"
            "| Alpha | Solid | S1 | S5 | ok |\n"
            "| Beta | Developing | S2 | S4 | wip |\n"
        )
        (self.learning / "knowledge-map.md").write_text(kmap)

        result = run_tool("snapshot", str(self.learning))
        data = json.loads(result.stdout)
        self.assertEqual(data["metrics"]["total_concepts"], 2)


class TrendsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="metrics_"))
        self.learning = self.tmp / "learning"
        self.learning.mkdir()
        (self.learning / "metrics").mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_trends_insufficient_history(self) -> None:
        (self.learning / "metrics" / "history.json").write_text("[]")
        result = run_tool("trends", str(self.learning))
        data = json.loads(result.stdout)
        self.assertIn("Insufficient", data["message"])

    def test_trends_with_two_snapshots(self) -> None:
        history = [
            {"session": 5, "date": "2026-01-05", "metrics": {
                "time_to_solid_avg": 5.0, "review_efficiency": 0.70,
                "regression_rate": 0.10, "mastery_velocity_slope": -0.2,
            }, "flags": []},
            {"session": 10, "date": "2026-01-10", "metrics": {
                "time_to_solid_avg": 4.0, "review_efficiency": 0.75,
                "regression_rate": 0.08, "mastery_velocity_slope": -0.3,
            }, "flags": []},
        ]
        (self.learning / "metrics" / "history.json").write_text(json.dumps(history))

        result = run_tool("trends", str(self.learning))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["snapshots_analyzed"], 2)
        self.assertIn("time_to_solid", data["trends"])


class CompareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="metrics_"))

        for name in ("proj1", "proj2"):
            learning = self.tmp / name / "learning"
            learning.mkdir(parents=True)
            journal = learning / "journal"
            journal.mkdir()
            (journal / "index.md").write_text(make_journal_index(10))

            concepts = [
                {"name": "A", "status": "Solid", "introduced": "S1"},
                {"name": "B", "status": "Solid", "introduced": "S2"},
            ]
            changelog = [
                {"concept": "A", "from": "Developing", "to": "Solid", "session": 3},
                {"concept": "B", "from": "Developing", "to": "Solid", "session": 5},
            ]
            (learning / "knowledge-map.md").write_text(make_kmap(concepts, changelog))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_compare_two_projects(self) -> None:
        p1 = str(self.tmp / "proj1" / "learning")
        p2 = str(self.tmp / "proj2" / "learning")
        result = run_tool("compare", p1, p2)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIn("project_1", data)
        self.assertIn("project_2", data)
        self.assertIn("comparison", data)
        self.assertEqual(data["comparison"]["faster_mastery"], "tied")


if __name__ == "__main__":
    unittest.main()
