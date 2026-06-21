#!/usr/bin/env python3
"""SM-2 Spaced Repetition Scheduling Engine.

A standalone CLI tool that implements the SM-2 algorithm for per-card scheduling.
Reads cards.md, writes scheduling state to cards.srs.json sidecar.

Commands:
    init <path>                     Create cards.srs.json from cards.md
    sync <path>                     Add new cards, detect retired/edited
    due <path> [--date YYYY-MM-DD]  List cards due for review
    grade <path> <card-id> <q>      Grade a card (0-5), update schedule [--date YYYY-MM-DD]
    stats <path>                    Aggregate statistics
    forecast <path> [--days N]      What's due each day for next N days

All commands output markdown by default, --json for machine-readable output.
Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# SM-2 Algorithm
# ---------------------------------------------------------------------------

class SM2:
    """Stateless SM-2 algorithm. Takes card state + quality, returns new state."""

    DEFAULT_EF = 2.5
    MIN_EF = 1.3
    MAX_HISTORY = 30

    @staticmethod
    def review(card: Dict[str, Any], quality: int, review_date: str) -> Dict[str, Any]:
        """Apply SM-2 algorithm to a card state.

        Args:
            card: Current card state dict.
            quality: Grade 0-5.
            review_date: ISO date string (YYYY-MM-DD) of the review.

        Returns:
            Updated card state dict (new copy).
        """
        if not 0 <= quality <= 5:
            raise ValueError(f"Quality must be 0-5, got {quality}")

        c = {k: v for k, v in card.items()}  # shallow copy
        ef = c.get("easiness_factor", SM2.DEFAULT_EF)
        interval = c.get("interval", 0)
        reps = c.get("repetitions", 0)
        lapses = c.get("lapses", 0)

        # EF update (always applied)
        ef = max(SM2.MIN_EF, ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

        if quality >= 3:
            # Correct response
            if reps == 0:
                interval = 1
            elif reps == 1:
                interval = 6
            else:
                interval = round(interval * ef)
            reps += 1
            status = "review" if reps > 1 else "learning"
        else:
            # Lapse
            if c.get("status") in ("review", "relearning"):
                status = "relearning"
            else:
                status = "learning"
            reps = 0
            interval = 1
            lapses += 1

        next_review = (date.fromisoformat(review_date) + timedelta(days=interval)).isoformat()

        # Build review history entry
        history_entry = {
            "date": review_date,
            "quality": quality,
            "ef": round(ef, 4),
            "interval": interval,
        }
        history = list(c.get("review_history", []))
        history.append(history_entry)
        if len(history) > SM2.MAX_HISTORY:
            history = history[-SM2.MAX_HISTORY:]

        c.update({
            "easiness_factor": round(ef, 4),
            "interval": interval,
            "repetitions": reps,
            "lapses": lapses,
            "status": status,
            "last_review": review_date,
            "next_review": next_review,
            "review_history": history,
        })
        return c


# ---------------------------------------------------------------------------
# Card Parser — reads cards.md (read-only, never modifies the markdown)
# ---------------------------------------------------------------------------

class CardParser:
    """Parse cards.md into structured data."""

    CARD_HEADER_RE = re.compile(r"^###\s+Card\s+(\d+)\s*(\(Reverse\))?\s*(\[RETIRED\])?\s*$", re.IGNORECASE)

    @staticmethod
    def parse(text: str) -> List[Dict[str, Any]]:
        """Parse cards.md content into a list of card dicts.

        Returns:
            List of dicts with keys: number, card_id, question, answer, tags,
            is_reverse, is_retired, question_hash.
        """
        cards = []
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            match = CardParser.CARD_HEADER_RE.match(lines[i].strip())
            if match:
                number = int(match.group(1))
                is_reverse = match.group(2) is not None
                is_retired = match.group(3) is not None
                i += 1

                question_lines = []
                answer_lines = []
                tags_line = ""
                section = None

                while i < len(lines):
                    line = lines[i].strip()
                    if line.startswith("---") or CardParser.CARD_HEADER_RE.match(line):
                        break
                    if line.startswith("**Q:**") or line.startswith("**Q**:"):
                        section = "q"
                        prefix = "**Q:**" if line.startswith("**Q:**") else "**Q**:"
                        question_lines.append(line[len(prefix):].strip())
                    elif line.startswith("**A:**") or line.startswith("**A**:"):
                        section = "a"
                        prefix = "**A:**" if line.startswith("**A:**") else "**A**:"
                        answer_lines.append(line[len(prefix):].strip())
                    elif line.startswith("**Tags:**") or line.startswith("**Tags**:"):
                        prefix = "**Tags:**" if line.startswith("**Tags:**") else "**Tags**:"
                        tags_line = line[len(prefix):].strip()
                        section = None
                    elif section == "q" and line:
                        question_lines.append(line)
                    elif section == "a" and line:
                        answer_lines.append(line)
                    i += 1

                question = " ".join(question_lines).strip()
                answer = " ".join(answer_lines).strip()
                tags = [t.strip() for t in tags_line.split(",") if t.strip()] if tags_line else []

                question_hash = hashlib.sha256(question.encode()).hexdigest()[:8]

                cards.append({
                    "number": number,
                    "card_id": f"card-{number}",
                    "question": question,
                    "answer": answer,
                    "tags": tags,
                    "is_reverse": is_reverse,
                    "is_retired": is_retired,
                    "question_hash": question_hash,
                })
            else:
                i += 1

        return cards


# ---------------------------------------------------------------------------
# SRS Store — reads/writes cards.srs.json
# ---------------------------------------------------------------------------

class SRSStore:
    """Manages the cards.srs.json sidecar file."""

    VERSION = "1.0"
    ALGORITHM = "sm2"

    @staticmethod
    def srs_path(cards_md_path: Path) -> Path:
        """Derive the .srs.json path from the cards.md path."""
        return cards_md_path.with_suffix(".srs.json")

    @staticmethod
    def load(path: Path) -> Dict[str, Any]:
        """Load an existing SRS store."""
        with open(path, "r") as f:
            return json.load(f)

    @staticmethod
    def save(path: Path, data: Dict[str, Any]) -> None:
        """Save the SRS store."""
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    @staticmethod
    def create(cards: List[Dict[str, Any]], topic: str, today: str) -> Dict[str, Any]:
        """Create a new SRS store from parsed cards."""
        store = {
            "version": SRSStore.VERSION,
            "algorithm": SRSStore.ALGORITHM,
            "topic": topic,
            "created": today,
            "last_sync": today,
            "cards": {},
        }
        for card in cards:
            if card["is_retired"]:
                continue
            store["cards"][card["card_id"]] = SRSStore._new_card_state(card, today)
        return store

    @staticmethod
    def _new_card_state(card: Dict[str, Any], today: str) -> Dict[str, Any]:
        """Create default state for a new card."""
        return {
            "card_number": card["number"],
            "question_preview": card["question"][:50] + ("..." if len(card["question"]) > 50 else ""),
            "question_hash": card["question_hash"],
            "easiness_factor": SM2.DEFAULT_EF,
            "interval": 0,
            "repetitions": 0,
            "lapses": 0,
            "status": "new",
            "last_review": None,
            "next_review": today,
            "created": today,
            "retired": False,
            "review_history": [],
        }

    @staticmethod
    def sync(store: Dict[str, Any], cards: List[Dict[str, Any]], today: str) -> Dict[str, Any]:
        """Sync the store with current cards.md content.

        Returns dict with: added, retired, edited, orphaned counts and details.
        """
        report = {"added": [], "retired": [], "edited": [], "orphaned": []}
        existing_ids = set(store["cards"].keys())
        parsed_ids = set()

        for card in cards:
            cid = card["card_id"]
            parsed_ids.add(cid)

            if cid not in store["cards"]:
                # New card
                if not card["is_retired"]:
                    store["cards"][cid] = SRSStore._new_card_state(card, today)
                    report["added"].append(cid)
            else:
                # Existing card — check for changes
                sc = store["cards"][cid]

                # Retired?
                if card["is_retired"] and not sc.get("retired", False):
                    sc["retired"] = True
                    report["retired"].append(cid)

                # Edited?
                if card["question_hash"] != sc.get("question_hash"):
                    sc["question_hash"] = card["question_hash"]
                    sc["question_preview"] = card["question"][:50] + ("..." if len(card["question"]) > 50 else "")
                    report["edited"].append(cid)

        # Orphaned: in store but not in cards.md
        for cid in existing_ids - parsed_ids:
            if not store["cards"][cid].get("retired", False):
                report["orphaned"].append(cid)

        store["last_sync"] = today
        return report


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class MarkdownFormatter:
    """Format output as markdown."""

    @staticmethod
    def due_list(cards: List[Tuple[str, Dict[str, Any]]], today: str, answer_lookup: Optional[Dict[str, str]] = None) -> str:
        if not cards:
            return f"No cards due for review on {today}."
        if answer_lookup is None:
            answer_lookup = {}
        lines = [f"## Cards Due for Review ({today})", ""]
        new = [(cid, c) for cid, c in cards if c["status"] == "new"]
        overdue = [(cid, c) for cid, c in cards if c["status"] != "new" and c["next_review"] < today]
        due_today = [(cid, c) for cid, c in cards if c["status"] != "new" and c["next_review"] == today]

        if overdue:
            lines.append(f"### Overdue ({len(overdue)})")
            for cid, c in overdue:
                lines.append(f"- **{cid}**: {c['question_preview']} (due {c['next_review']}, {c['status']})")
                if cid in answer_lookup:
                    lines.append(f"  - **Expected:** {answer_lookup[cid]}")
            lines.append("")
        if due_today:
            lines.append(f"### Due Today ({len(due_today)})")
            for cid, c in due_today:
                lines.append(f"- **{cid}**: {c['question_preview']} ({c['status']})")
                if cid in answer_lookup:
                    lines.append(f"  - **Expected:** {answer_lookup[cid]}")
            lines.append("")
        if new:
            lines.append(f"### New Cards ({len(new)})")
            for cid, c in new:
                lines.append(f"- **{cid}**: {c['question_preview']}")
                if cid in answer_lookup:
                    lines.append(f"  - **Expected:** {answer_lookup[cid]}")
            lines.append("")

        lines.append(f"**Total: {len(cards)} cards to review**")
        return "\n".join(lines)

    @staticmethod
    def grade_result(card_id: str, card: Dict[str, Any], quality: int) -> str:
        lines = [
            f"## Graded: {card_id}",
            "",
            f"- **Quality:** {quality}/5",
            f"- **Status:** {card['status']}",
            f"- **EF:** {card['easiness_factor']:.2f}",
            f"- **Interval:** {card['interval']} day(s)",
            f"- **Next review:** {card['next_review']}",
            f"- **Repetitions:** {card['repetitions']}",
            f"- **Lapses:** {card['lapses']}",
        ]
        return "\n".join(lines)

    @staticmethod
    def stats(store: Dict[str, Any]) -> str:
        cards = store["cards"]
        total = len(cards)
        if total == 0:
            return "No cards in the deck."

        status_counts: Dict[str, int] = {}
        total_reviews = 0
        total_lapses = 0
        ef_sum = 0.0
        active = 0

        for c in cards.values():
            if c.get("retired"):
                status_counts["retired"] = status_counts.get("retired", 0) + 1
                continue
            active += 1
            s = c.get("status", "new")
            status_counts[s] = status_counts.get(s, 0) + 1
            total_reviews += len(c.get("review_history", []))
            total_lapses += c.get("lapses", 0)
            ef_sum += c.get("easiness_factor", SM2.DEFAULT_EF)

        avg_ef = ef_sum / active if active else 0

        lines = [
            f"## SRS Statistics: {store.get('topic', 'unknown')}",
            "",
            f"- **Total cards:** {total} ({active} active, {status_counts.get('retired', 0)} retired)",
            f"- **New:** {status_counts.get('new', 0)}",
            f"- **Learning:** {status_counts.get('learning', 0)}",
            f"- **Review:** {status_counts.get('review', 0)}",
            f"- **Relearning:** {status_counts.get('relearning', 0)}",
            f"- **Total reviews:** {total_reviews}",
            f"- **Total lapses:** {total_lapses}",
            f"- **Average EF:** {avg_ef:.2f}",
            f"- **Algorithm:** {store.get('algorithm', 'sm2')}",
            f"- **Created:** {store.get('created', '?')}",
            f"- **Last sync:** {store.get('last_sync', '?')}",
        ]
        return "\n".join(lines)

    @staticmethod
    def forecast(buckets: Dict[str, int], days: int) -> str:
        if not any(buckets.values()):
            return "No reviews scheduled in the forecast period."
        lines = [f"## Review Forecast (next {days} days)", ""]
        lines.append("| Date | Cards Due |")
        lines.append("|------|-----------|")
        for d, count in sorted(buckets.items()):
            bar = "#" * count
            lines.append(f"| {d} | {count} {bar} |")
        total = sum(buckets.values())
        lines.append("")
        lines.append(f"**Total: {total} reviews over {days} days** (avg {total / days:.1f}/day)")
        return "\n".join(lines)

    @staticmethod
    def init_result(count: int, path: str) -> str:
        return f"Initialized SRS store with {count} cards at `{path}`."

    @staticmethod
    def sync_report(report: Dict[str, List[str]]) -> str:
        lines = ["## Sync Report", ""]
        lines.append(f"- **Added:** {len(report['added'])}")
        lines.append(f"- **Retired:** {len(report['retired'])}")
        lines.append(f"- **Edited:** {len(report['edited'])}")
        lines.append(f"- **Orphaned:** {len(report['orphaned'])}")
        if report["added"]:
            lines.append(f"\nNew cards: {', '.join(report['added'])}")
        if report["edited"]:
            lines.append(f"\nEdited cards (question changed): {', '.join(report['edited'])}")
        if report["orphaned"]:
            lines.append(f"\nOrphaned (in store but not in cards.md): {', '.join(report['orphaned'])}")
        return "\n".join(lines)


class JsonFormatter:
    """Format output as JSON."""

    @staticmethod
    def output(data: Any) -> str:
        return json.dumps(data, indent=2, default=str)


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

def _resolve_paths(path_arg: str) -> Tuple[Path, Path]:
    """Resolve cards.md and cards.srs.json paths from a directory or file path."""
    p = Path(path_arg)
    if p.is_dir():
        cards_md = p / "cards.md"
    elif p.name == "cards.md":
        cards_md = p
    elif p.suffix == ".json":
        cards_md = p.with_suffix("").with_suffix(".md")  # cards.srs.json -> cards.md
    else:
        cards_md = p / "cards.md"

    srs_json = SRSStore.srs_path(cards_md)
    return cards_md, srs_json


def _derive_topic(cards_md: Path) -> str:
    """Derive topic slug from path: learning/<topic-slug>/cards.md -> topic-slug."""
    parts = cards_md.parts
    for i, part in enumerate(parts):
        if part == "learning" and i + 1 < len(parts):
            return parts[i + 1]
    return cards_md.parent.name or "unknown"


def _today() -> str:
    return date.today().isoformat()


def cmd_init(args: argparse.Namespace) -> str:
    cards_md, srs_json = _resolve_paths(args.path)

    if not cards_md.exists():
        return f"Error: {cards_md} not found."

    if srs_json.exists() and not getattr(args, "force", False):
        return f"Error: {srs_json} already exists. Use --force to overwrite."

    text = cards_md.read_text()
    cards = CardParser.parse(text)
    today = _today()
    topic = _derive_topic(cards_md)
    store = SRSStore.create(cards, topic, today)
    SRSStore.save(srs_json, store)

    active = len([c for c in cards if not c["is_retired"]])

    if args.json:
        return JsonFormatter.output({"action": "init", "cards": active, "path": str(srs_json)})
    return MarkdownFormatter.init_result(active, str(srs_json))


def cmd_sync(args: argparse.Namespace) -> str:
    cards_md, srs_json = _resolve_paths(args.path)

    if not cards_md.exists():
        return f"Error: {cards_md} not found."
    if not srs_json.exists():
        return f"Error: {srs_json} not found. Run `init` first."

    text = cards_md.read_text()
    cards = CardParser.parse(text)
    store = SRSStore.load(srs_json)
    report = SRSStore.sync(store, cards, _today())
    SRSStore.save(srs_json, store)

    if args.json:
        return JsonFormatter.output({"action": "sync", **{k: len(v) for k, v in report.items()}, "details": report})
    return MarkdownFormatter.sync_report(report)


def cmd_due(args: argparse.Namespace) -> str:
    cards_md, srs_json = _resolve_paths(args.path)

    if not srs_json.exists():
        return f"Error: {srs_json} not found. Run `init` first."

    store = SRSStore.load(srs_json)
    check_date = args.date if args.date else _today()

    # Build card_id -> answer lookup from cards.md
    answer_lookup: Dict[str, str] = {}
    if cards_md.exists():
        parsed = CardParser.parse(cards_md.read_text())
        for card in parsed:
            answer_lookup[card["card_id"]] = card["answer"]

    due_cards = []
    for cid, card in store["cards"].items():
        if card.get("retired", False):
            continue
        if card["next_review"] <= check_date:
            due_cards.append((cid, card))

    # Sort: overdue first (oldest), then new
    due_cards.sort(key=lambda x: (x[1]["status"] == "new", x[1]["next_review"]))

    if args.json:
        return JsonFormatter.output({
            "action": "due",
            "date": check_date,
            "count": len(due_cards),
            "cards": [{**c, "card_id": cid, "expected_answer": answer_lookup.get(cid, "")} for cid, c in due_cards],
        })
    return MarkdownFormatter.due_list(due_cards, check_date, answer_lookup)


def cmd_grade(args: argparse.Namespace) -> str:
    _, srs_json = _resolve_paths(args.path)

    if not srs_json.exists():
        return f"Error: {srs_json} not found. Run `init` first."

    quality = int(args.quality)
    if not 0 <= quality <= 5:
        return "Error: Quality must be 0-5."

    store = SRSStore.load(srs_json)
    card_id = args.card_id

    if card_id not in store["cards"]:
        return f"Error: Card '{card_id}' not found."

    card = store["cards"][card_id]
    if card.get("retired", False):
        return f"Error: Card '{card_id}' is retired."

    today = args.date if args.date else _today()
    updated = SM2.review(card, quality, today)
    store["cards"][card_id] = updated
    SRSStore.save(srs_json, store)

    if args.json:
        return JsonFormatter.output({"action": "grade", "card_id": card_id, "quality": quality, **updated})
    return MarkdownFormatter.grade_result(card_id, updated, quality)


def cmd_stats(args: argparse.Namespace) -> str:
    _, srs_json = _resolve_paths(args.path)

    if not srs_json.exists():
        return f"Error: {srs_json} not found. Run `init` first."

    store = SRSStore.load(srs_json)

    if args.json:
        cards = store["cards"]
        active = {k: v for k, v in cards.items() if not v.get("retired")}
        status_counts: Dict[str, int] = {}
        for c in active.values():
            s = c.get("status", "new")
            status_counts[s] = status_counts.get(s, 0) + 1
        return JsonFormatter.output({
            "action": "stats",
            "total": len(cards),
            "active": len(active),
            "retired": len(cards) - len(active),
            "by_status": status_counts,
            "total_reviews": sum(len(c.get("review_history", [])) for c in active.values()),
            "total_lapses": sum(c.get("lapses", 0) for c in active.values()),
        })
    return MarkdownFormatter.stats(store)


def cmd_forecast(args: argparse.Namespace) -> str:
    _, srs_json = _resolve_paths(args.path)

    if not srs_json.exists():
        return f"Error: {srs_json} not found. Run `init` first."

    store = SRSStore.load(srs_json)
    days = args.days
    today = date.today()

    buckets: Dict[str, int] = {}
    for i in range(days):
        d = (today + timedelta(days=i)).isoformat()
        buckets[d] = 0

    for card in store["cards"].values():
        if card.get("retired", False):
            continue
        nr = card.get("next_review")
        if nr and nr in buckets:
            buckets[nr] += 1
        elif nr and nr < today.isoformat():
            # Overdue — count as today
            buckets[today.isoformat()] = buckets.get(today.isoformat(), 0) + 1

    if args.json:
        return JsonFormatter.output({"action": "forecast", "days": days, "buckets": buckets})
    return MarkdownFormatter.forecast(buckets, days)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srs_engine",
        description="SM-2 Spaced Repetition Scheduling Engine",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Create cards.srs.json from cards.md")
    p_init.add_argument("path", help="Path to cards.md or its parent directory")
    p_init.add_argument("--json", action="store_true", help="Output as JSON")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing srs.json")

    # sync
    p_sync = subparsers.add_parser("sync", help="Sync new/changed cards from cards.md")
    p_sync.add_argument("path", help="Path to cards.md or its parent directory")
    p_sync.add_argument("--json", action="store_true", help="Output as JSON")

    # due
    p_due = subparsers.add_parser("due", help="List cards due for review")
    p_due.add_argument("path", help="Path to cards.md or its parent directory")
    p_due.add_argument("--date", default=None, help="Check date (YYYY-MM-DD), defaults to today")
    p_due.add_argument("--json", action="store_true", help="Output as JSON")

    # grade
    p_grade = subparsers.add_parser("grade", help="Grade a card (0-5)")
    p_grade.add_argument("path", help="Path to cards.md or its parent directory")
    p_grade.add_argument("card_id", help="Card ID (e.g., card-1)")
    p_grade.add_argument("quality", type=int, help="Quality grade (0-5)")
    p_grade.add_argument("--date", default=None, help="Review date (YYYY-MM-DD), defaults to today")
    p_grade.add_argument("--json", action="store_true", help="Output as JSON")

    # stats
    p_stats = subparsers.add_parser("stats", help="Show aggregate statistics")
    p_stats.add_argument("path", help="Path to cards.md or its parent directory")
    p_stats.add_argument("--json", action="store_true", help="Output as JSON")

    # forecast
    p_forecast = subparsers.add_parser("forecast", help="Show review forecast")
    p_forecast.add_argument("path", help="Path to cards.md or its parent directory")
    p_forecast.add_argument("--days", type=int, default=7, help="Number of days to forecast (default: 7)")
    p_forecast.add_argument("--json", action="store_true", help="Output as JSON")

    return parser


COMMANDS = {
    "init": cmd_init,
    "sync": cmd_sync,
    "due": cmd_due,
    "grade": cmd_grade,
    "stats": cmd_stats,
    "forecast": cmd_forecast,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS.get(args.command)
    if not handler:
        parser.print_help()
        return 1
    try:
        result = handler(args)
        print(result)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
