#!/bin/bash
# SubagentStop hook: extracts token usage from a subagent's transcript
# JSONL and appends to <learning-root>/logs/subagent-tokens.jsonl.
# Learning root is read from /tmp/.sage-learning-root (set by SessionStart hook).
# Falls back to $HOME/.claude/logs/ if learning root is unavailable.

set -euo pipefail

INPUT=$(cat)

AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // "unknown"')
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // "unknown"')
TRANSCRIPT=$(echo "$INPUT" | jq -r '.agent_transcript_path // ""')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')

if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
  exit 0
fi

# Route logs to learning root (from sage config) or global fallback
SAGE_LEARNING_ROOT=$(cat /tmp/.sage-learning-root 2>/dev/null)
if [[ -n "$SAGE_LEARNING_ROOT" && -d "$SAGE_LEARNING_ROOT" ]]; then
  LOG_DIR="$SAGE_LEARNING_ROOT/logs"
else
  LOG_DIR="$HOME/.claude/logs"
fi
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/subagent-tokens.jsonl"

USAGE=$(jq -s '
  [ .[] | select(.type == "assistant") | .message.usage // empty ]
  | {
      input_tokens: (map(.input_tokens // 0) | add),
      output_tokens: (map(.output_tokens // 0) | add),
      cache_creation_tokens: (map(.cache_creation_input_tokens // 0) | add),
      cache_read_tokens: (map(.cache_read_input_tokens // 0) | add)
    }
' "$TRANSCRIPT")

echo "$USAGE" | jq -c \
  --arg agent_type "$AGENT_TYPE" \
  --arg agent_id "$AGENT_ID" \
  --arg session_id "$SESSION_ID" \
  --arg timestamp "$(date -Iseconds)" \
  '. + {agent_type: $agent_type, agent_id: $agent_id, session_id: $session_id, timestamp: $timestamp}' \
  >> "$LOG_FILE"
