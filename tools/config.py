#!/usr/bin/env python3
"""Sage config reader.

Resolves the learning root path with this precedence:
    SAGE_LEARNING_ROOT env var > ~/.config/sage/config.json > None

Tilde (`~`) is expanded everywhere, and saved paths are stored absolute.

When run as a script:
    python3 config.py                    # print the resolved learning root, or exit 1 if unset
    python3 config.py --normalize PATH   # print PATH expanded + made absolute; writes nothing

Zero external dependencies — Python 3.8+ stdlib only.
"""

import json
import os
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "sage"
CONFIG_PATH = CONFIG_DIR / "config.json"


def load_config():
    """Read the config file. Returns dict or empty dict if missing/invalid."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def normalize_root(raw):
    """Expand `~` and make the path absolute. Returns a Path.

    Used to preview a learner-supplied path before saving (so typos and `~`
    expansion are visible) and to canonicalize the value `save_config` stores.
    """
    return Path(raw).expanduser().resolve()


def save_config(learning_root):
    """Normalize, create the directory tree, then persist. Returns the resolved Path.

    The learning root and its `cross-refs/` subdirectory are created BEFORE the
    config file is written. If the directory cannot be created (permissions, a
    path under an existing file, ...), the error propagates and nothing is
    persisted — so a later run re-prompts instead of resolving a broken path.
    """
    root = normalize_root(learning_root)

    # Create the tree first; a failure here must not leave a bad path in config.
    (root / "cross-refs").mkdir(parents=True, exist_ok=True)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = load_config()
    config["learning_root"] = str(root)
    config.setdefault("version", 1)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    return root


def get_learning_root():
    """Resolve the learning root. Returns a Path or None. Expands `~`."""
    env_val = os.environ.get("SAGE_LEARNING_ROOT")
    if env_val:
        return Path(env_val).expanduser()

    config = load_config()
    root = config.get("learning_root")
    if root:
        return Path(root).expanduser()

    return None


def main():
    args = sys.argv[1:]

    if args and args[0] == "--normalize":
        if len(args) < 2:
            print("Usage: config.py --normalize PATH", file=sys.stderr)
            sys.exit(2)
        print(normalize_root(args[1]))
        return

    root = get_learning_root()
    if root:
        print(root)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
