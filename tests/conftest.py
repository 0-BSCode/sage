"""Shared pytest configuration and fixtures for ultralearn tests."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
HOOKS_DIR = REPO_ROOT / "hooks" / "scripts"

# Add tool directories to sys.path so modules can be imported directly.
# Existing tests already do this per-file; this centralizes it for new tests.
for subdir in ["srs", "assessment", "coach", "plateau", "demo"]:
    p = str(TOOLS_DIR / subdir)
    if p not in sys.path:
        sys.path.insert(0, p)

# Top-level tools/ for session_metrics, mcp_server
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
