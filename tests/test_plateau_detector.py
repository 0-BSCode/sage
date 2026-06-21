#!/usr/bin/env python3
"""Tests for tools/plateau/plateau_detector.py"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "plateau" / "plateau_detector.py"

PASS = 0
FAIL = 0


def assert_eq(test_name: str, expected, actual):
    global PASS, FAIL
    if expected == actual:
        print(f"  PASS: {test_name}")
        PASS += 1
    else:
        print(f"  FAIL: {test_name}")
        print(f"    expected: {expected}")
        print(f"    got: {actual}")
        FAIL += 1


class Fixtures:
    """Creates temp directory with learning artifacts for testing."""

    def __init__(self, tmpdir: str):
        self.tmpdir = Path(tmpdir)
        self.journal_dir = self.tmpdir / "journal"
        self.journal_dir.mkdir()
        self.srs_path = self.tmpdir / "cards.srs.json"
        self.ws_path = self.tmpdir / "weak-spots.md"

    def write_journal_index(self, rows: list):
        """Write journal/index.md with given row dicts."""
        lines = [
            "| # | Date | Type | Focus | Reviews | Avg Grade | Duration | File |",
            "|---|------|------|-------|---------|-----------|----------|------|",
        ]
        for r in rows:
            lines.append(
                f"| {r.get('id', '1')} | {r.get('date', '2026-04-01')} "
                f"| {r.get('type', '—')} | {r.get('focus', '—')} "
                f"| {r.get('reviews', '—')} | {r.get('avg_grade', '—')} "
                f"| {r.get('duration', '45m')} | {r.get('file', 'session-01.md')} |"
            )
        (self.journal_dir / "index.md").write_text("\n".join(lines))

    def write_srs(self, cards: dict):
        """Write cards.srs.json with given cards dict."""
        self.srs_path.write_text(json.dumps({"cards": cards}, indent=2))

    def write_weak_spots(self, weak_spots: list):
        """Write weak-spots.md with given weak spot entries."""
        lines = [
            "# Weak Spots",
            "",
            "---",
        ]
        for ws in weak_spots:
            ws_id = ws["id"]
            desc = ws.get("desc", "test")
            category = ws.get("category", "wrong-model")
            cards = ws.get("cards", [])
            cards_str = ", ".join(f"card-{c}" for c in cards) if cards else "—"
            first = ws.get("first", "S1")
            status = ws.get("status", "active")
            sessions = ws.get("sessions", [])

            lines.append("")
            lines.append(f"## {ws_id} — {desc}")
            lines.append("")
            lines.append(f"**Category:** {category}")
            lines.append(f"**Session:** {first.replace('S', '')}")
            lines.append(f"**Last tested:** {ws.get('last', first)}")
            lines.append(f"**What happened:** {desc}")
            lines.append(f"**Correct model:** (correct)")
            lines.append(f"**Cards:** {cards_str}")
            lines.append(f"**Status:** {status}")
            lines.append("")
            lines.append("### History")
            for s in sessions:
                lines.append(f"- **{s}:** Observed")
            if not sessions:
                lines.append(f"- **{first}:** First observed")
            lines.append("")
            lines.append("---")
        self.ws_path.write_text("\n".join(lines))

    def run(self, extra_args=None) -> dict:
        """Run plateau_detector.py against these fixtures."""
        cmd = [
            sys.executable, str(SCRIPT),
            "--journal-dir", str(self.journal_dir),
            "--srs", str(self.srs_path),
            "--weak-spots", str(self.ws_path),
        ]
        if extra_args:
            cmd.extend(extra_args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    stderr: {result.stderr.strip()}")
            return {}
        return json.loads(result.stdout)


def make_review_history(grades: list) -> list:
    """Build a review_history list from a list of grade ints."""
    return [{"quality": g, "date": f"2026-04-{i+1:02d}"} for i, g in enumerate(grades)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

print("plateau_detector.py")

# --- No plateau: healthy learning ---
print()
print("  [no plateau]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([
        {"id": "1", "type": "deep", "reviews": "0", "file": "session-01.md"},
        {"id": "2", "type": "—", "reviews": "5", "avg_grade": "4.2", "file": "session-02.md"},
        {"id": "3", "type": "deep", "reviews": "0", "file": "session-03.md"},
    ])
    f.write_srs({
        "card-1": {"review_history": make_review_history([3, 4, 5])},
        "card-2": {"review_history": make_review_history([4, 4, 5])},
    })
    f.write_weak_spots([])

    r = f.run()
    assert_eq("no plateau signal", "NO_PLATEAU_DETECTED", r["signal"])
    assert_eq("standard mode", "standard", r["recommended_mode"])
    assert_eq("no rules fired", False, any(r["rules"].values()))

# --- Stale weak spots (no card data) ---
print()
print("  [stale weak spots]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([])
    f.write_srs({})
    f.write_weak_spots([{
        "id": "WS-1",
        "desc": "Confuses map and flatMap",
        "cards": [],
        "sessions": ["S1", "S2", "S3", "S4"],
        "first": "S1",
        "last": "S4",
        "status": "active",
    }])

    r = f.run()
    assert_eq("stale ws rule fires", True, r["rules"]["stale_weak_spots"])
    assert_eq("mode is targeted_redesign", "targeted_redesign", r["recommended_mode"])
    assert_eq("visual_demo is candidate", True, "visual_demo" in r["candidate_modes"])

# --- Stale weak spots (with flat card grades) ---
print()
print("  [stale ws + flat card grades]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([])
    f.write_srs({
        "card-1": {"review_history": make_review_history([2, 3, 3])},
        "card-2": {"review_history": make_review_history([3, 3, 2])},
    })
    f.write_weak_spots([{
        "id": "WS-1",
        "desc": "Confuses map and flatMap",
        "cards": ["1", "2"],
        "sessions": ["S1", "S2", "S3", "S4"],
        "first": "S1",
        "last": "S4",
        "status": "active",
    }])

    r = f.run()
    assert_eq("stale ws fires with flat grades", True, r["rules"]["stale_weak_spots"])
    assert_eq("flat grades also fires", True, r["rules"]["flat_grades"])
    assert_eq("plateau likely", "PLATEAU_LIKELY", r["signal"])
    assert_eq("mode is interleaved", "interleaved_application", r["recommended_mode"])

# --- Resolved weak spots are skipped ---
print()
print("  [resolved weak spots ignored]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([])
    f.write_srs({})
    f.write_weak_spots([{
        "id": "WS-1",
        "desc": "Old issue",
        "cards": [],
        "sessions": ["S1", "S2", "S3", "S4", "S5"],
        "first": "S1",
        "last": "S5",
        "status": "resolved",
    }])

    r = f.run()
    assert_eq("resolved ws not flagged", False, r["rules"]["stale_weak_spots"])

# --- Flat grades only ---
print()
print("  [flat grades only]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([])
    f.write_srs({
        "card-1": {"review_history": make_review_history([2, 2, 3])},
        "card-2": {"review_history": make_review_history([3, 3, 3])},
        "card-3": {"review_history": make_review_history([4, 5, 5]), "retired": False},
    })
    f.write_weak_spots([])

    r = f.run()
    assert_eq("flat grades fires", True, r["rules"]["flat_grades"])
    assert_eq("2 flat cards", 2, len(r["flat_grade_cards"]))
    assert_eq("mode is application_scenario", "application_scenario", r["recommended_mode"])

# --- Retired cards are skipped ---
print()
print("  [retired cards ignored]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([])
    f.write_srs({
        "card-1": {"review_history": make_review_history([2, 2, 2]), "retired": True},
    })
    f.write_weak_spots([])

    r = f.run()
    assert_eq("retired card not flagged", False, r["rules"]["flat_grades"])

# --- Mode staleness ---
print()
print("  [mode staleness]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([
        {"id": "1", "type": "—", "reviews": "5", "file": "session-01.md"},
        {"id": "2", "type": "—", "reviews": "8", "file": "session-02.md"},
        {"id": "3", "type": "—", "reviews": "6", "file": "session-03.md"},
        {"id": "4", "type": "—", "reviews": "4", "file": "session-04.md"},
        {"id": "5", "type": "—", "reviews": "7", "file": "session-05.md"},
    ])
    f.write_srs({})
    f.write_weak_spots([])

    r = f.run()
    assert_eq("mode staleness fires", True, r["rules"]["mode_staleness"])
    assert_eq("5 consecutive recall sessions", 5, r["consecutive_recall_sessions"])
    assert_eq("mode is teach_back", "teach_back", r["recommended_mode"])

# --- Mode staleness broken by deep session ---
print()
print("  [staleness broken by deep]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([
        {"id": "1", "type": "—", "reviews": "5", "file": "session-01.md"},
        {"id": "2", "type": "—", "reviews": "8", "file": "session-02.md"},
        {"id": "3", "type": "deep", "reviews": "0", "file": "session-03.md"},
        {"id": "4", "type": "—", "reviews": "4", "file": "session-04.md"},
        {"id": "5", "type": "—", "reviews": "7", "file": "session-05.md"},
    ])
    f.write_srs({})
    f.write_weak_spots([])

    r = f.run()
    assert_eq("staleness count is 2 (broken by deep)", 2, r["consecutive_recall_sessions"])
    assert_eq("staleness does not fire", False, r["rules"]["mode_staleness"])

# --- Threshold overrides ---
print()
print("  [threshold overrides]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([
        {"id": "1", "type": "—", "reviews": "5", "file": "session-01.md"},
        {"id": "2", "type": "—", "reviews": "8", "file": "session-02.md"},
        {"id": "3", "type": "—", "reviews": "6", "file": "session-03.md"},
    ])
    f.write_srs({})
    f.write_weak_spots([])

    # Default threshold is 4, so 3 sessions shouldn't fire
    r = f.run()
    assert_eq("3 sessions below default threshold", False, r["rules"]["mode_staleness"])

    # Override threshold to 2
    r = f.run(extra_args=["--mode-staleness-threshold", "2"])
    assert_eq("3 sessions above overridden threshold", True, r["rules"]["mode_staleness"])

# --- All three rules fire → PLATEAU_LIKELY + interleaved ---
print()
print("  [all rules fire]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([
        {"id": "1", "type": "—", "reviews": "5", "file": "session-01.md"},
        {"id": "2", "type": "—", "reviews": "8", "file": "session-02.md"},
        {"id": "3", "type": "—", "reviews": "6", "file": "session-03.md"},
        {"id": "4", "type": "—", "reviews": "4", "file": "session-04.md"},
        {"id": "5", "type": "—", "reviews": "7", "file": "session-05.md"},
    ])
    f.write_srs({
        "card-1": {"review_history": make_review_history([2, 2, 3])},
    })
    f.write_weak_spots([{
        "id": "WS-1",
        "desc": "test",
        "cards": [],
        "sessions": ["S1", "S2", "S3", "S4"],
        "first": "S1",
        "last": "S4",
        "status": "active",
    }])

    r = f.run()
    assert_eq("all three rules fire", True, all(r["rules"].values()))
    assert_eq("plateau likely", "PLATEAU_LIKELY", r["signal"])
    assert_eq("interleaved mode", "interleaved_application", r["recommended_mode"])
    assert_eq("reason mentions 3 signals", True, "3 signal(s)" in r["reason"])

# --- Empty artifacts → no plateau ---
print()
print("  [empty artifacts]")

with tempfile.TemporaryDirectory() as tmpdir:
    f = Fixtures(tmpdir)
    f.write_journal_index([])
    f.write_srs({})
    f.write_weak_spots([])

    r = f.run()
    assert_eq("empty artifacts: no plateau", "NO_PLATEAU_DETECTED", r["signal"])
    assert_eq("empty artifacts: standard mode", "standard", r["recommended_mode"])


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print()
print("─────────────────────────")
print(f"Passed: {PASS}  Failed: {FAIL}")

if FAIL > 0:
    sys.exit(1)
