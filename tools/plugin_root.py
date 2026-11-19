#!/usr/bin/env python3
"""Resolve a loaded Sage skill, never a working directory or global /tmp slot."""
import argparse
from pathlib import Path


def validate(root):
    root = Path(root).expanduser().resolve(strict=True)
    for relative in ('skills/sage/SKILL.md', 'tools/session_router.py',
                     'agents/artifact-clerk.md'):
        if not (root / relative).is_file():
            raise ValueError('Not a complete Sage plugin: %s' % root)
    return root


def resolve(skill_file, override=None):
    skill = Path(skill_file).expanduser().resolve(strict=True)
    if skill.name != 'SKILL.md':
        raise ValueError('Pass the absolute path of the loaded SKILL.md')
    return validate(override if override else skill.parents[2])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('skill_file')
    parser.add_argument('--root', help='Explicit development override')
    args = parser.parse_args()
    try:
        print(resolve(args.skill_file, args.root))
    except (ValueError, OSError) as exc:
        parser.exit(1, '%s\n' % exc)
