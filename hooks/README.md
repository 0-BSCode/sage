# Sage Hooks

## Debugging

To see whether a hook fired and which branch it took, run it under `bash -x`
with a sample event on stdin:

```bash
echo '{"session_id":"test","cwd":"'"$PWD"'","stop_hook_active":false}' \
  | bash -x hooks/scripts/enforce-cross-refs.sh
```

## Hook Reference

| Hook | Event | Script | Purpose |
|------|-------|--------|---------|
| Verification counter | Stop | `scripts/verification-counter.sh` | Counts coach messages since last verification-gate call. Warns at 5+. |
| Reset verification | PostToolUse (Agent) | `scripts/reset-verification.sh` | Resets counter when verification-gate agent is called. Creates counter file on first call. |
| Checkpoint guard | PreToolUse (Agent) | `scripts/checkpoint-guard.sh` | Guards checkpoint calls. |
| Enforce cross-refs | Stop | `scripts/enforce-cross-refs.sh` | Blocks session end if knowledge maps were modified but cross-refs/ wasn't updated. |

## Known Issues

- ~~`reset-verification.sh` matches `subagent_type == "verification-gate"` but namespaced invocations use `"sage:verification-gate"`. Same for `"artifact-clerk"` vs `"sage:artifact-clerk"`. The counter file never gets created, so the verification overdue warning never fires.~~ **Fixed** — now uses glob suffix match (`*"verification-gate"`, `*"artifact-clerk"`).
