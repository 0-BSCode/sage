#!/usr/bin/env python3
"""Archive a Sage Project.

Retires a Project (its on-disk container) by moving the whole directory
under `<learning_root>/.archive/<slug>/`, co-locating its cross-ref shard
there, and scrubbing every reference to it from the cross-refs `INDEX.md`.
Archival is one-way-but-recoverable: nothing is deleted, and the removed
INDEX fragments + provenance are stashed in `archive-meta.json` inside the
archive directory. See adr/0003-archive-by-move-recoverable.md.

This tool is STATELESS and assumes a QUIESCENT project — the coach must
checkpoint any live session for this slug before invoking it.

Usage:
    python3 archive_project.py <learning_root> <slug> [--date YYYY-MM-DD]

Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import json
import os
import shutil
import sys


# ---------------------------------------------------------------------------
# Pure helpers (no filesystem side effects) — unit-tested directly.
# ---------------------------------------------------------------------------

def _split_overlaps(cell):
    """Parse an 'Overlaps With' cell into a list of project slugs.

    Empty / em-dash / hyphen placeholders mean 'no overlaps' → []."""
    cell = cell.strip()
    if cell in ("", "-", "—", "–"):
        return []
    return [tok.strip() for tok in cell.split(",") if tok.strip()]


def _join_overlaps(tokens):
    """Render a list of slugs back into a cell value, '—' when empty."""
    return ", ".join(tokens) if tokens else "—"


def _is_table_row(line):
    return line.lstrip().startswith("|")


def _is_separator_row(line):
    return set(line.strip()) <= set("|-: ")


def parse_index(text, slug):
    """Scrub `slug` from a cross-refs INDEX.md.

    Removes the project's own row and strips it from every other row's
    'Overlaps With' cell. Returns (new_text, fragments) where fragments is:
        {
          "own_row": "<raw own row line or None>",
          "own_overlaps": [<slugs the archived project overlapped>],
          "inbound": [{"project": <slug>, "row": <raw line before edit>}, ...],
        }

    Non-table lines (title, blockquote, blanks) and the header/separator
    rows are preserved verbatim. Idempotent: scrubbing an absent slug is a
    no-op that returns empty fragments.
    """
    fragments = {"own_row": None, "own_overlaps": [], "inbound": []}
    out_lines = []
    header_seen = False

    for line in text.split("\n"):
        if not _is_table_row(line) or _is_separator_row(line):
            out_lines.append(line)
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # Header row (the one naming the columns) — pass through once.
        if not header_seen and cells and cells[0].lower() == "project":
            header_seen = True
            out_lines.append(line)
            continue

        if len(cells) < 2:
            out_lines.append(line)
            continue

        project, overlaps_cell = cells[0], cells[1]

        if project == slug:
            # The archived project's own row — drop it, stash its overlaps.
            fragments["own_row"] = line
            fragments["own_overlaps"] = _split_overlaps(overlaps_cell)
            continue

        tokens = _split_overlaps(overlaps_cell)
        if slug in tokens:
            fragments["inbound"].append({"project": project, "row": line})
            tokens = [t for t in tokens if t != slug]
            out_lines.append(f"| {project} | {_join_overlaps(tokens)} |")
        else:
            out_lines.append(line)

    return "\n".join(out_lines), fragments


def next_archive_dir(archive_base, slug):
    """Lowest non-colliding archive directory name for `slug`.

    Returns an absolute path: `<archive_base>/<slug>` if free, else
    `<archive_base>/<slug>-2`, `-3`, ... Deterministic → testable."""
    candidate = os.path.join(archive_base, slug)
    if not os.path.exists(candidate):
        return candidate
    n = 2
    while True:
        candidate = os.path.join(archive_base, f"{slug}-{n}")
        if not os.path.exists(candidate):
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Orchestrator (filesystem side effects).
# ---------------------------------------------------------------------------

def archive_project(learning_root, slug, date=None):
    """Archive the Project `slug`. Returns a summary dict.

    Raises ValueError if the project does not resolve to an existing
    directory (never half-moves)."""
    project_path = os.path.join(learning_root, slug)
    if not os.path.isdir(project_path):
        raise ValueError(f"No project directory at {project_path}")

    cross_refs_dir = os.path.join(learning_root, "cross-refs")
    index_path = os.path.join(cross_refs_dir, "INDEX.md")
    shard_path = os.path.join(cross_refs_dir, f"{slug}.md")

    # 1. Compute INDEX edits in memory first — no writes yet, so a later
    #    filesystem failure can never leave a corrupted INDEX behind.
    new_index = None
    fragments = {"own_row": None, "own_overlaps": [], "inbound": []}
    if os.path.isfile(index_path):
        with open(index_path, "r") as f:
            new_index, fragments = parse_index(f.read(), slug)

    # 2. Resolve a non-colliding archive destination.
    archive_base = os.path.join(learning_root, ".archive")
    os.makedirs(archive_base, exist_ok=True)
    dest = next_archive_dir(archive_base, slug)

    # 3. Move the project directory (the big irreversible-ish step).
    shutil.move(project_path, dest)

    # 4. Co-locate the cross-ref shard, if any.
    shard_moved = False
    if os.path.isfile(shard_path):
        shutil.move(shard_path, os.path.join(dest, "cross-refs.md"))
        shard_moved = True

    # 5. Write the recovery stash + provenance.
    inbound_projects = [item["project"] for item in fragments["inbound"]]
    meta = {
        "original_slug": slug,
        "archived_date": date,
        "archived_dir": os.path.basename(dest),
        "index": {
            "own_row": fragments["own_row"],
            "own_overlaps": fragments["own_overlaps"],
            "inbound_rows": fragments["inbound"],
        },
        "inbound_ref_count": len(inbound_projects),
        "shard_archived": shard_moved,
    }
    with open(os.path.join(dest, "archive-meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # 6. Write the scrubbed INDEX last.
    if new_index is not None:
        with open(index_path, "w") as f:
            f.write(new_index)

    return {
        "status": "archived",
        "slug": slug,
        "archived_dir": dest,
        "shard_archived": shard_moved,
        "index_own_row_removed": fragments["own_row"] is not None,
        "inbound_refs_scrubbed": inbound_projects,
        "inbound_ref_count": len(inbound_projects),
    }


def main():
    parser = argparse.ArgumentParser(description="Archive a Sage Project.")
    parser.add_argument("learning_root", help="Absolute path to the learning root")
    parser.add_argument("slug", help="Project slug to archive")
    parser.add_argument(
        "--date",
        default=None,
        help="Archived date (YYYY-MM-DD), passed in by the coach for determinism",
    )
    args = parser.parse_args()

    try:
        summary = archive_project(args.learning_root, args.slug, date=args.date)
    except ValueError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
