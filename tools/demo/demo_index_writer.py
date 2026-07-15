#!/usr/bin/env python3
"""Deterministic index writer for docs/demos/index.html.

Manages the demo index file in a guaranteed canonical HTML format.
The demo-generator agent produces demo content; this script enforces
index formatting, deduplication, and validation.

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
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Canonical index template
# ---------------------------------------------------------------------------

INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive Demos</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 0.5rem; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f5f5f5; }}
        a {{ color: #0066cc; }}
    </style>
</head>
<body>
    <h1>Interactive Demos</h1>
    <p>Targeted demos for persistent weak spots. Each demo corrects a specific wrong mental model.</p>
    <table>
        <thead>
            <tr>
                <th>Weak Spot</th>
                <th>Demo</th>
                <th>Related Reference</th>
                <th>Created</th>
            </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
    </table>
</body>
</html>
"""

ROW_TEMPLATE = (
    '            <tr>\n'
    '                <td>{weak_spot_id}: {weak_spot_description}</td>\n'
    '                <td><a href="{demo_filename}">{demo_title}</a></td>\n'
    '                <td>{ref_cell}</td>\n'
    '                <td>{created_date}</td>\n'
    '            </tr>'
)

# Regex to extract existing rows from the tbody
ROW_RE = re.compile(
    r"<tr>\s*"
    r"<td>(WS-\d+):\s*(.*?)</td>\s*"
    r"<td><a\s+href=\"(.*?)\">(.*?)</a></td>\s*"
    r"<td>(.*?)</td>\s*"
    r"<td>(\d{4}-\d{2}-\d{2})</td>\s*"
    r"</tr>",
    re.DOTALL,
)

REF_LINK_RE = re.compile(r'<a\s+href="(.*?)">(.*?)</a>')

NO_REF_TEXT = "No reference doc yet"


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def parse_existing_rows(html: str) -> List[Dict[str, str]]:
    """Parse existing demo entries from the index HTML."""
    rows = []
    for m in ROW_RE.finditer(html):
        ref_cell_raw = m.group(5).strip()
        ref_match = REF_LINK_RE.search(ref_cell_raw)

        rows.append({
            "weak_spot_id": m.group(1),
            "weak_spot_description": m.group(2).strip(),
            "demo_filename": m.group(3),
            "demo_title": m.group(4).strip(),
            "related_reference": ref_match.group(1) if ref_match else "",
            "created_date": m.group(6),
        })
    return rows


def format_ref_cell(related_reference: str) -> str:
    """Format the related reference cell content."""
    if not related_reference or related_reference == "—":
        return NO_REF_TEXT
    # Extract concept name from slug: ref-hypothesis-testing.md -> Hypothesis Testing
    name = related_reference
    name = re.sub(r"^ref-", "", name)
    name = re.sub(r"\.md$", "", name)
    name = name.replace("-", " ").title()
    return f'<a href="../references/{related_reference}">{name}</a>'


def format_row(entry: Dict[str, str]) -> str:
    """Format a single table row."""
    return ROW_TEMPLATE.format(
        weak_spot_id=entry["weak_spot_id"],
        weak_spot_description=entry["weak_spot_description"],
        demo_filename=entry["demo_filename"],
        demo_title=entry["demo_title"],
        ref_cell=format_ref_cell(entry.get("related_reference", "")),
        created_date=entry["created_date"],
    )


def build_index(rows: List[Dict[str, str]]) -> str:
    """Build the complete index.html from a list of row entries."""
    if not rows:
        row_html = ""
    else:
        row_html = "\n".join(format_row(r) for r in rows) + "\n"
    return INDEX_TEMPLATE.format(rows=row_html)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_append(demos_dir: Path, entry: Dict[str, Any]) -> None:
    """Append a new demo entry to the index."""
    # Validate required fields
    required = ["weak_spot_id", "weak_spot_description", "demo_title",
                "demo_filename", "created_date"]
    missing = [f for f in required if not entry.get(f)]
    if missing:
        print(f"Error: missing required fields: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # Validate weak_spot_id format
    if not re.match(r"^WS-\d+$", entry["weak_spot_id"]):
        print(f"Error: weak_spot_id must match WS-<number>, got: {entry['weak_spot_id']}",
              file=sys.stderr)
        sys.exit(1)

    # Validate demo file exists
    demo_path = demos_dir / entry["demo_filename"]
    if not demo_path.exists():
        print(f"Warning: demo file not found: {demo_path}", file=sys.stderr)

    index_path = demos_dir / "index.html"

    # Parse existing or start fresh
    if index_path.exists():
        html = index_path.read_text(encoding="utf-8")
        rows = parse_existing_rows(html)
    else:
        rows = []

    # Check for duplicate WS-number — update if exists
    existing_idx = None
    for i, row in enumerate(rows):
        if row["weak_spot_id"] == entry["weak_spot_id"]:
            existing_idx = i
            break

    clean_entry = {
        "weak_spot_id": entry["weak_spot_id"],
        "weak_spot_description": entry["weak_spot_description"],
        "demo_title": entry["demo_title"],
        "demo_filename": entry["demo_filename"],
        "related_reference": entry.get("related_reference", ""),
        "created_date": entry["created_date"],
    }

    if existing_idx is not None:
        rows[existing_idx] = clean_entry
        action = "Updated"
    else:
        rows.append(clean_entry)
        action = "Appended"

    # Sort by created date (chronological)
    rows.sort(key=lambda r: r["created_date"])

    # Write
    index_path.write_text(build_index(rows), encoding="utf-8")

    print(f"{action} demo entry in {index_path}")
    print(f"  Weak spot: {clean_entry['weak_spot_id']}: {clean_entry['weak_spot_description']}")
    print(f"  Demo: {clean_entry['demo_filename']}")
    print(f"  Total entries: {len(rows)}")


def cmd_validate(demos_dir: Path) -> None:
    """Validate the demo index for issues."""
    index_path = demos_dir / "index.html"
    if not index_path.exists():
        print(f"Error: {index_path} does not exist", file=sys.stderr)
        sys.exit(1)

    html = index_path.read_text(encoding="utf-8")
    rows = parse_existing_rows(html)
    issues = []

    if not rows:
        print(f"OK — index exists but has no entries: {index_path}")
        return

    seen_ids = set()
    for row in rows:
        # Check for duplicate WS-numbers
        if row["weak_spot_id"] in seen_ids:
            issues.append(f"Duplicate weak spot: {row['weak_spot_id']}")
        seen_ids.add(row["weak_spot_id"])

        # Check demo file exists
        demo_path = demos_dir / row["demo_filename"]
        if not demo_path.exists():
            issues.append(f"Missing demo file: {row['demo_filename']} (for {row['weak_spot_id']})")

        # Check date format
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", row["created_date"]):
            issues.append(f"Invalid date format for {row['weak_spot_id']}: {row['created_date']}")

        # Check reference file exists (if specified)
        if row["related_reference"]:
            ref_path = demos_dir.parent / "references" / row["related_reference"]
            if not ref_path.exists():
                issues.append(f"Missing reference file: {row['related_reference']} (for {row['weak_spot_id']})")

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
        description="Deterministic index writer for docs/demos/index.html",
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
