# Known Issues

Tracked defects in the Sage plugin. Newest / most severe first.

---

## ✅ RESOLVED BY REMOVAL — Session token-metrics collector aggregated across sessions & projects

> **Resolved 2026-07-20.** The token-metrics system was **deleted rather than fixed**, per
> `context/done/REMOVE-SESSION-METRICS-PLAN.md`. None of the components below still exist:
> `tools/session_metrics.py`, `hooks/scripts/track-subagent.sh`, and
> `tests/test_session_metrics.py` are gone, and no `SubagentStop` hook is registered in
> `hooks/hooks.json`. The journal now records **Duration only**, derived from the Claude Code
> transcript by `tools/session_duration.py`.
>
> The diagnosis below is retained as history — it is the reasoning that justified removal, and
> the log-topology table still describes files that exist on disk. **None of the remediation
> options (A/B/C) were taken.**
>
> The removal plan sat marked "not started" long after it had shipped, and this entry stayed
> marked URGENT/OPEN for components that no longer existed. That staleness cost real work: it
> led the `session-duration-cwd-resolution` investigation to plan a shared fix with a sibling
> issue that had already been deleted.

- **Status:** RESOLVED by removal 2026-07-20 (originally: OPEN, fix deferred 2026-07-01; remediation of affected data done)
- **Severity:** was high — corrupted per-session cost/trend data that the resume brief and coach metrics relied on
- **Discovered:** Session 35, 2026-07-01 (learner noticed stale timestamps in a journal; then flagged a second affected journal)
- **Components (all since deleted):** `tools/session_metrics.py`, `hooks/scripts/track-subagent.sh`, `tools/session_wrapup.py`
- **Related tests (deleted):** `tests/test_session_metrics.py`, `tests/test_track_subagent.py`

### Symptom
The `### Token Metrics` block that `patch-metrics` appends to a session journal contains subagent-token log entries from **multiple prior sessions and other projects**, not just the current session. Example (auth-and-authz S35 journal): reported ~3.96M fresh tokens and 15 `artifact-clerk` invocations plus six agent types (`Explore`, `verification-gate`, `assessment-agent`, `doc-researcher`, `tldr-clerk`, `learning-git`) that were **never invoked that session**. The entries spanned 2026-06-26 → 2026-07-01 (sessions 32–35). Duration and context% were correct (they come from the main session metrics JSON, not the log).

### Root cause (two compounding defects)
1. **Consumer over-collects when unscoped.** `tools/session_metrics.py::parse_subagent_log(path, session_id="")` only filters by session when `session_id` is truthy:
   ```python
   if session_id and entry.get("session_id") != session_id:
       continue
   ```
   The end-of-session checklist invokes `session_wrapup.py` **without** `--session-id`, so `session_id=""` → the filter is skipped → the entire rolling, global `subagent-tokens.jsonl` (all sessions, all projects) is summed.

2. **Producer/consumer session-id spaces don't match.** `hooks/scripts/track-subagent.sh` (line 14) stamps each log line with the SubagentStop payload's `.session_id`. Empirically this id does **not** equal the main session id in `claude-session-metrics.json`. On 2026-07-01 the main session was `dc26b906-…`, but that session's own log lines were tagged with a different UUID — **0 matches**. So even if the consumer *were* passed the main session id, filtering would return **zero** entries (worse than over-collecting). This is why passing `--session-id` was effectively abandoned, leaving the unscoped fallback.

The log is **global across all projects** (`$HOME/.claude/logs/subagent-tokens.jsonl` when no learning root, or `<learning-root>/logs/`), so any concurrent/same-day project session also bleeds in.

### Log topology — why there are THREE divergent log files (discovered S35)
There is no single logger. **Two independent SubagentStop hooks fire on every subagent stop**, with different routing, and the plugin hook's routing changed mid-project. Result — three `subagent-tokens.jsonl` files:

