#!/usr/bin/env python3
"""Deterministic writer for weak-spots.md and coach-errors.md.

Appends new entries with auto-numbered IDs in canonical format.
Four kinds of entries in two files:

    --kind WS   learner weak spots         → weak-spots.md    (WS-1, WS-2, ...)
    --kind M    alias for WS (wrong-model) → weak-spots.md    (WS-1, WS-2, ...)
    --kind CE   coach content errors       → coach-errors.md  (CE-1, CE-2, ...)
    --kind CP   coach process failures     → coach-errors.md  (CP-1, CP-2, ...)

--kind M is a convenience alias: it writes to weak-spots.md with
Category: wrong-model auto-set. The entry gets a WS-N ID.

The writer refuses to write a coach entry to weak-spots.md and vice
versa — file boundary enforcement is structural, not convention.

Commands:
    append <path> --kind <WS|M|CE|CP> --stdin  Append a new entry from JSON

Canonical format (WS):
    ## WS-[N] — [short description]

Canonical format (CE/CP):
    ## CE-[N] — [short description]
    ## CP-[N] — [short description]

WS field block:
    **Category:** [wrong-model | incomplete-model | fragile-recall | application-gap]
    **Session:** [N] (first observed)
    **Last tested:** S[N]
    **What happened:** [context/trigger]
    **Correct model:** [the correct understanding or behavior]
    **Why it matters:** [downstream consequence]
    **Cards:** [card-N references, or —]
    **Concepts:** [exact concept names from knowledge-map.md]
    **Status:** [active | improving | resolved]

    ### History
    - **S[N]:** [observation, drill result, status change]

CE/CP field block:
    **Session:** [N]
    **What happened:** [context/trigger]
    **Root cause:** [diagnostic]
    **Correction:** [the correct mental model or process]
    **Why it matters:** [downstream consequence]
    **Follow-up:** [re-drill plans, metacognitive notes]
    **Source:** [URL citations, caught-by reference]
    **Cards:** [card-N references, or —]
    **Status:** [active | recurring | resolved | corrected]

WS required fields: Category, Session, What happened, Correct model, Status
CE/CP required fields: Session, What happened, Correction, Status

Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Kinds
# ---------------------------------------------------------------------------

KIND_WS = "WS"
# ponytail: KIND_M is a pure alias — it costs a KIND_TO_FILENAME entry and the
# args.kind-vs-kind path dance for something callers could express as
# `--kind WS --category wrong-model`. Kept because it is in real use (28
# invocations; `wrong-model` in 21 weak-spots.md files). Revisit if the alias
# ever stops carrying its weight — removal also touches the shipped markdown
# that teaches `--kind M`.
KIND_M = "M"  # Alias → resolves to WS with Category: wrong-model
KIND_CE = "CE"
KIND_CP = "CP"
ALL_KINDS = (KIND_WS, KIND_M, KIND_CE, KIND_CP)

KIND_TO_FILENAME = {
    KIND_WS: "weak-spots.md",
    KIND_M: "weak-spots.md",
    KIND_CE: "coach-errors.md",
    KIND_CP: "coach-errors.md",
}

VALID_CATEGORIES = frozenset({
    "wrong-model",
    "incomplete-model",
    "fragile-recall",
    "application-gap",
})


# ---------------------------------------------------------------------------
# Canonical format (kind-dependent)
# ---------------------------------------------------------------------------

WS_CANONICAL_FIELDS = [
    "Category",
    "Session",
    "Last tested",
    "What happened",
    "Correct model",
    "Why it matters",
    "Cards",
    "Concepts",
    "Status",
]

WS_REQUIRED_FIELDS = {"Category", "Session", "What happened", "Correct model", "Status"}

CE_CANONICAL_FIELDS = [
    "Session",
    "What happened",
    "Root cause",
    "Correction",
    "Why it matters",
    "Follow-up",
    "Source",
    "Cards",
    "Status",
]

CE_REQUIRED_FIELDS = {"Session", "What happened", "Correction", "Status"}


def _canonical_fields(kind: str) -> List[str]:
    return WS_CANONICAL_FIELDS if kind == KIND_WS else CE_CANONICAL_FIELDS


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _find_max_number(text: str, kind: str) -> int:
    """Find the highest number in the file for the given kind's namespace."""
    max_n = 0
    pattern = re.compile(rf"##?\s+{re.escape(kind)}-?(\d+)")
    for m in pattern.finditer(text):
        n = int(m.group(1))
        if n > max_n:
            max_n = n
    return max_n


