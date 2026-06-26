#!/usr/bin/env python3
"""Session router for Sage.

Single entry point for session start. Resolves config, derives slug,
checks for existing journal, and returns structured JSON so the coach
can branch on mode without multiple tool calls.

Usage:
    python3 session_router.py <sage_root> <topic>

Zero external dependencies — Python 3.8+ stdlib only.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from config import get_learning_root


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
    legacy = os.path.join(topic_path, "journal.md")
    if os.path.isfile(legacy):
        return legacy
    return None


def route(sage_root, topic):
    """Resolve session mode and return structured result."""
    slug = derive_slug(topic)

    learning_root = get_learning_root()
    if not learning_root:
        return {
            "mode": "needs_config",
            "slug": slug,
            "sage_root": sage_root,
        }

    learning_root_str = str(learning_root)
    topic_path = os.path.join(learning_root_str, slug, "learning")

    journal = find_journal(topic_path)
    if journal:
        has_insights = os.path.isfile(
            os.path.join(topic_path, "coach-insights.md")
        )
        return {
            "mode": "resume",
            "slug": slug,
            "learning_root": learning_root_str,
            "topic_path": topic_path,
            "sage_root": sage_root,
            "has_coach_insights": has_insights,
        }

    return {
        "mode": "fresh",
        "slug": slug,
        "learning_root": learning_root_str,
        "topic_path": topic_path,
        "sage_root": sage_root,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: session_router.py <sage_root> <topic>", file=sys.stderr)
        sys.exit(1)

    sage_root = sys.argv[1]
    topic = " ".join(sys.argv[2:])

    result = route(sage_root, topic)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