| File | Written by | Span (observed) | Notes |
|---|---|---|---|
| `<learning-root>/logs/` e.g. `…/ultralearn/logs/` | **Plugin hook** (current), routes to `$SAGE_LEARNING_ROOT/logs` where `$SAGE_LEARNING_ROOT`=`/tmp/.sage-learning-root` = the **ultralearn root** | 06-26 → present | **This is what `session_metrics.py` reads** (its `find_subagent_log` resolves the same `/tmp/.sage-learning-root`). Cross-**project** bucket shared by every topic under ultralearn. |
| `<project>/learning/logs/` e.g. `…/auth-and-authz/learning/logs/` | **Jarvis hook** `~/.claude/tools/jarvis/hooks/track-subagent.sh` (routes to `$CLAUDE_PROJECT_DIR/learning/logs`); also the plugin hook *before* commit 46f1742 | 05-04 → present | Project-scoped, still actively written by the jarvis hook. |
| `~/.claude/logs/` | Both hooks' fallback when no learning dir / no learning root | 04-13 → 06-30 | Original global default; used for non-Sage projects. |

Contributing factors:
1. **Duplicate hooks.** `~/.claude/settings.json` registers a personal `jarvis` SubagentStop hook AND the plugin's `hooks/hooks.json` registers the plugin hook. Both run every SubagentStop → the same event is logged to two different files (both show identical last-write timestamps). (Same duplication pattern seen with `enforce-cross-refs.sh`.)
2. **Routing drift.** Plugin commit `46f1742` ("Fix token tracking", ~06-26) changed the plugin hook from `$CLAUDE_PROJECT_DIR/learning/logs` → `$SAGE_LEARNING_ROOT/logs` (learning root). The jarvis hook was never updated, so producer paths diverged.
3. **Cross-project bucket, but session filtering resolves it.** `$SAGE_LEARNING_ROOT` is the **ultralearn root**, not the project, so the plugin log (the one the metrics tool reads) is shared across all topics. However, because a Sage **session maps 1:1 to a project** (one topic per session), correct **session-id filtering (Option B) isolates the project as a byproduct** — the surviving entries are all from the current session, hence all from one project. No separate per-project path scoping is required. **Sole exception (not a practical concern here):** running multiple topics inside a *single* Claude Code conversation (same session id, no `/clear`) would defeat session filtering — but the maintainer confirmed (S35) they always `/clear` or start a fresh session per topic, so each session id maps to exactly one project. Under that workflow Option B fully resolves cross-project pollution with no residual edge case. Option A (time-window) does NOT get this for free: a same-day session in another topic falls inside the time window regardless. Separately, the duplicate-hook + jarvis-copy situation should still be reconciled (double-writes; the jarvis hook lives outside this repo).
4. **Stale install risk.** The running hook is the plugin **cache** copy at `~/.claude/plugins/cache/sage/sage/1.0.0/hooks/scripts/track-subagent.sh` (currently identical to the dev repo). Edits to the dev repo won't take effect until the plugin is reinstalled/synced.

### Impact
- Per-session token totals in journals are inflated (multi-session cumulative), mislabeled as one session.
- The resume brief reads journals for cost/trend signals; inflated totals can corrupt "tokens/time per session increasing" analysis and could trip false plateau/efficiency flags.
- Only journals with a Token Metrics section are affected. That feature began at **S33**, so historically S33 and S34 were polluted (see remediation).

### Remediation options (not yet applied — decision deferred)
- **A. Time-window filter in `session_metrics.py` (~6 lines, 1 file).** Derive session start ≈ `now − duration_ms − margin` from the main metrics JSON; drop older log lines. Fixes cross-*day* pollution; ships now; self-contained. Limitation: same-*day* cross-project entries still bleed (log is global). Proposed diff:
  ```diff
  + from datetime import datetime, timedelta
  - def parse_subagent_log(path, session_id=""):
  + def parse_subagent_log(path, session_id="", since=None):
        ...
        if session_id and entry.get("session_id") != session_id:
            continue
  +     if since is not None:
  +         try:
  +             if datetime.fromisoformat(entry.get("timestamp", "")) < since:
  +                 continue
  +         except ValueError:
  +             pass  # unparseable timestamp -> keep (fail-open)
  ```
  and in `run()`:
  ```diff
  +   since = None
  +   if duration_ms and duration_ms > 0:
  +       since = datetime.now().astimezone() - timedelta(milliseconds=duration_ms) - timedelta(minutes=10)
      ...
  -   entries = parse_subagent_log(sub_log, session_id)
  +   entries = parse_subagent_log(sub_log, session_id, since=since)
  ```
