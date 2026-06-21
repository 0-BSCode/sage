#!/usr/bin/env python3
"""Coach effectiveness metrics for the ultralearning system.

Computes 4 core metrics from learning artifacts:
  1. Time-to-solid (avg sessions from introduced → solid)
  2. Review efficiency (% of reviews scoring 4-5)
  3. Regression rate (% of solid concepts that regressed)
  4. Mastery velocity trend (is time-to-solid improving?)

Commands:
    snapshot <path>                  Compute metrics, write history + dashboard
    trends <path>                   Analyze metric trends from history
    compare <path1> <path2>         Compare metrics across two projects

Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _find_concept_table_ranges(lines: List[str]) -> List[Tuple[int, int]]:
    """Find line ranges of concept tables (tables with 'Concept' as first header cell).

    Returns list of (first_data_row, last_data_row) pairs.
    """
    ranges: List[Tuple[int, int]] = []
    i = 0
    while i < len(lines):
        if not lines[i].strip().startswith("|"):
            i += 1
            continue
        cells = [c.strip() for c in lines[i].strip().split("|")[1:-1]]
        if len(cells) >= 4 and cells[0].lower() == "concept" and cells[1].lower() == "status":
            # Found a concept table header — skip separator, collect data rows
            if i + 1 < len(lines) and "---" in lines[i + 1]:
                start = i + 2
                end = start
                while end < len(lines) and lines[end].strip().startswith("|"):
                    end += 1
                if end > start:
                    ranges.append((start, end - 1))
                i = end
                continue
        i += 1
    return ranges


def parse_introduced_column(path: Path) -> Dict[str, int]:
    """Parse knowledge-map.md concepts table. Returns {concept_lower: introduced_session}.

    Only reads rows from tables with 'Concept' as the first header cell.
    Reads the Introduced column (S<N> format). Skips concepts with 'prior'.
    """
    kmap = path / "knowledge-map.md"
    if not kmap.exists():
        return {}

    text = kmap.read_text(encoding="utf-8")
    lines = text.split("\n")
    result: Dict[str, int] = {}

    for start, end in _find_concept_table_ranges(lines):
        for i in range(start, end + 1):
            cells = [c.strip() for c in lines[i].strip().split("|")[1:-1]]
            if len(cells) < 5:
                continue

            concept = cells[0]
            introduced = cells[2].strip()
            m = re.match(r"^S(\d+)$", introduced, re.IGNORECASE)
            if m:
                result[concept.lower()] = int(m.group(1))

    return result


def parse_concept_statuses(path: Path) -> Dict[str, str]:
    """Parse knowledge-map.md concepts table. Returns {concept_lower: status_lower}.

    Only reads rows from tables with 'Concept' as the first header cell.
    """
    kmap = path / "knowledge-map.md"
    if not kmap.exists():
        return {}

    text = kmap.read_text(encoding="utf-8")
    lines = text.split("\n")
    result: Dict[str, str] = {}

    for start, end in _find_concept_table_ranges(lines):
        for i in range(start, end + 1):
            cells = [c.strip() for c in lines[i].strip().split("|")[1:-1]]
            if len(cells) < 4:
                continue
            result[cells[0].lower()] = cells[1].lower()

    return result


def parse_changelog_solid_sessions(path: Path) -> Dict[str, int]:
    """Parse Status Changelog for first time each concept reached solid.

    Returns {concept_lower: session_number}.
    """
    kmap = path / "knowledge-map.md"
    if not kmap.exists():
        return {}

    text = kmap.read_text(encoding="utf-8")
    lines = text.split("\n")
    result: Dict[str, int] = {}

    in_changelog = False
    for line in lines:
        if re.match(r"^##\s+Status\s+Changelog\s*$", line.strip(), re.IGNORECASE):
            in_changelog = True
            continue
        if in_changelog and line.strip().startswith("## "):
            break
        if not in_changelog:
            continue

        cells = [c.strip() for c in line.strip().split("|")[1:-1]]
        if len(cells) < 4:
            continue
        if cells[0].lower() == "date" or "---" in cells[0]:
            continue

        # Handle both formats:
        #   5-col: Date | Concept | From | To | Session
        #   4-col: Date | Concept | From → To | Session
        concept = cells[1].strip().lower()
        session_str = cells[-1].strip()

        if len(cells) >= 5:
            to_status = cells[3].strip().lower()
        else:
            # 4-col: parse "From → To" cell
            arrow_cell = cells[2]
            parts = re.split(r"\s*→\s*", arrow_cell)
            to_status = parts[-1].strip().lower() if parts else ""

        if to_status != "solid":
            continue

        m = re.match(r"(\d+)", session_str)
        if not m:
            continue

        session_num = int(m.group(1))
        if concept not in result or session_num < result[concept]:
            result[concept] = session_num

    return result


def parse_changelog_regressions(path: Path) -> List[Dict[str, Any]]:
    """Find concepts that regressed from solid to a lower status.

    Returns list of {concept, from_session, to_session} dicts.
    """
    kmap = path / "knowledge-map.md"
    if not kmap.exists():
        return []

    text = kmap.read_text(encoding="utf-8")
    lines = text.split("\n")
    regressions: List[Dict[str, Any]] = []
    seen_concepts: set = set()

    in_changelog = False
    for line in lines:
        if re.match(r"^##\s+Status\s+Changelog\s*$", line.strip(), re.IGNORECASE):
            in_changelog = True
            continue
        if in_changelog and line.strip().startswith("## "):
            break
        if not in_changelog:
            continue

        cells = [c.strip() for c in line.strip().split("|")[1:-1]]
        if len(cells) < 4:
            continue
        if cells[0].lower() == "date" or "---" in cells[0]:
            continue

        concept = cells[1].strip()
        session_str = cells[-1].strip()

        if len(cells) >= 5:
            from_status = cells[2].strip().lower()
            to_status = cells[3].strip().lower()
        else:
            arrow_cell = cells[2]
            parts = re.split(r"\s*→\s*", arrow_cell)
            from_status = parts[0].strip().lower() if len(parts) >= 2 else ""
            to_status = parts[-1].strip().lower() if parts else ""

        if from_status != "solid":
            continue
        if to_status in ("solid", "mastered"):
            continue

        m = re.match(r"(\d+)", session_str)
        session_num = int(m.group(1)) if m else 0

        concept_lower = concept.lower()
        if concept_lower not in seen_concepts:
            seen_concepts.add(concept_lower)
            regressions.append({
                "concept": concept,
                "to_session": session_num,
            })

    return regressions


def parse_review_history(path: Path) -> List[Dict[str, Any]]:
    """Parse cards.srs.json review_history entries. Returns flat list of reviews."""
    srs_path = path / "cards.srs.json"
    if not srs_path.exists():
        return []

    data = json.loads(srs_path.read_text(encoding="utf-8"))
    reviews: List[Dict[str, Any]] = []

    for card_id, card in data.get("cards", {}).items():
        if card.get("retired", False):
            continue
        for entry in card.get("review_history", []):
            reviews.append(entry)

    return reviews


def parse_current_session(path: Path) -> int:
    """Determine current session number from journal/index.md."""
    index = path / "journal" / "index.md"
    if not index.exists():
        return 0

    text = index.read_text(encoding="utf-8")
    max_session = 0
    for line in text.split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().split("|")[1:-1]]
        if not cells or cells[0] == "#" or "---" in cells[0]:
            continue
        m = re.match(r"(\d+)", cells[0])
        if m:
            max_session = max(max_session, int(m.group(1)))

    return max_session


# ---------------------------------------------------------------------------
# Metric computations
# ---------------------------------------------------------------------------

def compute_time_to_solid(introduced: Dict[str, int],
                          solid_sessions: Dict[str, int]) -> Tuple[Optional[float], List[int]]:
    """Compute average time-to-solid and individual values.

    Uses the FIRST time a concept reached solid (if it regressed and recovered,
    the first solid is used).
    """
    values: List[Tuple[int, int]] = []  # (solid_session, tts_value) for ordering

    for concept, intro_session in introduced.items():
        if concept in solid_sessions:
            solid_session = solid_sessions[concept]
            tts = solid_session - intro_session
            if tts >= 0:
                values.append((solid_session, tts))

    if not values:
        return None, []

    values.sort(key=lambda x: x[0])
    tts_values = [v[1] for v in values]
    avg = sum(tts_values) / len(tts_values)
    return round(avg, 2), tts_values


def compute_review_efficiency(reviews: List[Dict[str, Any]]) -> Tuple[Optional[float], Dict[str, float]]:
    """Compute overall review efficiency and per-date breakdown."""
    if not reviews:
        return None, {}

    total = len(reviews)
    good = sum(1 for r in reviews if r.get("quality", 0) >= 4)
    overall = round(good / total, 4)

    by_date: Dict[str, List[int]] = {}
    for r in reviews:
        d = r.get("date", "unknown")
        by_date.setdefault(d, []).append(r.get("quality", 0))

    efficiency_by_date = {}
    for d, qualities in sorted(by_date.items()):
        if qualities:
            efficiency_by_date[d] = round(sum(1 for q in qualities if q >= 4) / len(qualities), 4)

    return overall, efficiency_by_date


def compute_regression_rate(statuses: Dict[str, str],
                            solid_sessions: Dict[str, int],
                            regressions: List[Dict[str, Any]]) -> Tuple[Optional[float], List[Dict]]:
    """Compute regression rate: % of ever-solid concepts that regressed."""
    ever_solid = set(solid_sessions.keys())
    # Also include currently solid/mastered concepts that may not have changelog entries
    for concept, status in statuses.items():
        if status in ("solid", "mastered"):
            ever_solid.add(concept)

    if not ever_solid:
        return None, regressions

    regressed = set(r["concept"].lower() for r in regressions)
    rate = round(len(regressed) / len(ever_solid), 4) if ever_solid else 0
    return rate, regressions


def compute_mastery_velocity(tts_values: List[int]) -> Tuple[Optional[str], Optional[float]]:
    """Compute mastery velocity trend from TTS values.

    Needs at least 5 values. Computes linear regression slope over the last 10.
    """
    if len(tts_values) < 5:
        return None, None

    recent = tts_values[-10:]
    n = len(recent)
    x = list(range(n))

    x_mean = sum(x) / n
    y_mean = sum(recent) / n
    numerator = sum((x[i] - x_mean) * (recent[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "stable", 0.0

    slope = round(numerator / denominator, 4)

    if slope < -0.1:
        direction = "improving"
    elif slope > 0.1:
        direction = "degrading"
    else:
        direction = "stable"

    return direction, slope


# ---------------------------------------------------------------------------
# Threshold flags
# ---------------------------------------------------------------------------

THRESHOLDS = [
    ("time_to_solid_avg", 6.0, "gt",
     "Teaching too slow — consider switching to example-first or application-based teaching"),
    ("review_efficiency", 0.60, "lt",
     "Review strategy may need adjustment — consider more interleaving"),
    ("regression_rate", 0.15, "gt",
     "Concepts regressing — tighten solid promotion criteria"),
]


def compute_flags(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check metrics against thresholds and return flags."""
    flags: List[Dict[str, Any]] = []

    for metric_key, threshold, comparator, message in THRESHOLDS:
        value = metrics.get(metric_key)
        if value is None:
            continue

        if comparator == "gt":
            triggered = value > threshold
        else:
            triggered = value < threshold

        flags.append({
            "metric": metric_key,
            "value": value,
            "threshold": threshold,
            "status": "warning" if triggered else "ok",
            "message": message if triggered else None,
        })

    # Mastery velocity flag
    slope = metrics.get("mastery_velocity_slope")
    if slope is not None and slope > 0:
        flags.append({
            "metric": "mastery_velocity_slope",
            "value": slope,
            "threshold": 0,
            "status": "warning",
            "message": "Coach is getting slower — review recent session changes",
        })
    elif slope is not None:
        flags.append({
            "metric": "mastery_velocity_slope",
            "value": slope,
            "threshold": 0,
            "status": "ok",
            "message": None,
        })

    return flags


