#!/usr/bin/env bash
# Stop hook: counts coach messages since last verification-gate call.
# Warns when 5+ messages have passed without verification.
#
# State file: /tmp/claude-verif-counter-<session_id>
# The counter file is created by reset-verification.sh on the first
# verification-gate call. If it doesn't exist, this hook is a no-op
# (we're not in a session that uses verification).

set -euo pipefail

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active')
COUNTER_FILE="/tmp/claude-verif-counter-${SESSION_ID}"

# Prevent infinite loops
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# No counter file = not in a verification-tracked session
if [ ! -f "$COUNTER_FILE" ]; then
  exit 0
fi

# Increment counter
COUNT=$(cat "$COUNTER_FILE")
COUNT=$((COUNT + 1))
echo "$COUNT" > "$COUNTER_FILE"

# Warn once at 5+
if [ "$COUNT" -ge 5 ]; then
  WARNED_FILE="/tmp/claude-verif-warned-${SESSION_ID}"
  if [ ! -f "$WARNED_FILE" ]; then
    echo "1" > "$WARNED_FILE"
    cat <<EOF
{
  "continue": true,
  "systemMessage": "[VERIFICATION OVERDUE] ${COUNT} messages since last verification-gate call. Per the message-counter fallback rule: STOP, collect all factual claims made in recent messages, and batch-verify them before continuing."
}
EOF
  fi
fi
