#!/usr/bin/env python3
"""Deterministic journal index writer for journal/index.md.

Appends rows to journal index tables in the canonical 8-column format.
The LLM produces content; this script enforces formatting.

Commands:
    append <path> --json '<json>'   Append a new row from JSON
    append <path> --stdin           Read row JSON from stdin

Canonical format (8-column):
    | # | Date | Type | Focus | Reviews | Avg Grade | Summary | File |

All columns except #, Date, Focus are optional (default to —).

Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Canonical schema
# ---------------------------------------------------------------------------

CANONICAL_HEADERS = ["#", "Date", "Type", "Focus", "Reviews", "Avg Grade", "Summary", "File"]

# Known header variants and their mapping to canonical column names
HEADER_MAP: Dict[str, str] = {
    "#": "#",
    "session": "#",
    "date": "Date",
    "type": "Type",
    "focus": "Focus",
    "reviews": "Reviews",
    "avg grade": "Avg Grade",
    "summary": "Summary",
    "file": "File",
}

HEADER_LINE = "| " + " | ".join(CANONICAL_HEADERS) + " |"
SEPARATOR_LINE = "|" + "|".join("---" for _ in CANONICAL_HEADERS) + "|"

TITLE_LINE = "# Session Index"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_table(text: str) -> Tuple[Optional[List[str]], List[List[str]]]:
    """Parse a markdown table from text.

    Returns (headers, rows). headers is None if no table found.
    """
    lines = text.split("\n")
    table_start = None
    headers: Optional[List[str]] = None
    rows: List[List[str]] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and "|" in stripped[1:]:
            if table_start is None:
                table_start = i
                # Parse header
                headers = [c.strip() for c in stripped.strip("|").split("|")]
                continue
            # Skip separator line
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            # Data row
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            rows.append(cells)
        elif table_start is not None and not stripped.startswith("|"):
            # End of table
            break

    if table_start is None:
        return None, []

    return headers, rows


def _map_headers(source_headers: List[str]) -> List[Optional[str]]:
    """Map source headers to canonical column names.

    Returns a list parallel to source_headers, where each entry is
    the canonical name or None if unrecognized.
    """
    result = []
    for h in source_headers:
        key = h.strip().lower()
        result.append(HEADER_MAP.get(key))
    return result


def _format_row(data: Dict[str, str]) -> str:
    """Format a row dict into a canonical table row."""
    cells = []
    for h in CANONICAL_HEADERS:
        cells.append(data.get(h, "—").strip() or "—")
    return "| " + " | ".join(cells) + " |"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_append(path: Path, row_json: Dict[str, Any]) -> None:
    """Append a new row to journal/index.md."""
    if not path.exists():
        # Create new file with header
        text = TITLE_LINE + "\n\n" + HEADER_LINE + "\n" + SEPARATOR_LINE + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    text = path.read_text(encoding="utf-8")
    headers, rows = _parse_table(text)

    # Build the new row
    session_num = row_json.get("session_number", "")
    date = row_json.get("date", "—")
    session_type = row_json.get("type", "—")
    focus = row_json.get("focus", "—")
    review_count = row_json.get("review_count")
    avg_grade = row_json.get("avg_grade")
    summary = row_json.get("summary", "—")

    # Derive filename
    sn = str(session_num)
    # Handle suffixed session numbers like "3b", "18a"
    file_name = f"session-{sn.zfill(2)}.md" if sn.isdigit() else f"session-{sn}.md"

    new_row = {
        "#": str(session_num),
        "Date": date,
        "Type": session_type or "—",
        "Focus": focus,
        "Reviews": str(review_count) if review_count is not None else "—",
        "Avg Grade": f"{avg_grade:.2f}" if avg_grade is not None else "—",
        "Summary": summary or "—",
        "File": file_name,
    }

    if headers is None:
        # No table found — create one
        content = text.rstrip() + "\n\n" + HEADER_LINE + "\n" + SEPARATOR_LINE + "\n" + _format_row(new_row) + "\n"
    else:
        # Check if table is already canonical
        canonical_map = _map_headers(headers)
        if set(CANONICAL_HEADERS) == {m for m in canonical_map if m}:
            # Already canonical — just append
            content = text.rstrip() + "\n" + _format_row(new_row) + "\n"
        else:
            # Not canonical — refuse rather than silently rewriting the table.
            mapped = {m for m in canonical_map if m}
            missing = set(CANONICAL_HEADERS) - mapped
            print(
                f"Error: {path} is not in canonical 8-column format "
                f"(missing columns: {', '.join(sorted(missing))}). "
                f"Expected: {' | '.join(CANONICAL_HEADERS)}",
                file=sys.stderr,
            )
            sys.exit(1)

    path.write_text(content, encoding="utf-8")
    print(f"Appended session {session_num} to {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_path(path_arg: str) -> Path:
    """Resolve to journal/index.md from a directory or file path."""
    p = Path(path_arg)
    if p.is_dir():
        journal_dir = p / "journal"
        if journal_dir.is_dir():
            return journal_dir / "index.md"
        return p / "journal" / "index.md"
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic journal index writer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_append = subparsers.add_parser("append", help="Append a new session row")
    p_append.add_argument("path", help="Path to journal/index.md or learning directory")
    p_append.add_argument("--json", dest="json_str", help="Row JSON string")
    p_append.add_argument("--stdin", action="store_true", help="Read JSON from stdin")

    args = parser.parse_args()
    path = _resolve_path(args.path)

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

        if not isinstance(data, dict):
            print("Error: JSON must be an object", file=sys.stderr)
            sys.exit(1)

        cmd_append(path, data)


if __name__ == "__main__":
    main()
