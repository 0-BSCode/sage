#!/usr/bin/env python3
"""Current-sitting wall time for a Sage session, from its transcript.

Resolves the Claude Code transcript **by session id**, then computes the duration
of the CURRENT sitting: the last timestamp minus the first timestamp after the
most recent gap > SITTING_GAP_SECONDS. Compact/resume keeps the same session id
and appends to the same file, so a naive first->last would span days across
sittings.

Transcript resolution, in order:

1. An explicit session id argument, if given.
2. ``$CLAUDE_CODE_SESSION_ID`` — Claude Code puts this in the environment and it
   is inherited by subprocesses, so no plumbing is needed.

   Either way the id is looked up as ``~/.claude/projects/*/<id>.jsonl``. A known
   id that resolves to nothing is a HARD FAILURE — the tool will not fall back to
   guessing, because a duration from the wrong session is indistinguishable from a
   correct one once it reaches the journal.

3. No id at all (manual invocation from a terminal): fall back to the newest
   .jsonl in the directory derived from the cwd, and warn on stderr that the
   answer was guessed.

Note that the <cwd-slug> directory name encodes the directory Claude Code was
LAUNCHED in, not the current one — and the Bash tool persists ``cd`` across calls.
That is why the slug is not used to find the transcript: any ``cd`` during the
session would silently repoint the lookup at a directory that never existed.

Usage:
    python3 session_duration.py [session_id]

Prints the formatted duration (e.g. "42m15s") to stdout on success.
Exits non-zero with no stdout, and a message naming the specific failure, if no
transcript or timestamps can be resolved.

Zero external dependencies — Python 3.8+ stdlib only.
"""

import datetime
import glob
import json
import os
import re
import sys

SITTING_GAP_SECONDS = 30 * 60  # a quiet gap longer than this starts a new sitting
SESSION_ID_ENV = "CLAUDE_CODE_SESSION_ID"


def projects_root():
    return os.path.join(os.path.expanduser("~"), ".claude", "projects")


def project_dir(cwd=None):
    """Transcript directory for a working directory, using Claude Code's encoding.

    Only used by the no-id fallback — see the module docstring for why this is not
    the primary lookup.
    """
    cwd = cwd if cwd is not None else os.getcwd()
    slug = re.sub(r"[^a-zA-Z0-9]", "-", cwd)
    return os.path.join(projects_root(), slug)


def resolve_transcript(session_id="", cwd=None):
    """Locate the transcript. Returns (path, error, warning); path is None on failure.

    An id — explicit or from the environment — is authoritative: if it resolves to
    nothing, that is an error, never a reason to guess.
    """
    sid = session_id or os.environ.get(SESSION_ID_ENV, "")
    source = "argument" if session_id else f"${SESSION_ID_ENV}"

    if sid:
        matches = glob.glob(os.path.join(projects_root(), "*", f"{sid}.jsonl"))
        if not matches:
            return None, (
                f"session id {sid} (from {source}): no transcript found under "
                f"{os.path.join(projects_root(), '*')}/ — refusing to guess"
            ), None
        warning = None
        if len(matches) > 1:
            warning = (
                f"session id {sid} matched {len(matches)} transcripts; "
                f"using the most recently modified"
            )
        return max(matches, key=os.path.getmtime), None, warning

    # No id at all — manual invocation. Guess, but say so.
    pdir = project_dir(cwd)
    if not os.path.isdir(pdir):
        return None, (
            f"no session id (${SESSION_ID_ENV} unset, none given) and no transcript "
            f"directory for cwd '{cwd if cwd is not None else os.getcwd()}' "
            f"(looked in {pdir})"
        ), None

    files = glob.glob(os.path.join(pdir, "*.jsonl"))
    if not files:
        return None, f"transcript directory {pdir} contains no .jsonl files", None

    newest = max(files, key=os.path.getmtime)
    return newest, None, (
        f"no session id; guessed newest transcript in {pdir} "
        f"({os.path.basename(newest)}) — may belong to another session"
    )


def find_transcript(session_id="", cwd=None):
    """Path to the transcript, or None. Thin wrapper over resolve_transcript()."""
    return resolve_transcript(session_id, cwd)[0]


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


def compute(session_id="", cwd=None):
    """Return (duration, error, warning). duration is None on failure."""
    path, error, warning = resolve_transcript(session_id, cwd)
    if path is None:
        return None, error, warning

    sitting = current_sitting(parse_timestamps(path))
    if not sitting:
        return None, f"transcript {path} has no parseable timestamps", warning

    start, end = sitting
    ms = int((end - start).total_seconds() * 1000)
    return fmt_duration(ms), None, warning


def run(session_id="", cwd=None):
    """Formatted duration, or None. Thin wrapper over compute()."""
    return compute(session_id, cwd)[0]


def main():
    session_id = sys.argv[1] if len(sys.argv) > 1 else ""
    duration, error, warning = compute(session_id=session_id)
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    if duration is None:
        print(error or "No transcript or timestamps found", file=sys.stderr)
        sys.exit(1)
    print(duration)


if __name__ == "__main__":
    main()
