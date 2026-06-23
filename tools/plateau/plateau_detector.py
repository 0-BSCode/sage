#!/usr/bin/env python3
"""Deterministic plateau detector for the Sage system.

Analyzes learning artifacts to detect learning plateaus and recommend
session mode changes. Outputs JSON to stdout.

Usage:
    python3 plateau_detector.py \
      --journal-dir learning/journal/ \
      --srs learning/cards.srs.json \
      --weak-spots learning/weak-spots.md

Optional threshold overrides:
    --stale-ws-threshold N         (default: 3)
    --flat-grade-window N          (default: 3)
    --flat-grade-threshold F       (default: 3.5)
    --mode-staleness-threshold N   (default: 4)
    --plateau-min-rules N          (default: 2)

Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

THRESHOLDS = {
    "stale_ws_sessions": 3,
    "flat_grade_window": 3,
    "flat_grade_threshold": 3.5,
    "mode_staleness_sessions": 4,
    "plateau_signal_min_rules": 2,
}

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_weak_spots(ws_path: Path) -> List[Dict[str, Any]]:
    """Parse weak spot entries from weak-spots.md.

    Expects heading-based format:
    ## WS-[N] — [description]
    **Category:** ...
    **Session:** ...
    **Last tested:** S[N]
    **Cards:** ...
    **Status:** ...
    ### History
    - **S[N]:** ...
    """
    if not ws_path.exists():
        return []

    text = ws_path.read_text(encoding="utf-8")
    heading_re = re.compile(r"^##\s+WS-?(\d+)\s*[—–\-:]\s*(.+)$")
    field_re = re.compile(r"^\*\*(.+?)(?:\*\*:\s*|\*\*\s*:\s*|:\*\*\s*)(.*)$")
    history_re = re.compile(r"^-\s+\*\*S(\d+).*?:\*\*\s*(.*)$")

    weak_spots = []
    current: Optional[Dict[str, Any]] = None
    in_history = False

    for line in text.split("\n"):
        stripped = line.strip()

        m = heading_re.match(stripped)
        if m:
            if current:
                weak_spots.append(current)
            current = {
                "id": f"WS-{m.group(1)}",
                "number": int(m.group(1)),
                "description": m.group(2).strip(),
                "fields": {},
                "history_sessions": [],
            }
            in_history = False
            continue

        if current is None:
            continue

        if re.match(r"^###\s+History", stripped, re.IGNORECASE):
            in_history = True
            continue

        if in_history:
            hm = history_re.match(stripped)
            if hm:
                current["history_sessions"].append(int(hm.group(1)))
            continue

        fm = field_re.match(stripped)
        if fm:
            current["fields"][fm.group(1).strip()] = fm.group(2).strip()

    if current:
        weak_spots.append(current)

    # Convert to the format detect_stale_weak_spots expects
    result = []
    for ws in weak_spots:
        fields = ws["fields"]
        status = fields.get("Status", "active")

        cards_raw = fields.get("Cards", "")
        cards = []
        if cards_raw and cards_raw != "—":
            cards = [f"card-{n}" for n in re.findall(r"\d+", cards_raw)]

        session_str = fields.get("Session", "")
        session_match = re.match(r"(\d+)", session_str)
        first_seen = f"S{session_match.group(1)}" if session_match else "?"

        last_tested = fields.get("Last tested", first_seen)

        # Sessions active = count of unique sessions in History
        history_sessions = ws["history_sessions"]
        sessions_active = len(history_sessions) if history_sessions else 1

        result.append({
            "id": ws["id"],
            "description": ws["description"],
            "category": fields.get("Category", ""),
            "cards": cards,
            "first_seen": first_seen,
            "last_seen": last_tested,
            "sessions": [str(s) for s in history_sessions],
            "sessions_active": sessions_active,
            "related_concepts": fields.get("Concepts", ""),
            "status": status,
        })

    return result


def parse_srs_cards(srs_path: Path) -> Dict[str, Dict[str, Any]]:
    """Parse cards.srs.json. Returns dict keyed by card ID."""
    data = json.loads(srs_path.read_text(encoding="utf-8"))
    return data.get("cards", {})


def parse_journal_index(journal_dir: Path) -> List[Dict[str, Any]]:
    """Parse journal/index.md into list of session dicts.

    Returns list of dicts with keys: session_id, date, type, focus,
    reviews, avg_grade, file.
    """
    index_path = journal_dir / "index.md"
    if not index_path.exists():
        return []

    text = index_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    sessions = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # Skip header and separator
        if "#" in stripped and "Date" in stripped:
            continue
        if re.match(r"^\|[\s\-:|]+\|$", stripped):
            continue

        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 8:
            continue

        session_id = cells[0].strip()
        reviews_raw = cells[4].strip()
        reviews = None
        if reviews_raw and reviews_raw != "—":
            try:
                reviews = int(reviews_raw)
            except ValueError:
                pass

        sessions.append({
            "session_id": session_id,
            "date": cells[1].strip(),
            "type": cells[2].strip(),
            "focus": cells[3].strip(),
            "reviews": reviews,
            "avg_grade": cells[5].strip(),
            "file": cells[7].strip(),
        })

    return sessions


def parse_session_mode(journal_dir: Path, filename: str) -> Optional[str]:
    """Try to read session_mode from a session file's frontmatter."""
    session_path = journal_dir / filename
    if not session_path.exists():
        return None

    text = session_path.read_text(encoding="utf-8")
    match = re.search(r"session_mode:\s*(\S+)", text)
    if match:
        return match.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Detection Rules
