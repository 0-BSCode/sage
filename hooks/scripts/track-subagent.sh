#!/bin/bash
# SubagentStop hook: extracts token usage from a subagent's transcript
# JSONL and appends to the project's learning/logs/ directory.
# Falls back to $HOME/.claude/logs/ if no learning/ directory exists.

set -euo pipefail

INPUT=$(cat)

AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // "unknown"')
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // "unknown"')
TRANSCRIPT=$(echo "$INPUT" | jq -r '.agent_transcript_path // ""')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')

if [[ -z "$TRANSCRIPT" || ! -f "$TRANSCRIPT" ]]; then
  exit 0
fi

# Route logs to project's learning/logs/ or global fallback
if [[ -n "${CLAUDE_PROJECT_DIR:-}" && -d "$CLAUDE_PROJECT_DIR/learning" ]]; then
  LOG_DIR="$CLAUDE_PROJECT_DIR/learning/logs"
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
