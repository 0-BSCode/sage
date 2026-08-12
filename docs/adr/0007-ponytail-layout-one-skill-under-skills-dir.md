# Move the skill under `skills/sage/` and ship a plugin per Host

Sage's Claude manifest declared `"skills": ["./"]` — the repo root *was* the skill. Codex's
plugin manifest takes `skills` as a single path string pointing at a *container* directory
holding skill subdirectories (verified: ponytail ships `skills/ponytail/SKILL.md`,
`skills/ponytail-audit/SKILL.md`, …). With `SKILL.md` at the repo root, Codex would scan for
skill subdirectories and find none. Supporting Codex therefore required a `skills/sage/`
directory.

**Only `SKILL.md` and `references/` moved.** An earlier draft of this ADR said `agents/` and
`tools/` moved too; implementing it showed both must stay at the plugin root:

- `agents/` is how **Claude Code registers subagents** — a plugin's Clerks are discovered at
  the plugin root by convention, with no `agents` key in the manifest (verified against
  `oh-my-claudecode`, which ships `"skills": "./skills/"` *and* a root `agents/`). Moving it
  would have silently unregistered all six Clerks.
- `tools/` is addressed as `$SAGE_ROOT/tools/…`, and `$SAGE_ROOT` is the plugin root.
  `references/` moves *because* it is addressed relative to `SKILL.md`.

So `$SAGE_ROOT` keeps its existing meaning, `SessionStart` still writes
`${CLAUDE_PLUGIN_ROOT}` unchanged, the thirty prose sites that read it are untouched, and no
test path moved. The restructure is a two-directory `git mv` plus one manifest line.

We now ship `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` side by side, both
pointing at one `hooks/claude-codex-hooks.json`. Install is one command per Host.
`${CLAUDE_PLUGIN_ROOT}` expands on both, and Codex normalizes event names
(`SubagentStart` → `subagent_start`), so no per-Host hook config and no event remap.
Future cleanup: replace that compatibility placeholder when the Hosts share a neutral
hook-root placeholder; Sage's internal name remains `$SAGE_ROOT`.

The split does put two different `agents/` directories in the tree: `agents/` at the root
(the six Clerk specs, read by Claude) and `skills/sage/agents/` (holding only `openai.yaml`,
Codex's skill-adjacent metadata, following mattpocock/skills' convention). Confusing enough
to note; not confusing enough to fight either Host over.
`tests/test_plugin_manifests.py` fails if any of this drifts.

mattpocock/skills looks like a counterexample — it restructured to `skills/<bucket>/<name>/`
but shipped no Codex plugin, and its ADR 0002 cites the single-path `skills` field. That
constraint does not apply here. Its Claude manifest is a hand-curated 22-entry array that
deliberately excludes `deprecated/`, `in-progress/`, and `personal/`; a single path string
cannot express that curation. Sage ships exactly one skill, so `"skills": "./skills/"` over
a directory containing only `sage/` ships precisely what is intended.

We considered one alternative:

- **Stay flat; install by symlink to `~/.agents/skills/sage` or `npx skills add`** — no
  moves, but no plugin manifest and therefore no hooks on Codex. Rejected: it trades a
  four-line change for permanent install friction, and the `git mv` becomes unavoidable the
  first time a second Sage skill ships.
