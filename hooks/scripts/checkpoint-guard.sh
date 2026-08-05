#!/usr/bin/env bash
# SubagentStart hook: warns if an artifact-clerk checkpoint is called
# but new cards haven't been verified this session.
#
# This is a soft guard (warning, not block) — the coach may
# legitimately checkpoint without new cards.
#
# Host-neutral: the Clerk is identified by the registered agent type
# (Claude: .tool_input.subagent_type, Codex: .agent_type) OR by the spec
# pointer the prose delegation carries in the prompt. Codex spawns
# unregistered subagents, so the prompt is the only signal there.
#
# Fails open: unparseable stdin or a missing jq exits 0 rather than
# blocking a session on an untested Host.

set -uo pipefail

INPUT=$(cat 2>/dev/null) || exit 0
[ -n "$INPUT" ] || exit 0

IDENT=$(echo "$INPUT" | jq -r '.agent_type // .tool_input.subagent_type // empty' 2>/dev/null) || exit 0
PROMPT=$(echo "$INPUT" | jq -r '.prompt // .tool_input.prompt // empty' 2>/dev/null) || exit 0

# Only care about artifact-clerk checkpoint calls
case "$IDENT$PROMPT" in
  *artifact-clerk*) ;;
  *) exit 0 ;;
esac

if ! echo "$PROMPT" | grep -qi "checkpoint"; then
  exit 0
fi

# Check if new cards are mentioned in the checkpoint prompt
if ! echo "$PROMPT" | grep -qi "card"; then
  # No cards mentioned — nothing to guard
  exit 0
fi

# Cards are mentioned — check if they were verified
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
CARDS_FLAG="/tmp/sage-cards-verified-${SESSION_ID}"

if [ ! -f "$CARDS_FLAG" ]; then
  # Cards mentioned but not verified — warn
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "[CHECKPOINT GUARD] This checkpoint includes new cards but verify-cards was not called this session. Per protocol: verify new flashcards through the verification-gate before including them in the checkpoint."
  }
}
EOF
fi

# Clear the flag for next checkpoint cycle
rm -f "$CARDS_FLAG"

exit 0
