#!/usr/bin/env bash
# Stop hook: counts coach messages since last verification-gate call.
# Warns when 5+ messages have passed without verification.
#
# State file: /tmp/sage-verif-counter-<session_id>
# The counter file is created by reset-verification.sh on the first
# verification-gate call. If it doesn't exist, this hook is a no-op
# (we're not in a session that uses verification).
#
# Fails open: unparseable stdin or a missing jq exits 0 rather than
# blocking a session on an untested Host.

set -uo pipefail

INPUT=$(cat 2>/dev/null) || exit 0
[ -n "$INPUT" ] || exit 0

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // empty' 2>/dev/null) || exit 0
COUNTER_FILE="/tmp/sage-verif-counter-${SESSION_ID}"

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
  WARNED_FILE="/tmp/sage-verif-warned-${SESSION_ID}"
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
