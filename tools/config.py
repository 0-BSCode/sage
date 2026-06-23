#!/usr/bin/env python3
"""Sage config reader.

Resolves the learning root path with this precedence:
    SAGE_LEARNING_ROOT env var > ~/.config/sage/config.json > None

When run as a script, prints the learning root path (or exits silently if unset).

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


def save_config(learning_root):
    """Write the config file with the given learning root."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = load_config()
    config["learning_root"] = str(learning_root)
    config.setdefault("version", 1)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def get_learning_root():
    """Resolve the learning root. Returns a Path or None."""
    env_val = os.environ.get("SAGE_LEARNING_ROOT")
    if env_val:
        return Path(env_val)

    config = load_config()
    root = config.get("learning_root")
    if root:
        return Path(root)

    return None


if __name__ == "__main__":
    root = get_learning_root()
    if root:
        print(root)
    else:
        sys.exit(1)
