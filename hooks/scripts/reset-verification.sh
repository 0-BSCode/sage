#!/usr/bin/env bash
# PostToolUse hook on Agent: resets the verification counter when
# a verification-gate agent is called. Also marks card verification
# for the checkpoint guard.
#
# Activates the counter on first verification-gate call in a session.

set -euo pipefail

DEBUG_LOG="/tmp/sage-hook-debug.log"
INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')

# Only care about Agent tool calls
if [ "$TOOL_NAME" != "Agent" ]; then
  exit 0
fi

SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty')
PROMPT=$(echo "$INPUT" | jq -r '.tool_input.prompt // empty')

# Reset on artifact-clerk checkpoint (end of teaching phase)
if [[ "$SUBAGENT_TYPE" == *"artifact-clerk" ]]; then
  if echo "$PROMPT" | grep -qi "checkpoint"; then
    COUNTER_FILE="/tmp/claude-verif-counter-${SESSION_ID}"
    if [ -f "$COUNTER_FILE" ]; then
      echo "0" > "$COUNTER_FILE"
    fi
    WARNED_FILE="/tmp/claude-verif-warned-${SESSION_ID}"
    rm -f "$WARNED_FILE"
  fi
  exit 0
fi

if [[ "$SUBAGENT_TYPE" != *"verification-gate" ]]; then
  echo "$(date '+%H:%M:%S') reset-verif: skip — subagent_type=$SUBAGENT_TYPE (not verification-gate)" >> "$DEBUG_LOG"
  exit 0
fi

# Reset the message counter (creates it if first call)
echo "$(date '+%H:%M:%S') reset-verif: RESET counter (subagent_type=$SUBAGENT_TYPE)" >> "$DEBUG_LOG"
COUNTER_FILE="/tmp/claude-verif-counter-${SESSION_ID}"
echo "0" > "$COUNTER_FILE"

# Clear warned flag
WARNED_FILE="/tmp/claude-verif-warned-${SESSION_ID}"
rm -f "$WARNED_FILE"

# If this was a verify-cards operation, mark it for the checkpoint guard
if echo "$PROMPT" | grep -qi "verify-cards"; then
  CARDS_FLAG="/tmp/claude-cards-verified-${SESSION_ID}"
  echo "1" > "$CARDS_FLAG"
fi

exit 0
