#!/usr/bin/env python3
"""Current-sitting wall time for a Sage session, from its transcript.

Reads the Claude Code transcript JSONL at
``~/.claude/projects/<cwd-slug>/<session-id>.jsonl`` and computes the duration of
the CURRENT sitting: the last timestamp minus the first timestamp after the most
recent gap > SITTING_GAP_SECONDS. Compact/resume keeps the same session id and
appends to the same file, so a naive first->last would span days across sittings.

The <cwd-slug> is the working directory with every non-alphanumeric character
replaced by '-' (Claude Code's encoding — e.g. ``/home/u/.claude`` -> ``-home-u--claude``).

Usage:
    python3 session_duration.py [session_id]

If session_id is given, that transcript is used; otherwise the most-recently
modified .jsonl in the project's transcript folder is used.

Prints the formatted duration (e.g. "42m15s") to stdout on success.
Exits non-zero with no stdout if no transcript or timestamps can be resolved.

Zero external dependencies — Python 3.8+ stdlib only.
"""

import datetime
import glob
import json
import os
import re
import sys

SITTING_GAP_SECONDS = 30 * 60  # a quiet gap longer than this starts a new sitting


def project_dir(cwd=None):
    cwd = cwd if cwd is not None else os.getcwd()
    slug = re.sub(r"[^a-zA-Z0-9]", "-", cwd)
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", slug)


def find_transcript(session_id="", cwd=None):
    pdir = project_dir(cwd)
    if session_id:
        candidate = os.path.join(pdir, f"{session_id}.jsonl")
        if os.path.isfile(candidate):
            return candidate
    files = glob.glob(os.path.join(pdir, "*.jsonl"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def parse_timestamps(path):
    stamps = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = entry.get("timestamp")
            if not ts:
                continue
            try:
                stamps.append(datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")))
            except ValueError:
                continue
    stamps.sort()
    return stamps


def current_sitting(stamps, gap_seconds=SITTING_GAP_SECONDS):
    """Return (start, end) of the last sitting, or None if there are no stamps.

    The sitting starts at the first timestamp following the most recent gap
    longer than gap_seconds (or the very first timestamp if no such gap exists).
    """
    if not stamps:
        return None
    start = stamps[0]
    for a, b in zip(stamps, stamps[1:]):
        if (b - a).total_seconds() > gap_seconds:
            start = b
    return start, stamps[-1]


def fmt_duration(ms):
    total_sec = ms // 1000
    hours = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours}h{mins:02d}m{secs:02d}s"
    elif mins > 0:
        return f"{mins}m{secs:02d}s"
    return f"{secs}s"


def run(session_id="", cwd=None):
    path = find_transcript(session_id, cwd)
    if not path:
        return None
    sitting = current_sitting(parse_timestamps(path))
    if not sitting:
        return None
    start, end = sitting
    ms = int((end - start).total_seconds() * 1000)
    return fmt_duration(ms)


def main():
    session_id = sys.argv[1] if len(sys.argv) > 1 else ""
    duration = run(session_id=session_id)
    if duration is None:
        print("No transcript or timestamps found", file=sys.stderr)
        sys.exit(1)
    print(duration)


if __name__ == "__main__":
    main()