# ---------------------------------------------------------------------------
# Dashboard writer
# ---------------------------------------------------------------------------

def write_dashboard(metrics_dir: Path, session: int, metrics: Dict, flags: List[Dict]) -> None:
    """Write metrics/dashboard.md (human-readable, overwritten each time)."""
    today = date.today().isoformat()

    lines = [
        "# Coach Effectiveness Dashboard",
        f"**Last updated**: Session {session} ({today})",
        "",
        "## Core Metrics",
    ]

    tts = metrics.get("time_to_solid_avg")
    lines.append(f"- Time-to-solid (avg): {tts if tts is not None else 'insufficient data'}"
                 f"{' sessions' if tts is not None else ''}")

    eff = metrics.get("review_efficiency")
    if eff is not None:
        lines.append(f"- Review efficiency: {round(eff * 100)}% (grade 4-5)")
    else:
        lines.append("- Review efficiency: no review data")

    reg = metrics.get("regression_rate")
    if reg is not None:
        solid_count = metrics.get("concepts_at_solid", 0) + metrics.get("concepts_at_mastered", 0)
        reg_count = len(metrics.get("regressions", []))
        lines.append(f"- Regression rate: {round(reg * 100)}% ({reg_count}/{solid_count} solid concepts regressed)")
    else:
        lines.append("- Regression rate: insufficient data")

    vel = metrics.get("mastery_velocity_trend")
    slope = metrics.get("mastery_velocity_slope")
    if vel is not None:
        lines.append(f"- Mastery velocity trend: {vel} (slope {slope} sessions/concept over last 10)")
    else:
        lines.append("- Mastery velocity trend: insufficient data (need 5+ concepts at solid)")

    lines.append("")
    lines.append("## Flags")

    warnings = [f for f in flags if f["status"] == "warning"]
    oks = [f for f in flags if f["status"] == "ok"]

    if warnings:
        for f in warnings:
            lines.append(f"- ⚠ {f['message']}")
    if oks:
        for f in oks:
            lines.append(f"- ✓ {f['metric']}: {f['value']} (threshold: {f['threshold']})")
    if not flags:
        lines.append("- No metrics data to evaluate")

    lines.append("")

    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "dashboard.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_snapshot(path: Path) -> None:
    """Compute metrics snapshot, write to history.json and dashboard.md."""
    introduced = parse_introduced_column(path)
    statuses = parse_concept_statuses(path)
    solid_sessions = parse_changelog_solid_sessions(path)
    regressions = parse_changelog_regressions(path)
    reviews = parse_review_history(path)
    session = parse_current_session(path)

    tts_avg, tts_values = compute_time_to_solid(introduced, solid_sessions)
    review_eff, review_by_date = compute_review_efficiency(reviews)
    reg_rate, reg_list = compute_regression_rate(statuses, solid_sessions, regressions)
    velocity_trend, velocity_slope = compute_mastery_velocity(tts_values)

    concepts_solid = sum(1 for s in statuses.values() if s == "solid")
    concepts_mastered = sum(1 for s in statuses.values() if s == "mastered")
    total_concepts = len(statuses)

    metrics = {
        "time_to_solid_avg": tts_avg,
        "time_to_solid_values": tts_values,
        "review_efficiency": review_eff,
        "review_efficiency_by_date": review_by_date,
        "regression_rate": reg_rate,
        "regressions": [{"concept": r["concept"], "to_session": r["to_session"]} for r in reg_list],
        "mastery_velocity_trend": velocity_trend,
        "mastery_velocity_slope": velocity_slope,
        "concepts_at_solid": concepts_solid,
        "concepts_at_mastered": concepts_mastered,
        "total_concepts": total_concepts,
    }

    flags = compute_flags(metrics)

    snapshot = {
        "session": session,
        "date": date.today().isoformat(),
        "metrics": metrics,
        "flags": flags,
    }

    # Write history
    metrics_dir = path / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    history_path = metrics_dir / "history.json"

    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))
    else:
        history = []

    history.append(snapshot)
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")

    # Write dashboard
    write_dashboard(metrics_dir, session, metrics, flags)

    # Output JSON to stdout
    print(json.dumps(snapshot, indent=2))


