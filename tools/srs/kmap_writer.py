#!/usr/bin/env python3
"""Deterministic knowledge-map writer for knowledge-map.md.

Handles Status Changelog appends, Status Legend normalization, and
concepts table manipulation (add/update rows).

Commands:
    changelog-append <path> --stdin    Append rows to Status Changelog section
    fix-legend <path>                  Normalize Status Legend to canonical format
    ensure-sections <path>             Create missing Changelog section
    validate <path>                    Check for format violations
    add-concept <path> --stdin         Add a new concept row to the concepts table
    update-status <path> --stdin       Update an existing concept's status

Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Canonical formats
# ---------------------------------------------------------------------------

CANONICAL_LEGEND = """## Status Legend
- **Not started** — Concept on the plan, not yet introduced
- **Introduced** — Concept presented, not yet retrieval-tested
- **Developing** — Retrieval-tested but inconsistent recall
- **Solid** — Reliable retrieval and application
- **Mastered** — Automatic retrieval, can teach and handle edge cases
- **Prior (from [project])** — Already solid/mastered in a sibling project"""

CANONICAL_STATUSES = {"not started", "introduced", "developing", "solid", "mastered", "prior"}

CHANGELOG_HEADER = "| Date | Concept | From | To | Session |"
CHANGELOG_SEP = "|------|---------|------|----|---------|"

INTRODUCED_RE = re.compile(r"^S\d+$|^prior$", re.IGNORECASE)

# Section heading patterns
CHANGELOG_HEADING_RE = re.compile(r"^##\s+Status\s+Changelog\s*$", re.IGNORECASE)
LEGEND_HEADING_RE = re.compile(r"^##\s+Status\s+Legend\s*$", re.IGNORECASE)

# Detect any legend-like content (bracket-style, bullet-style, etc.)
LEGEND_CONTENT_RE = re.compile(
    r"Status\s+legend|mastered.*solid.*developing|mastered.*solid.*shaky",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Section manipulation
# ---------------------------------------------------------------------------

def _find_section(lines: List[str], heading_re: re.Pattern) -> Optional[Tuple[int, int]]:
    """Find a section by heading regex. Returns (start_line, end_line) inclusive.

    end_line is the last line before the next ## heading or EOF.
    """
    start = None
    for i, line in enumerate(lines):
        if heading_re.match(line.strip()):
            start = i
            continue
        if start is not None and line.strip().startswith("## "):
            return (start, i - 1)
    if start is not None:
        return (start, len(lines) - 1)
    return None


def _find_legend_section(lines: List[str]) -> Optional[Tuple[int, int]]:
    """Find the Status Legend section, including non-canonical formats."""
    # First try canonical heading
    result = _find_section(lines, LEGEND_HEADING_RE)
    if result:
        return result

    # Try to find inline legend (e.g., "Status legend: [mastered] [solid] ...")
    for i, line in enumerate(lines):
        if LEGEND_CONTENT_RE.search(line) and not line.strip().startswith("#"):
            return (i, i)
    return None


def _last_table_line_in_section(lines: List[str], section: Tuple[int, int]) -> int:
    """Find the index of the last table line (header, separator, or data row) in a section."""
    start, end = section
    last_line = start
    for i in range(start, end + 1):
        stripped = lines[i].strip()
        if stripped.startswith("|"):
            last_line = i
    return last_line


# ---------------------------------------------------------------------------
# Concept table helpers
# ---------------------------------------------------------------------------

def _parse_table_row(line: str) -> List[str]:
    """Split a markdown table row into cells, stripping whitespace."""
    if not line.strip().startswith("|"):
        return []
    parts = line.strip().split("|")
    # First and last elements are empty strings from leading/trailing pipes
    return [c.strip() for c in parts[1:-1]]


def _is_concept_table_header(line: str) -> bool:
    """Check if a line is a concept table header (has Concept + Status columns)."""
    cells = _parse_table_row(line)
    return len(cells) >= 4 and cells[0].lower() == "concept" and cells[1].lower() == "status"


def _table_has_introduced(header_line: str) -> bool:
    """Check if a concept table header includes the Introduced column."""
    cells = _parse_table_row(header_line)
    return len(cells) >= 5 and cells[2].lower() == "introduced"


def _find_all_concept_tables(lines: List[str]) -> List[Tuple[int, int, int]]:
    """Find all concept tables. Returns list of (header_idx, sep_idx, last_data_idx)."""
    tables: List[Tuple[int, int, int]] = []
    i = 0
    while i < len(lines):
        if _is_concept_table_header(lines[i]):
            header_idx = i
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("|") and "---" in lines[i + 1]:
                sep_idx = i + 1
                last_data = sep_idx
                j = sep_idx + 1
                while j < len(lines) and lines[j].strip().startswith("|"):
                    last_data = j
                    j += 1
                tables.append((header_idx, sep_idx, last_data))
                i = last_data + 1
                continue
        i += 1
    return tables


def _find_concept_row(lines: List[str], concept_name: str) -> Optional[Tuple[int, int, bool]]:
    """Find a concept by name across all tables.

    Returns (row_idx, header_idx, has_introduced) or None.
    """
    tables = _find_all_concept_tables(lines)
    for header_idx, sep_idx, last_data in tables:
        has_intro = _table_has_introduced(lines[header_idx])
        for row_idx in range(sep_idx + 1, last_data + 1):
            cells = _parse_table_row(lines[row_idx])
            if cells and cells[0].lower() == concept_name.lower():
                return (row_idx, header_idx, has_intro)
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_changelog_append(path: Path, entries: List[Dict[str, Any]]) -> None:
    """Append rows to the Status Changelog section."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    section = _find_section(lines, CHANGELOG_HEADING_RE)
    if section is None:
        # Create section at end of file
        lines.append("")
        lines.append("## Status Changelog")
        lines.append("")
        lines.append(CHANGELOG_HEADER)
        lines.append(CHANGELOG_SEP)
        section = (len(lines) - 4, len(lines) - 1)

    insert_at = _last_table_line_in_section(lines, section) + 1

    new_rows = []
    for entry in entries:
        date = entry.get("date", "—")
        concept = entry.get("concept", "—")
        from_status = entry.get("from_status", "—")
        to_status = entry.get("to_status", "—")
        session = str(entry.get("session", "—"))
        new_rows.append(f"| {date} | {concept} | {from_status} | {to_status} | {session} |")

    for i, row in enumerate(new_rows):
        lines.insert(insert_at + i, row)

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Appended {len(new_rows)} changelog row(s) to {path}")


