# Sage Hooks

Native manifests select `claude-hooks.json` or `codex-hooks.json`. Each invokes
`tools/host_hooks.py` directly with an explicit host and event. Runtime hooks
require Python 3.8+; Bash/jq are not dependencies of this path.

| Event or operation | Behavior | Regression coverage |
|---|---|---|
| SessionStart | Supplies host, parent session ID and loaded plugin root; does not activate Sage | `test_host_hooks.py` |
| Explicit session activation | Binds the selected learning root/topic; independent of cwd | `test_session_context.py` |
| Verification operation completion | Resets reminder cycle; successful verify-cards sets a lifecycle marker | `test_reset_verification.py` |
| Checkpoint operation start | Warns about cards without a verification marker; consumes the marker | `test_checkpoint_guard.py` |
| Stop | Warns once after five responses; blocks stale cross-references for active Sage sessions | `test_verification_counter.py`, `test_enforce_cross_refs.py` |
| SessionEnd | Best-effort active-state cleanup | `test_host_hooks.py` |

The shared specialist start/completion tools are required by the coaching
protocol. Native subagent events alone do not prove which operation ran or that
verification succeeded, and a generic host need not expose an operation prompt.
Explicit tokens support native, generic, and inline workers. Only correlate an
agent ID with an exact token; never guess the latest pending worker.

Only stale cross-references block normal stopping. The card guard is advisory.
The cross-reference rule remains in `tools/cross_refs_check.py` and is called by
wrap-up even when hooks are disabled. A successful specialist completion marker
records execution, not factual truth. Inline verification remains self-checking.

State is stored under `~/.config/sage/runtime/<host>/<hashed-parent-id>/`, with
atomic writes and locking. Unrelated sessions remain inactive, even inside the
learning directory. Missing parent identity produces a diagnostic and never
selects another session. Recursive stop hooks are ignored. Identifiable active
sessions report validation/access errors rather than implying a clean check.

To inspect state, run `session_context.py --host <host> --session-id <parent> inspect`
under the installed `tools/` directory. Get the real parent identity from startup
context; do not guess. See `skills/sage/references/ref-host-session.md` for the
complete operation lifecycle and close protocol.

Legacy shell filenames remain delegating development shims, requiring explicit
`SAGE_HOST`; native plugin manifests do not use them. Their former `/tmp` state
format is retired. Updates change hook hashes: use the host's review controls,
then start a new session. Automatic safeguards require trusted/enabled hooks.