# ---------------------------------------------------------------------------

def detect_stale_weak_spots(
    weak_spots: List[Dict[str, Any]],
    cards: Dict[str, Dict[str, Any]],
    thresholds: Dict[str, Any],
) -> Tuple[bool, List[Dict[str, Any]]]:
    """Rule 1: Flag active weak spots that have persisted too many sessions
    with flat or declining card grades."""

    threshold = thresholds["stale_ws_sessions"]
    grade_window = thresholds["flat_grade_window"]
    grade_threshold = thresholds["flat_grade_threshold"]
    stale = []

    for ws in weak_spots:
        # Skip resolved weak spots
        if "resolved" in ws["status"].lower():
            continue

        if ws["sessions_active"] <= threshold:
            continue

        # Check associated card grades
        recent_grades = []
        grade_trend = "unknown"

        for card_id in ws["cards"]:
            card = cards.get(card_id)
            if not card:
                continue
            history = card.get("review_history", [])
            if len(history) >= grade_window:
                grades = [r["quality"] for r in history[-grade_window:]]
                recent_grades.extend(grades)

        if recent_grades:
            avg = sum(recent_grades) / len(recent_grades)
            grade_range = max(recent_grades) - min(recent_grades)
            if avg < grade_threshold and grade_range <= 1:
                grade_trend = "flat"
            elif max(recent_grades) < grade_threshold:
                grade_trend = "declining"
            else:
                grade_trend = "improving"

            # Only flag if trend is flat or declining
            if grade_trend in ("flat", "declining"):
                stale.append({
                    "id": ws["id"],
                    "sessions_active": ws["sessions_active"],
                    "associated_cards": ws["cards"],
                    "recent_grades": recent_grades,
                    "grade_trend": grade_trend,
                })
        else:
            # No card data — flag on session count alone
            stale.append({
                "id": ws["id"],
                "sessions_active": ws["sessions_active"],
                "associated_cards": ws["cards"],
                "recent_grades": [],
                "grade_trend": "no_card_data",
            })

    fired = len(stale) > 0
    return fired, stale