def cmd_fix_legend(path: Path) -> None:
    """Replace the Status Legend with the canonical version."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    section = _find_legend_section(lines)
    if section is None:
        # No legend found — insert after the title line
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("# "):
                insert_at = i + 1
                break
            if line.strip().startswith("**Last updated"):
                insert_at = i + 1
                break

        # Skip blank lines after title/date
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1

        legend_lines = CANONICAL_LEGEND.split("\n")
        for i, ll in enumerate(legend_lines):
            lines.insert(insert_at + i, ll)
        lines.insert(insert_at + len(legend_lines), "")

        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Inserted canonical Status Legend in {path}")
        return

    start, end = section

    # Check if already canonical
    existing = "\n".join(lines[start:end + 1]).strip()
    if existing == CANONICAL_LEGEND.strip():
        print(f"Status Legend already canonical in {path}")
        return

    # Replace
    legend_lines = CANONICAL_LEGEND.split("\n")
    lines[start:end + 1] = legend_lines
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Replaced Status Legend with canonical version in {path}")


def cmd_ensure_sections(path: Path) -> None:
    """Create missing Changelog section."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    added = []

    if _find_section(lines, CHANGELOG_HEADING_RE) is None:
        lines.append("")
        lines.append("## Status Changelog")
        lines.append("")
        lines.append(CHANGELOG_HEADER)
        lines.append(CHANGELOG_SEP)
        added.append("Status Changelog")

    if added:
        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Added sections to {path}: {', '.join(added)}")
    else:
        print(f"All sections already present in {path}")


