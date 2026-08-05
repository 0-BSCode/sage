# Hooks are advisory; the one real invariant moves into the tools

Porting Sage to a second **Host** raised the question of what breaks when a host has no
hook system. `AGENT-AGNOSTIC.md` had claimed correctness depended on Claude Code firing
hooks, and that enforcement must therefore be migrated into `tools/` before any port.
Reading the four scripts showed that was true of one hook, not four:

- `checkpoint-guard.sh` — self-described "soft guard (warning, not block)"
- `verification-counter.sh` — emits a `systemMessage`
- `reset-verification.sh` — writes a flag file, renders no verdict
- `enforce-cross-refs.sh` — the only `"decision": "block"` in the repo

So three hooks are ergonomics and one is an invariant. The invariant is also the cheapest
to relocate: it compares mtimes of files under the **Learning Root** and needs no
transcript, session id, or host API — host-neutral logic that happens to live in a
Claude-only file.

The decision: the check is extracted to `tools/cross_refs_check.py`, which owns the rule and
is called from two places — `session_wrapup.py` (returning `cross_refs_stale` in its result,
which the end-of-session checklist acts on) and `enforce-cross-refs.sh`, now a thin trigger
that resolves the Learning Root, gates on cwd, and shells to the tool. The guarantee holds
wherever the wrapup runs; the hook only makes it automatic and blocking on Hosts that have
one. The other three hooks stay advisory ergonomics and are allowed to be absent elsewhere —
a Host without them loses nudges, not guarantees. `AGENT-AGNOSTIC.md` is retired.

Two things follow from putting the rule in Python. The check no longer depends on `find`,
`stat -c`, or GNU-flavored `grep`, so it is portable to any Host that can run the engine at
all. And `session_wrapup.py`'s existing tests plus `tests/test_enforce_cross_refs.py` (which
drives the hook end to end, and therefore the tool through it) cover one implementation
instead of two.

We considered two alternatives:

- **Full move-2-first** (migrate all four hooks' enforcement into `tools/`, add a
  `build-adapters.js` generator and a drift guard, as `AGENT-AGNOSTIC.md` proposed) —
  rejected: three advisory nudges do not justify a code generator, and the doc's premise
  was measurably wrong.
- **Port the hooks as-is and change nothing** (as `multi-host-support.md` proposed) —
  rejected: it leaves the sole hard invariant depending on Codex's hook trust gate, which
  the same doc lists as an unknown. Relocating ~15 lines removes the question entirely.