def cmd_trends(path: Path) -> None:
    """Analyze metric trends from history.json."""
    history_path = path / "metrics" / "history.json"
    if not history_path.exists():
        print(json.dumps({"message": "No metrics history found"}))
        return

    history = json.loads(history_path.read_text(encoding="utf-8"))
    if len(history) < 2:
        print(json.dumps({"message": "Insufficient history for trend analysis"}))
        return

    def trend_for(key: str) -> Dict[str, Any]:
        values = [s["metrics"].get(key) for s in history if s["metrics"].get(key) is not None]
        if len(values) < 2:
            return {"direction": "insufficient_data"}

        current = values[-1]
        previous = values[-2]
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        num = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((x[i] - x_mean) ** 2 for i in range(n))
        slope = round(num / den, 4) if den != 0 else 0.0

        if abs(slope) < 0.01:
            direction = "stable"
        elif slope > 0:
            direction = "improving" if key == "review_efficiency" else "degrading"
        else:
            direction = "degrading" if key == "review_efficiency" else "improving"

        return {
            "direction": direction,
            "current": current,
            "previous": previous,
            "slope": slope,
        }

    result = {
        "snapshots_analyzed": len(history),
        "trends": {
            "time_to_solid": trend_for("time_to_solid_avg"),
            "review_efficiency": trend_for("review_efficiency"),
            "regression_rate": trend_for("regression_rate"),
            "mastery_velocity": trend_for("mastery_velocity_slope"),
        },
        "flags": [],
    }

    print(json.dumps(result, indent=2))