def cmd_validate(path: Path) -> None:
    """Check knowledge-map.md for format violations."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    issues: List[str] = []

    # Check legend
    legend = _find_legend_section(lines)
    if legend is None:
        issues.append("Status Legend: missing entirely")
    else:
        existing = "\n".join(lines[legend[0]:legend[1] + 1]).strip()
        if existing != CANONICAL_LEGEND.strip():
            issues.append("Status Legend: non-canonical format")

    # Check changelog
    changelog = _find_section(lines, CHANGELOG_HEADING_RE)
    if changelog is None:
        issues.append("Status Changelog: section missing")

    if not issues:
        print(f"OK — no format violations in {path}")
        return

    print(f"Found {len(issues)} issue(s) in {path}:\n")
    for issue in issues:
        print(f"  - {issue}")
    print()
    sys.exit(1)


def cmd_add_concept(path: Path, entry: Dict[str, Any]) -> None:
    """Add a new concept row to the last concept table."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    concept = entry.get("concept", "").strip()
    status = entry.get("status", "").strip()
    introduced = entry.get("introduced", "").strip()
    last_tested = entry.get("last_tested", "").strip()
    notes = entry.get("notes", "").strip()

    if not concept:
        print("Error: 'concept' is required", file=sys.stderr)
        sys.exit(1)
    if not status:
        print("Error: 'status' is required", file=sys.stderr)
        sys.exit(1)
    if not introduced:
        print("Error: 'introduced' is required", file=sys.stderr)
        sys.exit(1)
    if not INTRODUCED_RE.match(introduced):
        print(f"Error: 'introduced' must be S<N> or 'prior', got '{introduced}'", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    existing = _find_concept_row(lines, concept)
    if existing is not None:
        print(f"Error: concept '{concept}' already exists at line {existing[0] + 1}", file=sys.stderr)
        sys.exit(1)

    tables = _find_all_concept_tables(lines)
    if not tables:
        print("Error: no concept table found in knowledge-map", file=sys.stderr)
        sys.exit(1)

    header_idx, sep_idx, last_data = tables[-1]
    has_intro = _table_has_introduced(lines[header_idx])

    if has_intro:
        row = f"| {concept} | {status} | {introduced} | {last_tested} | {notes} |"
    else:
        row = f"| {concept} | {status} | {last_tested} | {notes} |"

    lines.insert(last_data + 1, row)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Added concept '{concept}' to {path}")


def cmd_update_status(path: Path, entry: Dict[str, Any]) -> None:
    """Update an existing concept's status, last_tested, and/or notes. Never modifies Introduced."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    concept = entry.get("concept", "").strip()
    if not concept:
        print("Error: 'concept' is required", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    result = _find_concept_row(lines, concept)
    if result is None:
        print(f"Error: concept '{concept}' not found", file=sys.stderr)
        sys.exit(1)

    row_idx, header_idx, has_intro = result
    cells = _parse_table_row(lines[row_idx])

    if has_intro:
        # 5-col: Concept | Status | Introduced | Last Tested | Notes
        current_introduced = cells[2] if len(cells) > 2 else ""
        new_status = entry.get("status", cells[1] if len(cells) > 1 else "").strip()
        new_last_tested = entry.get("last_tested", cells[3] if len(cells) > 3 else "").strip()
        new_notes = entry.get("notes", cells[4] if len(cells) > 4 else "").strip()
        lines[row_idx] = f"| {cells[0]} | {new_status} | {current_introduced} | {new_last_tested} | {new_notes} |"
    else:
        # 4-col: Concept | Status | Last Tested | Notes
        new_status = entry.get("status", cells[1] if len(cells) > 1 else "").strip()
        new_last_tested = entry.get("last_tested", cells[2] if len(cells) > 2 else "").strip()
        new_notes = entry.get("notes", cells[3] if len(cells) > 3 else "").strip()
        lines[row_idx] = f"| {cells[0]} | {new_status} | {new_last_tested} | {new_notes} |"

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Updated concept '{concept}' in {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_path(path_arg: str) -> Path:
    """Resolve to knowledge-map.md from a directory or file path."""
    p = Path(path_arg)
    if p.is_dir():
        return p / "knowledge-map.md"
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic knowledge-map writer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_cl = subparsers.add_parser("changelog-append", help="Append Status Changelog rows")
    p_cl.add_argument("path", help="Path to knowledge-map.md or learning directory")
    p_cl.add_argument("--json", dest="json_str", help="JSON string")
    p_cl.add_argument("--stdin", action="store_true", help="Read JSON from stdin")

    p_fl = subparsers.add_parser("fix-legend", help="Normalize Status Legend")
    p_fl.add_argument("path", help="Path to knowledge-map.md or learning directory")

    p_es = subparsers.add_parser("ensure-sections", help="Create missing sections")
    p_es.add_argument("path", help="Path to knowledge-map.md or learning directory")

    p_v = subparsers.add_parser("validate", help="Check for format violations")
    p_v.add_argument("path", help="Path to knowledge-map.md or learning directory")

    p_ac = subparsers.add_parser("add-concept", help="Add a new concept row")
    p_ac.add_argument("path", help="Path to knowledge-map.md or learning directory")
    p_ac.add_argument("--json", dest="json_str", help="JSON string")
    p_ac.add_argument("--stdin", action="store_true", help="Read JSON from stdin")

    p_us = subparsers.add_parser("update-status", help="Update an existing concept's status")
    p_us.add_argument("path", help="Path to knowledge-map.md or learning directory")
    p_us.add_argument("--json", dest="json_str", help="JSON string")
    p_us.add_argument("--stdin", action="store_true", help="Read JSON from stdin")

    args = parser.parse_args()
    path = _resolve_path(args.path)

    if args.command == "changelog-append":
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

        if not isinstance(data, list):
            data = [data]
        cmd_changelog_append(path, data)

    elif args.command == "fix-legend":
        cmd_fix_legend(path)

    elif args.command == "ensure-sections":
        cmd_ensure_sections(path)

    elif args.command == "validate":
        cmd_validate(path)

    elif args.command in ("add-concept", "update-status"):
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

        if args.command == "add-concept":
            cmd_add_concept(path, data)
        else:
            cmd_update_status(path, data)


if __name__ == "__main__":
    main()
