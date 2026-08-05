# Sage Hooks

## Debugging

To see whether a hook fired and which branch it took, run it under `bash -x`
with a sample event on stdin:

```bash
echo '{"session_id":"test","cwd":"'"$PWD"'","stop_hook_active":false}' \
  | bash -x hooks/scripts/enforce-cross-refs.sh
```

## Hook Reference

One config, `claude-codex-hooks.json`, serves both Claude Code and Codex — both
support these events and the same stdin/stdout JSON contract, and Codex normalizes
the event names itself (`SubagentStart` → `subagent_start`).

| Hook | Event | Script | Purpose |
|------|-------|--------|---------|
| Verification counter | Stop | `scripts/verification-counter.sh` | Counts coach messages since last verification-gate call. Warns at 5+. |
| Reset verification | SubagentStop | `scripts/reset-verification.sh` | Resets counter when a verification-gate Clerk is called. Creates counter file on first call. |
| Checkpoint guard | SubagentStart | `scripts/checkpoint-guard.sh` | Guards checkpoint calls. |
| Enforce cross-refs | Stop | `scripts/enforce-cross-refs.sh` | Blocks session end if knowledge maps were modified but cross-refs/ wasn't updated. |

## Design notes

**Only one hook enforces anything.** `enforce-cross-refs.sh` is the sole
`"decision": "block"`; the other three are advisory. That check therefore lives in
`tools/cross_refs_check.py` and is called by `session_wrapup.py` too, so it holds on
Hosts with no hook system — the hook is only the automatic trigger. See
`docs/adr/0006-hooks-are-advisory-invariants-live-in-tools.md`.

**Clerk identification is Host-neutral.** Sage registers no Codex agents, so
`agent_type` is generic there. Both agent-keyed scripts match on the registered type
*or* the spec pointer the prose delegation carries in the prompt:

```bash
IDENT=$(jq -r '.agent_type // .tool_input.subagent_type // empty')
PROMPT=$(jq -r '.prompt // .tool_input.prompt // empty')
case "$IDENT$PROMPT" in *verification-gate*) ;; *) exit 0 ;; esac
```

Unverified on Codex: whether its `SubagentStart` payload carries a prompt. If not,
these two hooks no-op there — advisory only, so the cost is lost nudges.

**All scripts fail open** — unparseable stdin, a jq error, or an empty payload exits 0.
A hook must never wedge a session on an untested Host. Each is also capped by a 5s
`timeout` in the config.

## Known Issues

- ~~`reset-verification.sh` matches `subagent_type == "verification-gate"` but namespaced invocations use `"sage:verification-gate"`. Same for `"artifact-clerk"` vs `"sage:artifact-clerk"`. The counter file never gets created, so the verification overdue warning never fires.~~ **Fixed** — the identity-or-prompt match above matches a substring, so both bare and namespaced forms hit, and the spec-path fallback sidesteps namespacing entirely.
- State files are `/tmp/sage-*` (renamed from `/tmp/claude-*` in v1.2.0 — they are Sage's own state, and the old name read as wrong on every non-Claude Host).
