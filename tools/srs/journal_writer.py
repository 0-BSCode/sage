#!/usr/bin/env python3
"""Deterministic journal index writer for journal/index.md.

Appends rows and normalizes journal index tables to the canonical 8-column
format. The LLM produces content; this script enforces formatting.

Commands:
    append <path> --json '<json>'   Append a new row from JSON
    append <path> --stdin           Read row JSON from stdin
    validate <path>                 Check for format violations
    fix <path>                      Normalize to canonical 8-column format

Canonical format (8-column superset):
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

def _parse_table(text: str) -> Tuple[Optional[List[str]], List[List[str]], str, str]:
    """Parse a markdown table from text.

    Returns:
        (headers, rows, pre_table_text, post_table_text)
        headers is None if no table found.
    """
    lines = text.split("\n")
    table_start = None
    table_end = None
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
            table_end = i
        elif table_start is not None and not stripped.startswith("|"):
            # End of table
            break

    if table_start is None:
        return None, [], text, ""

    if table_end is None:
        table_end = table_start + 1  # just header + separator

    pre = "\n".join(lines[:table_start])
    post = "\n".join(lines[table_end + 1:])
    return headers, rows, pre, post


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


def _remap_row(row: List[str], source_headers: List[str], canonical_map: List[Optional[str]]) -> Dict[str, str]:
    """Convert a row from source format to a dict keyed by canonical column names.

    Handles short rows (fewer cells than headers) by mapping positionally,
    then using heuristics to fix misplacements:
    - If a value looks like a filename (session-*.md) but isn't mapped to "File",
      move it to "File" and clear the wrong slot.
    """
    d: Dict[str, str] = {}
    for i, cell in enumerate(row):
        if i < len(canonical_map) and canonical_map[i]:
            d[canonical_map[i]] = cell.strip()

    # Heuristic: detect filename in wrong column
    file_re = re.compile(r"^session-\S+\.md$")
    if "File" not in d or not d.get("File", "").strip() or d.get("File", "—") == "—":
        for col_name, value in list(d.items()):
            if col_name != "File" and file_re.match(value.strip()):
                d["File"] = value.strip()
                d[col_name] = "—"
                break

    return d


def _format_row(data: Dict[str, str]) -> str:
    """Format a row dict into a canonical table row."""
    cells = []
    for h in CANONICAL_HEADERS:
        cells.append(data.get(h, "—").strip() or "—")
    return "| " + " | ".join(cells) + " |"


def _build_table(rows: List[Dict[str, str]]) -> str:
    """Build a complete canonical table from row dicts."""
    lines = [HEADER_LINE, SEPARATOR_LINE]
    for row in rows:
        lines.append(_format_row(row))
    return "\n".join(lines)


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
    headers, rows, pre, post = _parse_table(text)

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
            # Non-canonical — migrate existing rows + append
            migrated_rows = []
            for row in rows:
                migrated_rows.append(_remap_row(row, headers, canonical_map))
            migrated_rows.append(new_row)
            table = _build_table(migrated_rows)
            content = pre.rstrip() + "\n\n" + table + "\n"
            if post.strip():
                content += "\n" + post.lstrip("\n")

    path.write_text(content, encoding="utf-8")
    print(f"Appended session {session_num} to {path}")


def cmd_validate(path: Path) -> None:
    """Check journal/index.md for format violations."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    headers, rows, _, _ = _parse_table(text)
    issues: List[str] = []

    if headers is None:
        issues.append("No markdown table found")
    else:
        # Check headers
        canonical_map = _map_headers(headers)
        mapped = {m for m in canonical_map if m}
        if mapped != set(CANONICAL_HEADERS):
            missing = set(CANONICAL_HEADERS) - mapped
            extra = set(headers) - {h for h, m in zip(headers, canonical_map) if m}
            if missing:
                issues.append(f"Missing columns: {', '.join(sorted(missing))}")
            if extra:
                issues.append(f"Unrecognized columns: {', '.join(sorted(extra))}")

        # Check row widths
        expected_cols = len(headers)
        for i, row in enumerate(rows):
            if len(row) != expected_cols:
                issues.append(f"Row {i + 1}: expected {expected_cols} columns, got {len(row)}")

        # Check for duplicate session numbers
        session_nums = [r[0].strip() if r else "" for r in rows]
        seen = {}
        for i, sn in enumerate(session_nums):
            if sn in seen:
                issues.append(f"Duplicate session number '{sn}' at rows {seen[sn] + 1} and {i + 1}")
            else:
                seen[sn] = i

    if not issues:
        print(f"OK — no format violations in {path}")
        return

    print(f"Found {len(issues)} issue(s) in {path}:\n")
    for issue in issues:
        print(f"  - {issue}")
    print()
    sys.exit(1)


def cmd_fix(path: Path) -> None:
    """Normalize journal/index.md to canonical 8-column format."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    headers, rows, pre, post = _parse_table(text)

    if headers is None:
        print(f"No table found in {path} — nothing to fix")
        return

    canonical_map = _map_headers(headers)
    mapped = {m for m in canonical_map if m}

    if mapped == set(CANONICAL_HEADERS):
        # Check row widths for mismatches
        needs_fix = False
        for row in rows:
            if len(row) != len(headers):
                needs_fix = True
                break
        if not needs_fix:
            print(f"Already canonical — no fixes needed in {path}")
            return

    # Migrate all rows
    migrated_rows = []
    for row in rows:
        migrated_rows.append(_remap_row(row, headers, canonical_map))
    table = _build_table(migrated_rows)

    content = pre.rstrip() + "\n\n" + table + "\n"
    if post.strip():
        content += "\n" + post.lstrip("\n")

    path.write_text(content, encoding="utf-8")
    print(f"Fixed {path} — migrated {len(migrated_rows)} rows to canonical 8-column format")


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

    p_validate = subparsers.add_parser("validate", help="Check for format violations")
    p_validate.add_argument("path", help="Path to journal/index.md or learning directory")

    p_fix = subparsers.add_parser("fix", help="Normalize to canonical 8-column format")
    p_fix.add_argument("path", help="Path to journal/index.md or learning directory")

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

    elif args.command == "validate":
        cmd_validate(path)

    elif args.command == "fix":
        cmd_fix(path)


if __name__ == "__main__":
    main()
