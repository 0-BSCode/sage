#!/bin/bash
# Stop hook: blocks session end if knowledge maps were modified
# but the cross-reference registry wasn't updated.
# Only fires when cwd is under the Learning Root.
#
# The check itself lives in tools/cross_refs_check.py so it holds on Hosts
# with no hook system — this script is only the automatic trigger on Claude
# and Codex. See docs/adr/0006-hooks-are-advisory-invariants-live-in-tools.md.
#
# Fails open: unparseable stdin or a missing jq exits 0 rather than
# blocking a session on an untested Host.

set -uo pipefail

SAGE_DIR="${SAGE_DIR:-$(cat /tmp/.sage-learning-root 2>/dev/null)}"
if [ -z "$SAGE_DIR" ]; then
  exit 0
fi

SAGE_ROOT="${SAGE_ROOT:-$(cat /tmp/.sage-plugin-root 2>/dev/null)}"
if [ -z "$SAGE_ROOT" ]; then
  exit 0
fi

INPUT=$(cat 2>/dev/null) || exit 0
[ -n "$INPUT" ] || exit 0

CWD=$(echo "$INPUT" | jq -r '.cwd // ""' 2>/dev/null) || exit 0
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // empty' 2>/dev/null) || exit 0

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# Only fire under the Learning Root (or a subdirectory)
if [[ "$CWD" != "$SAGE_DIR"* ]]; then
  exit 0
fi

REASON=$(python3 "$SAGE_ROOT/tools/cross_refs_check.py" "$SAGE_DIR" 2>/dev/null) || exit 0

if [ -n "$REASON" ]; then
  jq -n --arg reason "$REASON" '{decision: "block", reason: $reason}'
fi

exit 0
