#!/usr/bin/env bash
# PreToolUse hook on Agent: warns if artifact-clerk checkpoint is
# called but new cards haven't been verified this session.
#
# This is a soft guard (warning, not block) — the coach may
# legitimately checkpoint without new cards.

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')

# Only care about Agent tool calls
if [ "$TOOL_NAME" != "Agent" ]; then
  exit 0
fi

SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty')
PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // empty')

# Only care about artifact-clerk checkpoint calls
if [ "$SUBAGENT_TYPE" != "artifact-clerk" ]; then
  exit 0
fi

if ! echo "$PROMPT" | grep -qi "checkpoint"; then
  exit 0
fi

# Check if new cards are mentioned in the checkpoint prompt
if ! echo "$PROMPT" | grep -qi "card"; then
  # No cards mentioned — nothing to guard
  exit 0
fi

# Cards are mentioned — check if they were verified
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')
CARDS_FLAG="/tmp/claude-cards-verified-${SESSION_ID}"

if [ ! -f "$CARDS_FLAG" ]; then
  # Cards mentioned but not verified — warn
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "[CHECKPOINT GUARD] This checkpoint includes new cards but verify-cards was not called this session. Per protocol: verify new flashcards through the verification-gate before including them in the checkpoint."
  }
}
EOF
fi

# Clear the flag for next checkpoint cycle
rm -f "$CARDS_FLAG"

exit 0
