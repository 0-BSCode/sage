# End-of-Session Checklist

Follow this checklist in order when the session ends or the learner signals they want to stop. Do NOT try to squeeze in more material — capturing state is more important than covering one more concept.

## 1. Quick Retrieval Pulse

2-3 rapid questions on what was covered. Keep it brief if the learner is wrapping up.

## 2. Metacognitive Reflection

"What clicked? What's still fuzzy?"

## 3. Verify Flashcards

Before persisting any new flashcards, delegate to `verification-gate`:

```
Read $SAGE_ROOT/agents/verification-gate.md in full and follow it exactly — that
file is your complete specification. Do not act before reading it.

Operation: verify-cards
Topic: [topic]

Cards:
### Card 1
**Q:** [question]
**A:** [answer]
**Tags:** [tags]
...
```

Apply corrections from `corrected` verdicts. For `flagged` cards, either fix them yourself or drop them — never persist an unverified flashcard. Wrong flashcards are actively harmful because spaced repetition will cement the error.

## 4. Checkpoint via Artifact Clerk

Compile your session notes (what was covered, retrieval scores, assessment performance, new cards, misconceptions, knowledge map changes, savepoint data) and delegate to `artifact-clerk`:

```
Read $SAGE_ROOT/agents/artifact-clerk.md in full and follow it exactly — that
file is your complete specification. Do not act before reading it.

Operation: checkpoint
Path: <topic-slug>/learning/

[session notes]
```

The clerk updates all artifacts, runs SRS sync/forecast, and validates cross-artifact consistency. Include an "Assessment Performance" section in session notes with question IDs, scores, and quality ratings from any assessment agent evaluations.

- If any CE-# or CP-# entries were created, updated, or resolved this session, include a flag in the checkpoint data:
  `Coach Reflect: yes`
  After the checkpoint completes, delegate to `artifact-clerk` again with the
  spec pointer followed by `Operation: coach-reflect` and
  `Path: <topic-slug>/learning/`.
  Review the returned candidates and approve or reject each one. The clerk writes approved rules to `coach-insights.md`.
- If CE/CP entries are logged **after** the checkpoint completes (e.g., through learner feedback or late self-discovery), trigger `coach-reflect` immediately — do not defer to the next session. Full session context is available now; it won't be later.

## 5. Review Clerk Report

Check for consistency warnings and address any flagged issues.

## 6. Run Wrapup Script

After all post-checkpoint work is complete, run the wrapup script:

```bash
SAGE_ROOT="${SAGE_ROOT:-$(cat /tmp/.sage-plugin-root 2>/dev/null)}"
python3 "$SAGE_ROOT/tools/session_wrapup.py" "$SAGE_ROOT" "<topic_path>"
```

If `coach_metrics_flags` is non-empty, mention the flags in your session summary.
If `insight_updates` is non-empty, update the corresponding CI-# entries in `coach-insights.md`.
The wrapup returns `duration` (current-sitting wall time from the session transcript, or null) — used in step 7.
If `cross_refs_stale` is non-null, a knowledge map was promoted this session but
`cross-refs/` was not updated. Upsert the affected concepts before finishing — this
is the one hard invariant, and it is enforced here so it holds on every Host, not
only where a Stop hook happens to fire.
If any `errors`, note them but don't block — these are non-critical.

## 7. Patch Duration into Journal

Delegate to `artifact-clerk` with the spec pointer followed by
`Operation: patch-metrics`, `Path: <topic-slug>/learning/`, and
`Duration: <duration from step 6>`.

The clerk patches the session duration into the latest journal entry.

**Fallback:** `duration` is null whenever no session transcript can be trusted —
either the lookup failed, or the Host does not expose a session id at all (only
Claude Code does). In both cases ask the learner for the session wall time and
pass that as the `Duration` value instead. Never pass a guessed number.

## 8. Confirm to Learner

Tell them what was saved and when their next spaced review is due.

**Do NOT commit to git automatically.** Suggest the commit message, but let the learner decide when to commit.

## 9. Spaced Review Reminder

"Your next review is due [date]"