def _format_entry(
    kind: str,
    number: int,
    description: str,
    fields: Dict[str, str],
    history: Optional[List[str]] = None,
) -> str:
    """Format a single entry in canonical format for the given kind."""
    canonical = _canonical_fields(kind)
    lines = [f"## {kind}-{number} — {description}", ""]
    for field_name in canonical:
        value = fields.get(field_name, "")
        if value and value.strip() and value.strip() != "—":
            lines.append(f"**{field_name}:** {value.strip()}")
    for key, value in fields.items():
        if key not in canonical:
            if value and value.strip() and value.strip() != "—":
                lines.append(f"**{key}:** {value.strip()}")

    # WS entries include a History subsection
    if kind == KIND_WS:
        lines.append("")
        lines.append("### History")
        if history:
            for h in history:
                lines.append(h)
        else:
            session = fields.get("Session", "?")
            session_match = re.match(r"(\d+)", str(session))
            s = session_match.group(1) if session_match else "?"
            lines.append(f"- **S{s}:** First observed")

    lines.append("")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# File header templates (auto-creation)
# ---------------------------------------------------------------------------

WEAK_SPOTS_HEADER = (
    "# Weak Spots\n\n"
    "Scope: learner weaknesses that need drilling. "
    "Coach errors belong in `coach-errors.md`.\n\n"
    "Categories:\n"
    "- **wrong-model:** Learner believes something factually incorrect\n"
    "- **incomplete-model:** Learner knows part but misses a dimension\n"
    "- **fragile-recall:** Correct knowledge, unreliable retrieval\n"
    "- **application-gap:** Understands concept, defaults to wrong pattern\n\n"
    "---\n"
)

