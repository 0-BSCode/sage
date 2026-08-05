#!/usr/bin/env bash
# Link this working tree into every Host's skill directory.
#
# For development only. Users install via the plugin manifests
# (`.claude-plugin/`, `.codex-plugin/`) — one command per Host.
#
# Each link points at this repo, so `git pull` keeps every Host current.
# Pointing all Hosts at one tree also removes the shared-/tmp-slot ambiguity
# described in KNOWN-ISSUES.md, because there is only one plugin root to write.
#
# Re-run after adding, removing, or renaming a skill.
#
# Usage: scripts/link-skills.sh [--dry-run]

set -euo pipefail

DRY_RUN=false
[ "${1:-}" = "--dry-run" ] && DRY_RUN=true

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/skills"

if [ ! -d "$SKILLS_DIR" ]; then
  echo "error: no skills/ directory at $REPO_ROOT" >&2
  exit 1
fi

# Agent Skills standard location first — Codex reads ~/.codex/skills, which is
# itself commonly a symlink into ~/.agents/skills.
TARGETS=(
  "$HOME/.agents/skills"
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
)

link_one() {
  local src="$1" dest="$2" name="$3"

  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    echo "  skip  $name → $dest exists and is not a symlink"
    return
  fi

  if [ "$DRY_RUN" = true ]; then
    echo "  would link $name → $dest"
    return
  fi

  ln -sfn "$src" "$dest"
  echo "  linked $name → $dest"
}

for target in "${TARGETS[@]}"; do
  if [ ! -d "$(dirname "$target")" ]; then
    echo "$target — parent missing, Host not installed, skipping"
    continue
  fi

  mkdir -p "$target"
  echo "$target"

  for skill in "$SKILLS_DIR"/*/; do
    [ -f "$skill/SKILL.md" ] || continue
    name="$(basename "$skill")"
    link_one "${skill%/}" "$target/$name" "$name"
  done
done

echo
echo "Export SAGE_ROOT to pin the plugin root for this shell:"
echo "  export SAGE_ROOT=\"$REPO_ROOT\""