def detect_flat_grades(
    cards: Dict[str, Dict[str, Any]],
    thresholds: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Rule 2: Flag cards with flat grade trends."""

    window = thresholds["flat_grade_window"]
    threshold = thresholds["flat_grade_threshold"]
    flat_cards = []

    for card_id, card in cards.items():
        if card.get("retired", False):
            continue

        history = card.get("review_history", [])
        if len(history) < window:
            continue

        grades = [r["quality"] for r in history[-window:]]
        avg = sum(grades) / len(grades)
        grade_range = max(grades) - min(grades)

        # Flat: average below threshold AND all grades within 1 point
        if avg < threshold and grade_range <= 1:
            flat_cards.append(card_id)

    fired = len(flat_cards) > 0
    return fired, flat_cards


def classify_session_mode(
    session: Dict[str, Any],
    journal_dir: Path,
) -> str:
    """Classify a journal index row as 'recall' or 'non-recall'.

    Priority:
    1. If the session file has a session_mode field, use it.
    2. Otherwise, use heuristic: deep = non-recall,
       quick/— with reviews = recall, — without reviews = non-recall.
    """
    # Try frontmatter first
    file_mode = parse_session_mode(journal_dir, session.get("file", ""))
    if file_mode:
        return file_mode

    # Heuristic fallback
    session_type = session.get("type", "—")
    has_reviews = session.get("reviews") is not None and session.get("reviews", 0) > 0

    if session_type == "deep":
        return "deep"
    if has_reviews:
        return "recall"
    return "deep"


def detect_mode_staleness(
    sessions: List[Dict[str, Any]],
    journal_dir: Path,
    thresholds: Dict[str, Any],
) -> Tuple[bool, int]:
    """Rule 3: Count consecutive recall sessions from most recent backward."""

    threshold = thresholds["mode_staleness_sessions"]
    consecutive = 0

    for session in reversed(sessions):
        mode = classify_session_mode(session, journal_dir)
        if mode in ("recall", "mixed"):
            consecutive += 1
        else:
            break

    fired = consecutive > threshold
    return fired, consecutive


# ---------------------------------------------------------------------------
# Signal & Mode Selection
# ---------------------------------------------------------------------------

def select_mode(stale_ws: bool, flat_grades: bool, mode_staleness: bool) -> str:
    """Deterministic mode selection based on which rules fired."""
    signals = sum([stale_ws, flat_grades, mode_staleness])

    if signals >= 2:
        return "interleaved_application"

    if stale_ws:
        return "targeted_redesign"
    if flat_grades:
        return "application_scenario"
    if mode_staleness:
        return "teach_back"

    return "standard"


def select_candidate_modes(stale_ws: bool, flat_grades: bool, mode_staleness: bool) -> List[str]:
    """Return all candidate modes, including visual_demo when stale weak spots exist.

    visual_demo is a candidate whenever stale_ws fires — the coach asks the
    learner whether a demo would help before generating one.
    """
    candidates = []
    primary = select_mode(stale_ws, flat_grades, mode_staleness)
    candidates.append(primary)

    # visual_demo is always a candidate when stale weak spots exist,
    # regardless of what other modes fired
    if stale_ws and "visual_demo" not in candidates:
        candidates.append("visual_demo")

    return candidates


def build_reason(
    stale_ws: bool,
    stale_ws_data: List[Dict[str, Any]],
    flat_grades: bool,
    flat_grade_cards: List[str],
    mode_staleness: bool,
    consecutive_sessions: int,
) -> str:
    """Build a human-readable reason string."""
    parts = []
    signal_count = sum([stale_ws, flat_grades, mode_staleness])

    if stale_ws:
        ws_ids = ", ".join(d["id"] for d in stale_ws_data)
        parts.append(f"stale weak spots ({ws_ids})")
    if flat_grades:
        parts.append(f"flat grades ({len(flat_grade_cards)} cards)")
    if mode_staleness:
        parts.append(f"mode staleness ({consecutive_sessions} consecutive recall sessions)")

    if not parts:
        return "No plateau signals detected"

    return f"{signal_count} signal(s) fired: {', '.join(parts)}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_detection(
    journal_dir: Path,
    srs_path: Path,
    ws_path: Path,
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """Run all detection rules and return the result dict."""

    # Parse artifacts
    weak_spots = parse_weak_spots(ws_path)
    cards = parse_srs_cards(srs_path)
    sessions = parse_journal_index(journal_dir)

    # Run rules
    stale_ws, stale_ws_data = detect_stale_weak_spots(weak_spots, cards, thresholds)
    flat_grades, flat_grade_cards = detect_flat_grades(cards, thresholds)
    mode_staleness, consecutive = detect_mode_staleness(sessions, journal_dir, thresholds)

    # Signal
    signal_count = sum([stale_ws, flat_grades, mode_staleness])
    signal = "PLATEAU_LIKELY" if signal_count >= thresholds["plateau_signal_min_rules"] else "NO_PLATEAU_DETECTED"

    # Mode
    recommended_mode = select_mode(stale_ws, flat_grades, mode_staleness)
    candidate_modes = select_candidate_modes(stale_ws, flat_grades, mode_staleness)

    # Reason
    reason = build_reason(stale_ws, stale_ws_data, flat_grades, flat_grade_cards, mode_staleness, consecutive)

    return {
        "signal": signal,
        "rules": {
            "stale_weak_spots": stale_ws,
            "flat_grades": flat_grades,
            "mode_staleness": mode_staleness,
        },
        "stale_weak_spots": stale_ws_data,
        "flat_grade_cards": flat_grade_cards,
        "consecutive_recall_sessions": consecutive,
        "recommended_mode": recommended_mode,
        "candidate_modes": candidate_modes,
        "reason": reason,
        "thresholds_used": thresholds,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic plateau detector for Sage"
    )
    parser.add_argument(
        "--journal-dir", required=True,
        help="Path to journal/ directory containing index.md and session files"
    )
    parser.add_argument(
        "--srs", required=True,
        help="Path to cards.srs.json"
    )
    parser.add_argument(
        "--weak-spots", required=True,
        help="Path to weak-spots.md"
    )
    parser.add_argument("--stale-ws-threshold", type=int, default=None)
    parser.add_argument("--flat-grade-window", type=int, default=None)
    parser.add_argument("--flat-grade-threshold", type=float, default=None)
    parser.add_argument("--mode-staleness-threshold", type=int, default=None)
    parser.add_argument("--plateau-min-rules", type=int, default=None)

    args = parser.parse_args()

    # Build thresholds with overrides
    thresholds = dict(THRESHOLDS)
    if args.stale_ws_threshold is not None:
        thresholds["stale_ws_sessions"] = args.stale_ws_threshold
    if args.flat_grade_window is not None:
        thresholds["flat_grade_window"] = args.flat_grade_window
    if args.flat_grade_threshold is not None:
        thresholds["flat_grade_threshold"] = args.flat_grade_threshold
    if args.mode_staleness_threshold is not None:
        thresholds["mode_staleness_sessions"] = args.mode_staleness_threshold
    if args.plateau_min_rules is not None:
        thresholds["plateau_signal_min_rules"] = args.plateau_min_rules

    journal_dir = Path(args.journal_dir)
    srs_path = Path(args.srs)
    ws_path = Path(args.weak_spots)

    # Validate paths
    errors = []
    if not journal_dir.is_dir():
        errors.append(f"Journal directory not found: {journal_dir}")
    if not srs_path.is_file():
        errors.append(f"SRS file not found: {srs_path}")
    if not ws_path.is_file():
        errors.append(f"Weak spots file not found: {ws_path}")

    if errors:
        for e in errors:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    result = run_detection(journal_dir, srs_path, ws_path, thresholds)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
