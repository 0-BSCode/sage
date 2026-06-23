#!/bin/bash
# Stop hook: blocks session end if knowledge maps were modified
# but cross-reference registry wasn't updated.
# Only fires when cwd is the sage repo.
# Supports both sharded cross-refs/ directory and legacy cross-references.md.

set -euo pipefail

SAGE_DIR="${SAGE_DIR:-$(cat /tmp/.sage-learning-root 2>/dev/null)}"
if [ -z "$SAGE_DIR" ]; then
  exit 0
fi
THRESHOLD=1800  # 30 minutes

INPUT=$(cat)

CWD=$(echo "$INPUT" | jq -r '.cwd // ""')
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active')

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# Only fire in the sage repo (or a subdirectory)
if [[ "$CWD" != "$SAGE_DIR"* ]]; then
  exit 0
fi

CROSS_REFS_DIR="${SAGE_DIR}/cross-refs"
CR_FILE="${SAGE_DIR}/cross-references.md"

NOW=$(date +%s)

# Check if any knowledge-map.md was modified within threshold
KM_MODIFIED=false
while IFS= read -r km; do
  KM_MTIME=$(stat -c %Y "$km" 2>/dev/null || echo 0)
  KM_AGE=$((NOW - KM_MTIME))
  if [ "$KM_AGE" -lt "$THRESHOLD" ]; then
    KM_MODIFIED=true
    break
  fi
done < <(find "$SAGE_DIR" -name "knowledge-map.md" 2>/dev/null)

if [ "$KM_MODIFIED" != "true" ]; then
  exit 0
fi

# Knowledge map modified — check if cross-refs were updated too
CR_UPDATED=false

# Check sharded cross-refs/ directory (preferred)
if [ -d "$CROSS_REFS_DIR" ]; then
  while IFS= read -r cr; do
    CR_MTIME=$(stat -c %Y "$cr" 2>/dev/null || echo 0)
    CR_AGE=$((NOW - CR_MTIME))
    if [ "$CR_AGE" -lt "$THRESHOLD" ]; then
      CR_UPDATED=true
      break
    fi
  done < <(find "$CROSS_REFS_DIR" -name "*.md" 2>/dev/null)
# Fall back to legacy monolithic file
elif [ -f "$CR_FILE" ]; then
  CR_MTIME=$(stat -c %Y "$CR_FILE" 2>/dev/null || echo 0)
  CR_AGE=$((NOW - CR_MTIME))
  if [ "$CR_AGE" -lt "$THRESHOLD" ]; then
    CR_UPDATED=true
  fi
fi

# Knowledge map modified but cross-references weren't — block
if [ "$CR_UPDATED" != "true" ]; then
  cat <<'EOF'
{
  "decision": "block",
  "reason": "Knowledge map(s) were modified this session but cross-refs/ was not updated. Per CLAUDE.md Cross-Reference Protocol: upsert any concept that reached Developing or higher into cross-refs/<project>.md before ending the session."
}
EOF
fi

exit 0