- **B. Unify the session-id source (the exact fix, ~3 files).** Have the SessionStart hook write `/tmp/.sage-session-id` (the main id it already knows), make `track-subagent.sh` stamp *that* instead of the payload `.session_id`, and make `session_metrics.py` filter by it. Both sides share one id → exact per-session isolation, no same-day bleed. Larger surface; only helps sessions after the fix.
- **C. Ship A now, file B as a follow-up issue.** (Maintainer's leaning at time of writing, but deferred.)

Whichever is chosen: do it on a branch and **update `tests/test_session_metrics.py` and `tests/test_track_subagent.py`** (existing coverage — a patch without test updates is a regression risk). Note: no fix can retroactively repair the global log's existing entries; it only cleans data going forward.

### Data remediation already applied (auth-and-authz project, 2026-07-01)
- **S35 journal:** trimmed to that session's entries (were cleanly separable — all same-day entries were this session's). Real numbers retained: 405,336 fresh, duration 1h38m48s.
- **S33 & S34 journals:** metrics block replaced with an honest stub (per-session totals judged unreconstructable — global log's session_ids don't map, same-day cross-project entries can't be separated). Session-scoped Duration/Context retained.
- Logged in project artifacts as **CP-9** (coach-errors) and **CI-7** (coach-insights: "verify metrics-file date scope before approving patch-metrics").

### Reproduce
```bash
SAGE_ROOT="${SAGE_ROOT:-$(cat /tmp/.sage-plugin-root 2>/dev/null)}"
python3 "$SAGE_ROOT/tools/session_wrapup.py" "$SAGE_ROOT" "<abs-learning-path>" "<slug>"
# inspect /tmp/session-metrics-<slug>.txt — timestamps will span multiple days/sessions
```

---

## `/tmp/.sage-plugin-root` is a single global slot shared by every Host

**Status:** known, accepted. Escape hatch shipped in v1.2.0.

`${CLAUDE_PLUGIN_ROOT}` is a hook-config substitution and is **not** present in the
Bash tool's environment, so `/tmp/.sage-plugin-root` is the only bridge from hook
space into the prose bash blocks. Every Host's `SessionStart` writes that same path.

Run Sage on two Hosts on one machine and the last session started wins:

- Claude Code writes its plugin root (e.g. a local dev checkout)
- Codex writes its version-pinned cache path (`~/.codex/plugins/cache/sage/sage/<version>/`)

Both are valid Sage trees, so nothing crashes. It bites as **silent version skew**:
the protocol you are reading comes from one tree while the tools you are running come
from another. Most likely during development, when a working tree and a released
install are both active.

**Escape hatch:** every bootstrap line now prefers an exported variable —

```bash
SAGE_ROOT="${SAGE_ROOT:-$(cat /tmp/.sage-plugin-root 2>/dev/null)}"
```

Export `SAGE_ROOT` per shell (or per Host profile) and the shared file stops mattering.
`scripts/link-skills.sh` points both Hosts at the same working tree, which removes the
ambiguity for the development case entirely.

**Not fixed** because session-scoping the filename needs a session id available inside
prose bash. Claude Code exports `CLAUDE_CODE_SESSION_ID`; no equivalent is confirmed on
Codex. That is a mechanism to build and validate for a failure mode requiring two Hosts,
two versions, and interleaved sessions.

`/tmp/.sage-learning-root` has the same structure but is benign — the Learning Root is
Host-independent.
