#!/usr/bin/env python3
"""Deterministic card writer for cards.md.

Accepts card content as structured JSON and appends to cards.md in a
guaranteed canonical format. The LLM produces content; this script
enforces formatting.

Commands:
    append <path> --json '<json>'   Append new cards from JSON
    append <path> --stdin           Read card JSON from stdin
    validate <path>                 Check existing cards.md for format violations
    fix <path>                      Rewrite non-canonical format in-place

JSON input format (array of card objects):
    [
        {
            "question": "What is X?",
            "answer": "X is ...",
            "tags": ["tag1", "tag2"]
        }
    ]

Card numbering is auto-assigned (continues from the last card in the file).
The "Last updated" header line is updated automatically.

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
# Canonical format constants
# ---------------------------------------------------------------------------

CARD_TEMPLATE = """\
### Card {number}
**Q:** {question}
**A:** {answer}
{tags_line}
---"""

# Matches the date (YYYY-MM-DD) in any "Last updated" header line
HEADER_DATE_RE = re.compile(
    r"(Last updated.*?)\d{4}-\d{2}-\d{2}",
    re.MULTILINE | re.IGNORECASE,
)

CARD_HEADER_RE = re.compile(
    r"^###\s+Card\s+(\d+)",
    re.IGNORECASE | re.MULTILINE,
)

# Parses each card heading + Q line for dedup. Captures: number, optional
# [RETIRED] marker, question text up to (but not including) the **A:** line.
CARD_PARSE_RE = re.compile(
    r"^###\s+Card\s+(\d+)(\s*\[RETIRED\])?\s*\n\*\*Q:\*\*\s*(.+?)(?=\n\*\*A:\*\*)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

# Trailing punctuation stripped during normalization. Conservative — only
# obvious sentence-end markers.
_NORMALIZE_TRAILING = ".?!:"

# Approved card type tags. Every new card must carry exactly one.
APPROVED_CARD_TYPES = frozenset({
    "fact", "why", "process", "discrimination",
    "transfer", "reverse", "error",
})

# Format violations to detect
Q_BAD_RE = re.compile(r"\*\*Q\*\*:")   # colon outside bold
A_BAD_RE = re.compile(r"\*\*A\*\*:")
TAGS_BAD_RE = re.compile(r"\*\*Tags\*\*:")

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def find_last_card_number(text: str) -> int:
    """Find the highest card number in existing cards.md content."""
    numbers = [int(m.group(1)) for m in CARD_HEADER_RE.finditer(text)]
    return max(numbers) if numbers else 0


def normalize_question(text: str) -> str:
    """Normalize a card question for strict duplicate detection.

    Catches accidental verbatim duplicates (case differences, trailing
    punctuation, whitespace variation) without attempting fuzzy/semantic
    matching. Different question framings of the same fact (e.g., "What
    is X?" vs "Explain X") will produce different normalized forms and
    are NOT treated as duplicates here — that is by design.
    """
    s = text.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(_NORMALIZE_TRAILING).strip()
    return s


def parse_existing_cards(text: str) -> List[Dict[str, Any]]:
    """Parse cards.md content into a list of card records.

    Each record is {'number': int, 'question': str, 'retired': bool}.
    Used for duplicate detection and any future card-introspection needs.
    """
    cards = []
    for m in CARD_PARSE_RE.finditer(text):
        cards.append({
            "number": int(m.group(1)),
            "retired": m.group(2) is not None,
            "question": m.group(3).strip(),
        })
    return cards


def build_existing_question_index(text: str) -> Dict[str, int]:
    """Map normalized question -> card number for non-retired cards.

    Used by cmd_append to detect duplicates against the current deck.
    Retired cards are excluded so a previously-retired question can be
    re-added without being flagged.
    """
    index: Dict[str, int] = {}
    for card in parse_existing_cards(text):
        if card["retired"]:
            continue
        normalized = normalize_question(card["question"])
        if not normalized:
            continue
        # First-write wins: if two non-retired cards already share a normalized
        # form, keep the lower-numbered one as the canonical match. This case
        # shouldn't happen once dedup is in force.
        index.setdefault(normalized, card["number"])
    return index


def validate_type_tag(tags: List[str]) -> Optional[str]:
    """Check that tags contain exactly one approved type:<X> tag.

    Returns None if valid, or an error message string if invalid.
    Only used during append (new cards). Existing untyped cards are
    not affected.
    """
    type_tags = [t for t in tags if t.startswith("type:")]
    if len(type_tags) == 0:
        return "missing required type tag (expected one of: type:fact, type:why, type:process, type:discrimination, type:transfer, type:reverse, type:error)"
    if len(type_tags) > 1:
        return f"multiple type tags found ({', '.join(type_tags)}) — each card must have exactly one"
    value = type_tags[0].removeprefix("type:")
    if value not in APPROVED_CARD_TYPES:
        return f"unapproved type tag 'type:{value}' (approved values: {', '.join(sorted(APPROVED_CARD_TYPES))})"
    return None


def format_card(number: int, question: str, answer: str, tags: List[str]) -> str:
    """Format a single card in canonical format."""
    tags_line = f"**Tags:** {', '.join(tags)}" if tags else ""
    card = CARD_TEMPLATE.format(
        number=number,
        question=question.strip(),
        answer=answer.strip(),
        tags_line=tags_line,
    )
    # Clean up blank line if no tags
    card = re.sub(r"\n\n\n", "\n\n", card)
    return card


def update_header_date(text: str, today: str) -> str:
    """Update only the date in the 'Last updated' header line, preserving everything else."""
    if HEADER_DATE_RE.search(text):
        return HEADER_DATE_RE.sub(rf"\g<1>{today}", text, count=1)
    return text


def validate_cards_md(text: str) -> List[Dict[str, Any]]:
    """Check for format violations. Returns list of issues."""
    issues = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if Q_BAD_RE.match(stripped):
            issues.append({
                "line": i,
                "type": "bad_q_format",
                "text": stripped,
                "fix": stripped.replace("**Q**:", "**Q:**", 1),
            })
        if A_BAD_RE.match(stripped):
            issues.append({
                "line": i,
                "type": "bad_a_format",
                "text": stripped,
                "fix": stripped.replace("**A**:", "**A:**", 1),
            })
        if TAGS_BAD_RE.match(stripped):
            issues.append({
                "line": i,
                "type": "bad_tags_format",
                "text": stripped,
                "fix": stripped.replace("**Tags**:", "**Tags:**", 1),
            })
    return issues


def fix_cards_md(text: str) -> Tuple[str, int]:
    """Fix format violations in-place. Returns (fixed_text, fix_count)."""
    fixes = 0
    lines = text.splitlines()
    result = []
    for line in lines:
        stripped = line.strip()
        # Fix colon placement
        if Q_BAD_RE.match(stripped):
            line = line.replace("**Q**:", "**Q:**", 1)
            fixes += 1
        if A_BAD_RE.match(stripped):
            line = line.replace("**A**:", "**A:**", 1)
            fixes += 1
        if TAGS_BAD_RE.match(stripped):
            line = line.replace("**Tags**:", "**Tags:**", 1)
            fixes += 1
        result.append(line)
    return "\n".join(result), fixes


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_append(path: Path, cards_json: List[Dict[str, Any]]) -> None:
    """Append new cards to cards.md in canonical format."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    if not cards_json:
        print("No cards to append.")
        return

    text = path.read_text(encoding="utf-8")
    last_num = find_last_card_number(text)
    today = date.today().isoformat()

    # Build a normalized-Q index of the existing deck for strict duplicate
    # detection. Retired cards are excluded.
    existing_index = build_existing_question_index(text)

    # Build new cards. Strict-Q duplicates and type-tag violations are
    # skipped with a stderr notice — remaining valid cards still get written.
    new_cards = []
    skipped_duplicates: List[Tuple[str, int]] = []  # (incoming_q_preview, existing_card_num)
    skipped_type_errors: List[Tuple[str, str]] = []  # (incoming_q_preview, error_msg)
    next_num = last_num + 1
    for card in cards_json:
        q = card.get("question", "").strip()
        a = card.get("answer", "").strip()
        tags = card.get("tags", [])

        if not q or not a:
            print(f"Warning: skipping card — missing question or answer", file=sys.stderr)
            continue

        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        # Type tag validation — every new card must have exactly one approved type
        type_error = validate_type_tag(tags)
        if type_error:
            preview = q if len(q) <= 60 else q[:57] + "..."
            skipped_type_errors.append((preview, type_error))
            continue

        normalized = normalize_question(q)
        if normalized in existing_index:
            existing_num = existing_index[normalized]
            preview = q if len(q) <= 60 else q[:57] + "..."
            skipped_duplicates.append((preview, existing_num))
            continue

        # Reserve the number now so we don't collide with another incoming
        # card that has the same normalized form (intra-batch duplicates).
        existing_index[normalized] = next_num
        new_cards.append(format_card(next_num, q, a, tags))
        next_num += 1

    if skipped_type_errors:
        print(
            f"Rejected {len(skipped_type_errors)} card(s) with type tag errors:",
            file=sys.stderr,
        )
        for preview, error_msg in skipped_type_errors:
            print(
                f"  - \"{preview}\": {error_msg}",
                file=sys.stderr,
            )

    if skipped_duplicates:
        print(
            f"Skipped {len(skipped_duplicates)} duplicate card(s):",
            file=sys.stderr,
        )
        for preview, existing_num in skipped_duplicates:
            print(
                f"  - \"{preview}\" duplicates existing card-{existing_num}",
                file=sys.stderr,
            )

    if not new_cards:
        print("No valid cards to append.")
        return

    # Update header date
    text = update_header_date(text, today)

    # Ensure file ends with newline before appending
    if not text.endswith("\n"):
        text += "\n"

    # Ensure there's a separator before new cards
    if not text.rstrip().endswith("---"):
        text = text.rstrip() + "\n\n---\n\n"
    else:
        text = text.rstrip() + "\n\n"

    # Append all new cards
    text += "\n\n".join(new_cards) + "\n"

    path.write_text(text, encoding="utf-8")

    print(f"Appended {len(new_cards)} card(s) to {path}")
    print(f"Card numbers: {last_num + 1}–{last_num + len(new_cards)}")
    print(f"Last updated: {today}")


def cmd_validate(path: Path) -> None:
    """Check cards.md for format violations."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    issues = validate_cards_md(text)

    if not issues:
        print(f"OK — no format violations in {path}")
        return

    print(f"Found {len(issues)} format violation(s) in {path}:\n")
    for issue in issues:
        print(f"  Line {issue['line']}: [{issue['type']}]")
        print(f"    Found: {issue['text']}")
        print(f"    Fix:   {issue['fix']}")
        print()

    sys.exit(1)


def cmd_fix(path: Path) -> None:
    """Fix format violations in-place."""
    if not path.exists():
        print(f"Error: {path} does not exist", file=sys.stderr)
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    fixed_text, fix_count = fix_cards_md(text)

    if fix_count == 0:
        print(f"No fixes needed in {path}")
        return

    path.write_text(fixed_text, encoding="utf-8")
    print(f"Fixed {fix_count} issue(s) in {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_cards_md(path_arg: str) -> Path:
    """Resolve to a cards.md path from a directory or file path."""
    p = Path(path_arg)
    if p.is_dir():
        return p / "cards.md"
    return p


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic card writer for cards.md",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # append
    p_append = subparsers.add_parser("append", help="Append new cards from JSON")
    p_append.add_argument("path", help="Path to cards.md or its parent directory")
    p_append.add_argument("--json", dest="json_str", help="Card JSON string")
    p_append.add_argument("--stdin", action="store_true", help="Read card JSON from stdin")

    # validate
    p_validate = subparsers.add_parser("validate", help="Check for format violations")
    p_validate.add_argument("path", help="Path to cards.md or its parent directory")

    # fix
    p_fix = subparsers.add_parser("fix", help="Fix format violations in-place")
    p_fix.add_argument("path", help="Path to cards.md or its parent directory")

    args = parser.parse_args()
    path = _resolve_cards_md(args.path)

    if args.command == "append":
        if args.stdin:
            raw = sys.stdin.read()
        elif args.json_str:
            raw = args.json_str
        else:
            print("Error: provide --json or --stdin", file=sys.stderr)
            sys.exit(1)

        try:
            cards = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON — {e}", file=sys.stderr)
            sys.exit(1)

        if not isinstance(cards, list):
            print("Error: JSON must be an array of card objects", file=sys.stderr)
            sys.exit(1)

        cmd_append(path, cards)

    elif args.command == "validate":
        cmd_validate(path)

    elif args.command == "fix":
        cmd_fix(path)


if __name__ == "__main__":
    main()
