# Sage Hooks

## Debug Log

All hook scripts write timestamped traces to `/tmp/sage-hook-debug.log`. Check this file to verify whether hooks fired and which branch they took.

```bash
cat /tmp/sage-hook-debug.log
```

Each entry: `HH:MM:SS <hook-name>: <outcome>`.

## Hook Reference

| Hook | Event | Script | Purpose |
|------|-------|--------|---------|
| Verification counter | Stop | `scripts/verification-counter.sh` | Counts coach messages since last verification-gate call. Warns at 5+. |
| Reset verification | PostToolUse (Agent) | `scripts/reset-verification.sh` | Resets counter when verification-gate agent is called. Creates counter file on first call. |
| Checkpoint guard | PreToolUse (Agent) | `scripts/checkpoint-guard.sh` | Guards checkpoint calls. |
| Enforce cross-refs | Stop | `scripts/enforce-cross-refs.sh` | Blocks session end if knowledge maps were modified but cross-refs/ wasn't updated. |
| Track subagent | SubagentStop | `scripts/track-subagent.sh` | Tracks subagent token consumption. |

## Known Issues

- `reset-verification.sh` matches `subagent_type == "verification-gate"` but namespaced invocations use `"sage:verification-gate"`. Same for `"artifact-clerk"` vs `"sage:artifact-clerk"`. The counter file never gets created, so the verification overdue warning never fires.