COACH_ERRORS_HEADER = (
    "# Coach Errors\n\n"
    "Scope: coach-originated errors only. "
    "Learner weaknesses belong in `weak-spots.md`.\n\n"
    "Entry kinds:\n"
    "- **CE-# (Content Error):** Coach taught something factually wrong; "
    "learner absorbed it into their mental model or cards. "
    "Requires transparency + artifact correction.\n"
    "- **CP-# (Process Failure):** Coach violated a workflow discipline "
    "(e.g., skipped verification gate). Requires process fix, not retrieval drilling.\n\n"
    "A coach error is NOT a learner weakness. These entries exist for coach "
    "accountability, not for planning retrieval drills.\n\n"
    "---\n"
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_category(category: str) -> None:
    """Reject invalid category values with a hard error."""
    if category not in VALID_CATEGORIES:
        print(
            f"Error: invalid category '{category}'. "
            f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
            file=sys.stderr,
        )
        sys.exit(1)


def _validate_concepts(concepts_str: str, kmap_path: Optional[Path]) -> None:
    """Warn if Concepts field values don't match known concepts in knowledge-map."""
    if not kmap_path or not kmap_path.exists():
        return

    kmap_text = kmap_path.read_text(encoding="utf-8")
    known_concepts: set = set()
    for line in kmap_text.split("\n"):
        stripped = line.strip()
        if (
            stripped.startswith("|")
            and not stripped.startswith("| ---")
            and not stripped.startswith("| Concept")
        ):
            cells = [c.strip() for c in stripped.split("|")]
            if len(cells) >= 2 and cells[1]:
                known_concepts.add(cells[1].lower())

    if not known_concepts:
        return

    for concept in concepts_str.split(","):
        concept = concept.strip()
        if concept and concept.lower() not in known_concepts:
            print(
                f"Warning: concept '{concept}' not found in knowledge-map",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_append(
    path: Path,
    kind: str,
    entry_json: Dict[str, Any],
    kmap_path: Optional[Path] = None,
) -> None:
    """Append a new entry of the given kind with auto-numbered ID."""
    # Auto-create files if missing
    if not path.exists():
        if path.name == "coach-errors.md":
            path.write_text(COACH_ERRORS_HEADER, encoding="utf-8")
        elif path.name == "weak-spots.md":
            path.write_text(WEAK_SPOTS_HEADER, encoding="utf-8")
        else:
            print(f"Error: {path} does not exist", file=sys.stderr)
            sys.exit(1)

    text = path.read_text(encoding="utf-8")
    max_n = _find_max_number(text, kind)
    new_n = max_n + 1

    description = entry_json.get("description", "Untitled")

    if kind == KIND_WS:
        # --- WS entry ---
        category = entry_json.get("category", "")
        if category:
            _validate_category(category)

        fields: Dict[str, str] = {}
        for key, canonical in [
            ("category", "Category"),
            ("session", "Session"),
            ("last_tested", "Last tested"),
            ("what_happened", "What happened"),
            ("correct_model", "Correct model"),
            ("correction", "Correct model"),
            ("why_it_matters", "Why it matters"),
            ("concepts", "Concepts"),
            ("status", "Status"),
        ]:
            if key in entry_json and entry_json[key] and canonical not in fields:
                fields[canonical] = str(entry_json[key])

        cards = entry_json.get("cards", [])
        if isinstance(cards, list):
            fields["Cards"] = ", ".join(cards) if cards else "—"
        elif cards:
            fields["Cards"] = str(cards)

        # Auto-set Last tested from Session if not provided
        if "Last tested" not in fields and "Session" in fields:
            session_match = re.match(r"(\d+)", fields["Session"])
            if session_match:
                fields["Last tested"] = f"S{session_match.group(1)}"

        # Validate concepts against knowledge map
        if "Concepts" in fields:
            _validate_concepts(fields["Concepts"], kmap_path)

        # Build initial history
        history_text = entry_json.get("history", "First observed")
        session_match = re.match(r"(\d+)", fields.get("Session", "?"))
        s = session_match.group(1) if session_match else "?"
        history = [f"- **S{s}:** {history_text}"]

        formatted = _format_entry(kind, new_n, description, fields, history=history)

    else:
        # --- CE/CP entry (unchanged from original) ---
        fields = {}
        for key, canonical in [
            ("session", "Session"),
            ("what_happened", "What happened"),
            ("root_cause", "Root cause"),
            ("correction", "Correction"),
            ("why_it_matters", "Why it matters"),
            ("follow_up", "Follow-up"),
            ("source", "Source"),
            ("status", "Status"),
        ]:
            if key in entry_json and entry_json[key]:
                fields[canonical] = str(entry_json[key])

        cards = entry_json.get("cards", [])
        if isinstance(cards, list):
            fields["Cards"] = ", ".join(cards) if cards else "—"
        elif cards:
            fields["Cards"] = str(cards)

        formatted = _format_entry(kind, new_n, description, fields)

    content = text.rstrip()
    if not content.endswith("---"):
        content += "\n\n---"
    content += "\n\n" + formatted + "\n"

    path.write_text(content, encoding="utf-8")
    label = f"{kind}-{new_n}"
    print(f"Appended {label} — {description} to {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_path(path_arg: str, kind: str) -> Path:
    """Resolve to the correct file for the given kind, validating explicit paths."""
    p = Path(path_arg)
    expected_filename = KIND_TO_FILENAME[kind]
    if p.is_dir():
        return p / expected_filename
    if p.name != expected_filename:
        raise ValueError(
            f"Path {p} does not match kind={kind} "
            f"(expected filename: {expected_filename}). "
            f"Refusing to operate on a {kind} entry against the wrong file."
        )
    return p


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic weak-spot / coach-error writer"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_append = subparsers.add_parser("append", help="Append a new entry")
    p_append.add_argument("path", help="Path to file or learning directory")
    p_append.add_argument("--json", dest="json_str", help="JSON string")
    p_append.add_argument(
        "--stdin", action="store_true", help="Read JSON from stdin"
    )
    p_append.add_argument(
        "--knowledge-map",
        dest="knowledge_map",
        help="Path to knowledge-map.md for concept validation",
    )

    p_append.add_argument(
        "--kind",
        choices=list(ALL_KINDS),
        default=KIND_WS,
        help=(
            "Entry kind: WS for learner weak spots (default), "
            "M for wrong-model alias (writes WS with Category: wrong-model), "
            "CE for coach content errors, CP for coach process failures"
        ),
    )

    args = parser.parse_args()

    # Resolve M alias to WS early
    kind = args.kind
    auto_category = None
    if kind == KIND_M:
        auto_category = "wrong-model"
        kind = KIND_WS

    # Use original args.kind for path resolution (M and WS both map to weak-spots.md)
    try:
        path = _resolve_path(args.path, args.kind)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    kmap_path = None
    if hasattr(args, "knowledge_map") and args.knowledge_map:
        kmap_path = Path(args.knowledge_map)

    if args.command == "append":
        if args.stdin:
            raw = sys.stdin.read()
        elif args.json_str:
            raw = args.json_str
        else:
            print("Error: provide --json or --stdin", file=sys.stderr)
            sys.exit(1)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON — {e}", file=sys.stderr)
            sys.exit(1)

        # Auto-set category for M alias
        if auto_category and "category" not in data:
            data["category"] = auto_category

        cmd_append(path, kind, data, kmap_path=kmap_path)


if __name__ == "__main__":
    main()
