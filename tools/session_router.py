#!/usr/bin/env python3
"""Session router for Sage.

Single entry point for every `/sage` invocation. The grammar is
`/sage <verb> <topic>` with exactly two verbs, `learn` and `archive`.
The verb is mandatory; there is no verb-less form. The router parses it,
resolves config, and returns structured JSON so the coach can branch on
`mode` without multiple tool calls. It is a read-only dispatcher — it
never mutates the filesystem. Archival mutation lives in
`archive_project.py`, which the coach invokes on `mode: "archive"`.

Usage:
    python3 session_router.py <sage_root> <verb> [topic...]

Zero external dependencies — Python 3.8+ stdlib only.
"""

import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from config import get_learning_root


# The only two valid verbs. Everything else is an error.
VERBS = {"learn", "archive"}

# Pre-verb-grammar resume keywords. No longer valid; kept only so the
# router can point users at the new `learn` verb.
LEGACY_RESUME_KEYWORDS = {"continue", "resume", "pick", "list"}


def parse_invocation(raw):
    """Split raw args into (verb, topic_string). Verb is lowercased."""
    parts = raw.strip().split()
    if not parts:
        return "", ""
    verb = parts[0].lower()
    rest = " ".join(parts[1:]).strip()
    return verb, rest


def list_projects(learning_root, require="journal"):
    """Scan for existing projects. Returns list sorted by last session date.

    `require` selects the existence predicate, because the two pickers ask
    different questions:
      - "journal" (default) — projects with session history, i.e. something
        to *resume*. Gate: `learning/journal/index.md`. Used by `learn`.
      - "plan" — any *initialized* project, whether or not a session ever
        ran. Gate: `learning/plan.md`. Used by `archive`, so a project you
        set up but never started is still archivable.
    """
    marker = os.path.join("journal", "index.md") if require == "journal" else "plan.md"
    projects = []
    if not os.path.isdir(learning_root):
        return projects

    for entry in sorted(os.listdir(learning_root)):
        # Skip hidden entries (notably `.archive/`, where archived
        # projects live) so archived projects never appear in discovery.
        if entry.startswith("."):
            continue
        project_learning = os.path.join(learning_root, entry, "learning")
        if not os.path.isfile(os.path.join(project_learning, marker)):
            continue

        # Best-effort last-session date from the journal index (a plan-only
        # project has none — it sorts last).
        last_date = None
        journal_index = os.path.join(project_learning, "journal", "index.md")
        try:
            with open(journal_index, "r") as f:
                for line in f:
                    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", line)
                    if date_match:
                        last_date = date_match.group(1)
        except OSError:
            pass

        projects.append({
            "slug": entry,
            "last_session": last_date,
        })

    projects.sort(key=lambda p: p.get("last_session") or "", reverse=True)
    return projects


def derive_slug(topic):
    """Convert topic name to a filesystem-safe slug."""
    slug = topic.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def find_journal(topic_path):
    """Check for existing journal. Returns path if found, None otherwise."""
    current = os.path.join(topic_path, "journal", "index.md")
    if os.path.isfile(current):
        return current
    return None


def find_plan(topic_path):
    """Check for a learning plan — the marker of an initialized project.

    Returns the path if found, None otherwise. This is the archivability
    predicate: a project counts as archivable once it has a plan, even if
    no session ever ran."""
    plan = os.path.join(topic_path, "plan.md")
    if os.path.isfile(plan):
        return plan
    return None


def suggest_slug(slug, learning_root):
    """Closest archivable project slug to a no-match archive target, or None."""
    existing = [p["slug"] for p in list_projects(learning_root, require="plan")]
    matches = difflib.get_close_matches(slug, existing, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _unknown_verb(verb, topic, sage_root):
    """Build a helpful error for an unrecognized leading verb."""
    if verb in LEGACY_RESUME_KEYWORDS:
        hint = f"/sage learn {topic}".strip()
        message = f"'{verb}' is no longer a command. Did you mean `{hint}`?"
        suggestion = "learn"
    else:
        # Most likely a legacy bare-topic invocation like `/sage react hooks`.
        full = f"{verb} {topic}".strip()
        message = (
            f"Unknown verb '{verb}'. Commands now require a verb: "
            f"`/sage learn {full}` to learn it, or `/sage archive <topic>` to archive it."
        )
        suggestion = None
    return {
        "mode": "unknown_verb",
        "verb": verb,
        "suggestion": suggestion,
        "message": message,
        "sage_root": sage_root,
    }


def route(sage_root, raw_args):
    """Resolve invocation mode and return structured result."""
    verb, topic = parse_invocation(raw_args)
    learning_root = get_learning_root()

    if verb == "":
        return {
            "mode": "unknown_verb",
            "verb": "",
            "suggestion": None,
            "message": "Usage: `/sage learn <topic>` or `/sage archive <topic>`.",
            "sage_root": sage_root,
        }

    if verb not in VERBS:
        return _unknown_verb(verb, topic, sage_root)

    if not learning_root:
        return {
            "mode": "needs_config",
            "verb": verb,
            "sage_root": sage_root,
        }

    learning_root_str = str(learning_root)

    # Bare verb with no topic → the project picker. `action` tells the
    # coach what to do with the learner's selection. `learn` lists
    # resumable projects (journal); `archive` lists any initialized
    # project (plan).
    if not topic:
        return {
            "mode": "pick",
            "action": verb,
            "projects": list_projects(
                learning_root_str, require="plan" if verb == "archive" else "journal"
            ),
            "learning_root": learning_root_str,
            "sage_root": sage_root,
        }

    slug = derive_slug(topic)
    project_path = os.path.join(learning_root_str, slug)
    topic_path = os.path.join(project_path, "learning")
    journal = find_journal(topic_path)

    if verb == "learn":
        if journal:
            has_insights = os.path.isfile(
                os.path.join(topic_path, "coach-insights.md")
            )
            return {
                "mode": "resume",
                "slug": slug,
                "learning_root": learning_root_str,
                "topic_path": topic_path,
                "project_path": project_path,
                "sage_root": sage_root,
                "has_coach_insights": has_insights,
            }
        return {
            "mode": "fresh",
            "slug": slug,
            "learning_root": learning_root_str,
            "topic_path": topic_path,
            "project_path": project_path,
            "sage_root": sage_root,
        }

    # verb == "archive": target must resolve to an initialized project
    # (has a learning plan) — session history is not required.
    if not find_plan(topic_path):
        return {
            "mode": "archive_no_match",
            "slug": slug,
            "suggestion": suggest_slug(slug, learning_root_str),
            "learning_root": learning_root_str,
            "sage_root": sage_root,
        }
    return {
        "mode": "archive",
        "slug": slug,
        "learning_root": learning_root_str,
        "topic_path": topic_path,
        "project_path": project_path,
        "sage_root": sage_root,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: session_router.py <sage_root> <verb> [topic...]", file=sys.stderr)
        sys.exit(1)

    sage_root = sys.argv[1]
    raw_args = " ".join(sys.argv[2:])

    result = route(sage_root, raw_args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
