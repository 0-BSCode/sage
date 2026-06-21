#!/usr/bin/env python3
"""Scan ultralearning decks for strict question-text duplicates.

Walks all `learning/cards.md` files under a configurable root and reports
groups of cards that share the same normalized question text. Read-only —
makes no modifications. The user reviews the report and manually retires
duplicates by editing cards.md.

Strict normalization only (lowercase, whitespace collapse, trailing
punctuation strip). Different question phrasings of the same fact are NOT
detected; that is intentional. Fuzzy/semantic detection is out of scope.

Retired cards (`### Card N [RETIRED]`) are excluded from comparison.

Usage:
    python3 find_duplicate_cards.py [--root <path>]

Defaults to ~/Documents/codes/labs/ultralearn/.

Exit code is always 0 — this is a report tool, not a CI gate.

Zero external dependencies — Python 3.8+ stdlib only.
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

# Import shared helpers from the sibling card_writer module so normalization
# stays in lockstep with the writer's dedup logic.
sys.path.insert(0, str(Path(__file__).parent))
from card_writer import (  # noqa: E402
    normalize_question,
    parse_existing_cards,
)


DEFAULT_ROOT = Path.home() / "Documents/codes/labs/ultralearn"


def find_decks(root: Path) -> List[Path]:
    """Find all learning/cards.md files under the root."""
    return sorted(root.glob("*/learning/cards.md"))


def scan_deck(path: Path) -> Dict[str, List[Dict]]:
    """Scan one deck. Return {normalized_q: [card_records]} for groups >1."""
    text = path.read_text(encoding="utf-8")
    cards = parse_existing_cards(text)

    groups: Dict[str, List[Dict]] = defaultdict(list)
    for card in cards:
        if card["retired"]:
            continue
        normalized = normalize_question(card["question"])
        if not normalized:
            continue
        groups[normalized].append(card)

    return {k: v for k, v in groups.items() if len(v) > 1}


def format_deck_report(deck_path: Path, root: Path, duplicate_groups: Dict[str, List[Dict]]) -> str:
    """Format the per-deck section of the report."""
    try:
        rel = deck_path.relative_to(root)
    except ValueError:
        rel = deck_path

    lines = [f"=== {rel} ==="]

    if not duplicate_groups:
        lines.append("No duplicates found.")
        lines.append("")
        return "\n".join(lines)

    total_dupes = sum(len(group) for group in duplicate_groups.values())
    lines.append(
        f"Found {len(duplicate_groups)} duplicate group(s) "
        f"covering {total_dupes} cards."
    )
    lines.append("")

    for normalized, group in sorted(duplicate_groups.items()):
        lines.append(
            f"Duplicate group ({len(group)} cards): \"{normalized}\""
        )
        for card in sorted(group, key=lambda c: c["number"]):
            q_preview = card["question"]
            if len(q_preview) > 100:
                q_preview = q_preview[:97] + "..."
            lines.append(f"  - card-{card['number']}: {q_preview}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan ultralearning decks for strict question-text duplicates."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"Root directory to scan (default: {DEFAULT_ROOT})",
    )
    args = parser.parse_args()

    if not args.root.exists():
        print(f"Error: root directory does not exist: {args.root}", file=sys.stderr)
        sys.exit(1)

    decks = find_decks(args.root)
    if not decks:
        print(f"No decks found under {args.root} (looked for */learning/cards.md)")
        return

    print(f"Scanning {len(decks)} deck(s) under {args.root}\n")

    total_decks_with_dupes = 0
    total_groups = 0
    total_dupe_cards = 0

    for deck in decks:
        groups = scan_deck(deck)
        if groups:
            total_decks_with_dupes += 1
            total_groups += len(groups)
            total_dupe_cards += sum(len(g) for g in groups.values())
        print(format_deck_report(deck, args.root, groups))

    # Summary footer
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Decks scanned:          {len(decks)}")
    print(f"Decks with duplicates:  {total_decks_with_dupes}")
    print(f"Duplicate groups total: {total_groups}")
    print(f"Cards in dup groups:    {total_dupe_cards}")


if __name__ == "__main__":
    main()
