#!/usr/bin/env bash
# SubagentStop hook: resets the verification counter when a
# verification-gate Clerk is called. Also marks card verification
# for the checkpoint guard.
#
# Activates the counter on first verification-gate call in a session.
#
# Host-neutral: the Clerk is identified by the registered agent type
# (Claude: .tool_input.subagent_type, Codex: .agent_type) OR by the spec
# pointer the prose delegation carries in the prompt. Matching the spec
# path also sidesteps the plugin-namespace prefix problem that forced
# glob-suffix matching here (see hooks/README.md).
#
# Fails open: unparseable stdin or a missing jq exits 0 rather than
# blocking a session on an untested Host.

set -uo pipefail

INPUT=$(cat 2>/dev/null) || exit 0
[ -n "$INPUT" ] || exit 0

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
IDENT=$(echo "$INPUT" | jq -r '.agent_type // .tool_input.subagent_type // empty' 2>/dev/null) || exit 0
PROMPT=$(echo "$INPUT" | jq -r '.prompt // .tool_input.prompt // empty' 2>/dev/null) || exit 0

COUNTER_FILE="/tmp/sage-verif-counter-${SESSION_ID}"
WARNED_FILE="/tmp/sage-verif-warned-${SESSION_ID}"

# Reset on artifact-clerk checkpoint (end of teaching phase)
case "$IDENT$PROMPT" in
  *artifact-clerk*)
    if echo "$PROMPT" | grep -qi "checkpoint"; then
      if [ -f "$COUNTER_FILE" ]; then
        echo "0" > "$COUNTER_FILE"
      fi
      rm -f "$WARNED_FILE"
    fi
    exit 0
    ;;
esac

case "$IDENT$PROMPT" in
  *verification-gate*) ;;
  *) exit 0 ;;
esac

# Reset the message counter (creates it if first call)
echo "0" > "$COUNTER_FILE"

# Clear warned flag
rm -f "$WARNED_FILE"

# If this was a verify-cards operation, mark it for the checkpoint guard
if echo "$PROMPT" | grep -qi "verify-cards"; then
  CARDS_FLAG="/tmp/sage-cards-verified-${SESSION_ID}"
  echo "1" > "$CARDS_FLAG"
fi

exit 0
