#!/usr/bin/env python3
"""Deterministic index writer for docs/demos/index.md.

Manages the demo index as a markdown table. The demo-generator agent produces
demo content; this script enforces index formatting, deduplication, and
validation.

Commands:
    append <path> --json '<json>'   Append a new demo entry from JSON
    append <path> --stdin           Read demo JSON from stdin
    validate <path>                 Check index for issues (missing files, format)

JSON input format (single object):
    {
        "weak_spot_id": "WS-31",
        "weak_spot_description": "one-sided vs two-sided z-value confusion",
        "demo_title": "Z-Values: One-sided vs Two-sided",
        "demo_filename": "one-sided-vs-two-sided-z-values.html",
        "related_reference": "ref-hypothesis-testing.md",
        "created_date": "2026-04-02"
    }

If "related_reference" is empty or omitted, the column shows "No reference doc yet".

Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

INDEX_HEADER = """\
# Interactive Demos

Targeted demos for persistent weak spots. Each demo corrects a specific wrong mental model.

| Weak Spot | Demo | Related Reference | Created |
|-----------|------|-------------------|---------|
"""

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]*)\)")

NO_REF_TEXT = "No reference doc yet"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def cells(row: str) -> List[str]:
    """Split a markdown table row into its cells."""
    return [c.strip() for c in row.strip().strip("|").split("|")]


def format_ref_cell(related_reference: str) -> str:
    """Format the related reference cell content."""
    if not related_reference or related_reference == "—":
        return NO_REF_TEXT
    # Extract concept name from slug: ref-hypothesis-testing.md -> Hypothesis Testing
    name = re.sub(r"^ref-", "", related_reference)
    name = re.sub(r"\.md$", "", name)
    name = name.replace("-", " ").title()
    return f"[{name}](../references/{related_reference})"


def format_row(entry: Dict[str, Any]) -> str:
    """Format a single markdown table row."""
    return (
        f"| {entry['weak_spot_id']}: {entry['weak_spot_description']} "
        f"| [{entry['demo_title']}]({entry['demo_filename']}) "
        f"| {format_ref_cell(entry.get('related_reference', ''))} "
        f"| {entry['created_date']} |"
    )


def read_rows(index_path: Path) -> List[str]:
    """Read existing table rows, excluding the header and its separator.

    Every data row is kept verbatim, including hand-written ones this script
    did not produce. Only rows carrying a WS id are ever rewritten; anything
    else rides along untouched rather than being dropped on the next append.
    """
    if not index_path.exists():
        return []
    return [
        line for line in index_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("|")
        and not line.startswith("| Weak Spot")
        and not set(line) <= set("|- ")
    ]


def write_index(index_path: Path, rows: List[str]) -> None:
    index_path.write_text(INDEX_HEADER + "".join(r + "\n" for r in rows), encoding="utf-8")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_append(demos_dir: Path, entry: Dict[str, Any]) -> None:
    """Append a new demo entry to the index."""
    required = ["weak_spot_id", "weak_spot_description", "demo_title",
                "demo_filename", "created_date"]
    missing = [f for f in required if not entry.get(f)]
    if missing:
        print(f"Error: missing required fields: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    ws_id = entry["weak_spot_id"]
    if not re.match(r"^WS-\d+$", ws_id):
        print(f"Error: weak_spot_id must match WS-<number>, got: {ws_id}",
              file=sys.stderr)
        sys.exit(1)

    if not (demos_dir / entry["demo_filename"]).exists():
        print(f"Warning: demo file not found: {demos_dir / entry['demo_filename']}",
              file=sys.stderr)

    index_path = demos_dir / "index.md"
    rows = read_rows(index_path)

    # Same weak spot replaces its previous entry
    kept = [r for r in rows if not r.startswith(f"| {ws_id}:")]
    action = "Updated" if len(kept) < len(rows) else "Appended"

    kept.append(format_row(entry))
    kept.sort(key=lambda r: cells(r)[-1])  # chronological by Created (always last)
    write_index(index_path, kept)

    print(f"{action} demo entry in {index_path}")
    print(f"  Weak spot: {ws_id}: {entry['weak_spot_description']}")
    print(f"  Demo: {entry['demo_filename']}")
    print(f"  Total entries: {len(kept)}")


def cmd_validate(demos_dir: Path) -> None:
    """Validate the demo index for issues."""
    index_path = demos_dir / "index.md"
    if not index_path.exists():
        print(f"Error: {index_path} does not exist", file=sys.stderr)
        sys.exit(1)

    rows = read_rows(index_path)
    if not rows:
        print(f"OK — index exists but has no entries: {index_path}")
        return

    issues = []
    seen_ids = set()
    for row in rows:
        c = cells(row)
        ws_id = c[0].split(":")[0].strip()
        if not re.match(r"^WS-\d+$", ws_id):
            continue  # hand-written row — not this script's to check

        if ws_id in seen_ids:
            issues.append(f"Duplicate weak spot: {ws_id}")
        seen_ids.add(ws_id)

        demo_link = LINK_RE.search(c[1])
        if not demo_link:
            issues.append(f"Malformed demo link for {ws_id}: {c[1]}")
        elif not (demos_dir / demo_link.group(1)).exists():
            issues.append(f"Missing demo file: {demo_link.group(1)} (for {ws_id})")

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", c[-1]):
            issues.append(f"Invalid date format for {ws_id}: {c[-1]}")

        ref_link = LINK_RE.search(c[2])
        if ref_link and not (demos_dir / ref_link.group(1)).exists():
            issues.append(f"Missing reference file: {ref_link.group(1)} (for {ws_id})")

    if not issues:
        print(f"OK — {len(rows)} entries, no issues found in {index_path}")
        return

    print(f"Found {len(issues)} issue(s) in {index_path}:\n")
    for issue in issues:
        print(f"  - {issue}")
    print()
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_demos_dir(path_arg: str) -> Path:
    """Resolve to a docs/demos/ directory path."""
    p = Path(path_arg)
    if p.is_file():
        return p.parent
    return p


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic index writer for docs/demos/index.md",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # append
    p_append = subparsers.add_parser("append", help="Append a demo entry from JSON")
    p_append.add_argument("path", help="Path to docs/demos/ directory")
    p_append.add_argument("--json", dest="json_str", help="Demo entry JSON string")
    p_append.add_argument("--stdin", action="store_true", help="Read demo JSON from stdin")

    # validate
    p_validate = subparsers.add_parser("validate", help="Check index for issues")
    p_validate.add_argument("path", help="Path to docs/demos/ directory")

    args = parser.parse_args()
    demos_dir = _resolve_demos_dir(args.path)

    if args.command == "append":
        if args.stdin:
            raw = sys.stdin.read()
        elif args.json_str:
            raw = args.json_str
        else:
            print("Error: provide --json or --stdin", file=sys.stderr)
            sys.exit(1)

        try:
            entry = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON — {e}", file=sys.stderr)
            sys.exit(1)

        if not isinstance(entry, dict):
            print("Error: JSON must be a single demo entry object", file=sys.stderr)
            sys.exit(1)

        cmd_append(demos_dir, entry)

    elif args.command == "validate":
        cmd_validate(demos_dir)


if __name__ == "__main__":
    main()
