#!/usr/bin/env bash
# Legacy entrypoint. Native plugin hooks call the Python adapter directly.
# Explicit host required; never infer identity or use a global root slot.
set -eu
: "${SAGE_HOST:?Pass claude-code or codex as SAGE_HOST}"
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec python3 "$SCRIPT_ROOT/tools/host_hooks.py" --host "$SAGE_HOST" --event Stop
