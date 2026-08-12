#!/usr/bin/env python3
"""Cross-reference staleness check — the one Sage invariant that blocks.

If a knowledge map was modified this sitting and holds any concept at
Developing or higher, the cross-refs registry must have been updated too.

This lives in a tool rather than a hook because it is the only enforcing
check Sage has, and a Host without hooks would otherwise lose it silently.
The Claude/Codex `Stop` hook calls this as its automatic trigger; the
session-ending tool calls it directly so the guarantee holds everywhere.
See docs/adr/0006-hooks-are-advisory-invariants-live-in-tools.md.

Inputs are mtimes under the Learning Root — no transcript, no session id,
no Host API.

Usage:
    python3 cross_refs_check.py <learning-root>

Exit 0 and print nothing when the invariant holds; exit 0 and print the
reason when it does not (the caller decides whether to block).
"""

import os
import sys
import time

# ponytail: mtime window, not a change journal. A session longer than this
# with no kmap write looks unmodified. Swap for a manifest if that bites.
SITTING_THRESHOLD_SECONDS = 1800

REASON = (
    "Knowledge map(s) were modified this session but cross-refs/ was not "
    "updated. Per the Cross-Reference Protocol: upsert any concept that "
    "reached Developing or higher into cross-refs/<project>.md before "
    "ending the session."
)

PROMOTED_MARKERS = ("| developing |", "| solid |", "| mastered |")


def _recently_modified(path, now):
    try:
        return (now - os.path.getmtime(path)) < SITTING_THRESHOLD_SECONDS
    except OSError:
        return False


def _has_promoted_concept(path):
    try:
        with open(path, encoding="utf-8") as fh:
            lowered = fh.read().lower()
    except OSError:
        return False
    return any(marker in lowered for marker in PROMOTED_MARKERS)


def check(learning_root, now=None):
    """Return a reason string when cross-refs are stale, else None."""
    if not learning_root or not os.path.isdir(learning_root):
        return None

    now = time.time() if now is None else now

    touched = False
    for dirpath, _dirnames, filenames in os.walk(learning_root):
        if "knowledge-map.md" not in filenames:
            continue
        kmap = os.path.join(dirpath, "knowledge-map.md")
        if _recently_modified(kmap, now) and _has_promoted_concept(kmap):
            touched = True
            break

    if not touched:
        return None

    cross_refs = os.path.join(learning_root, "cross-refs")
    if os.path.isdir(cross_refs):
        for dirpath, _dirnames, filenames in os.walk(cross_refs):
            for name in filenames:
                if name.endswith(".md") and _recently_modified(
                    os.path.join(dirpath, name), now
                ):
                    return None

    return REASON


def main(argv):
    learning_root = argv[1] if len(argv) > 1 else ""
    reason = check(learning_root)
    if reason:
        print(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