def cmd_compare(path1: Path, path2: Path) -> None:
    """Compare coach effectiveness across two projects."""
    def project_metrics(path: Path) -> Dict[str, Any]:
        introduced = parse_introduced_column(path)
        statuses = parse_concept_statuses(path)
        solid_sessions = parse_changelog_solid_sessions(path)
        regressions = parse_changelog_regressions(path)
        reviews = parse_review_history(path)

        tts_avg, _ = compute_time_to_solid(introduced, solid_sessions)
        review_eff, _ = compute_review_efficiency(reviews)
        reg_rate, _ = compute_regression_rate(statuses, solid_sessions, regressions)

        return {
            "name": path.parent.name,
            "time_to_solid_avg": tts_avg,
            "review_efficiency": review_eff,
            "regression_rate": reg_rate,
        }

    m1 = project_metrics(path1)
    m2 = project_metrics(path2)

    def better(key: str, lower_is_better: bool) -> Optional[str]:
        v1, v2 = m1.get(key), m2.get(key)
        if v1 is None or v2 is None:
            return None
        if v1 == v2:
            return "tied"
        if lower_is_better:
            return m1["name"] if v1 < v2 else m2["name"]
        return m1["name"] if v1 > v2 else m2["name"]

    result = {
        "project_1": m1,
        "project_2": m2,
        "comparison": {
            "faster_mastery": better("time_to_solid_avg", lower_is_better=True),
            "better_retention": better("review_efficiency", lower_is_better=False),
            "fewer_regressions": better("regression_rate", lower_is_better=True),
        },
    }

    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_path(path_arg: str, require_kmap: bool = True) -> Path:
    p = Path(path_arg).expanduser()
    if p.name == "knowledge-map.md":
        p = p.parent
    if require_kmap:
        kmap = p / "knowledge-map.md"
        if not kmap.exists():
            basename = Path(p.parts[-1]) if len(p.parts) > 1 else p
            alt_kmap = basename / "knowledge-map.md"
            hint = f" Did you mean '{basename}'?" if alt_kmap.exists() else ""
            sys.exit(f"Error: '{kmap}' not found.{hint} (cwd: {Path.cwd()})")
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description="Coach effectiveness metrics")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_snap = subparsers.add_parser("snapshot", help="Compute metrics snapshot")
    p_snap.add_argument("path", help="Path to learning directory")

    p_trend = subparsers.add_parser("trends", help="Analyze metric trends")
    p_trend.add_argument("path", help="Path to learning directory")

    p_cmp = subparsers.add_parser("compare", help="Compare two projects")
    p_cmp.add_argument("path1", help="Path to first learning directory")
    p_cmp.add_argument("path2", help="Path to second learning directory")

    args = parser.parse_args()

    if args.command == "snapshot":
        cmd_snapshot(_resolve_path(args.path, require_kmap=False))
    elif args.command == "trends":
        cmd_trends(_resolve_path(args.path, require_kmap=False))
    elif args.command == "compare":
        cmd_compare(_resolve_path(args.path1), _resolve_path(args.path2))


if __name__ == "__main__":
    main()
