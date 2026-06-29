# End-of-Session Checklist

Follow this checklist in order when the session ends or the learner signals they want to stop. Do NOT try to squeeze in more material — capturing state is more important than covering one more concept.

## 1. Quick Retrieval Pulse

2-3 rapid questions on what was covered. Keep it brief if the learner is wrapping up.

## 2. Metacognitive Reflection

"What clicked? What's still fuzzy?"

## 3. Verify Flashcards

Before persisting any new flashcards, send them through the verification gate:

```
Task(subagent_type="verification-gate", prompt="Operation: verify-cards\nTopic: [topic]\n\nCards:\n### Card 1\n**Q:** [question]\n**A:** [answer]\n**Tags:** [tags]\n...")
```

Apply corrections from `corrected` verdicts. For `flagged` cards, either fix them yourself or drop them — never persist an unverified flashcard. Wrong flashcards are actively harmful because spaced repetition will cement the error.

## 4. Checkpoint via Artifact Clerk

Compile your session notes (what was covered, retrieval scores, assessment performance, new cards, misconceptions, knowledge map changes, savepoint data) and send to the clerk:

```
Task(subagent_type="artifact-clerk", prompt="Operation: checkpoint\nPath: <topic-slug>/learning/\n\n[session notes]")
```

The clerk updates all artifacts, runs SRS sync/forecast, and validates cross-artifact consistency. Include an "Assessment Performance" section in session notes with question IDs, scores, and quality ratings from any assessment agent evaluations.

- If any CE-# or CP-# entries were created, updated, or resolved this session, include a flag in the checkpoint data:
  `Coach Reflect: yes`
  After the checkpoint completes, make a separate call to trigger reflection:
  `Task(subagent_type="artifact-clerk", prompt="Operation: coach-reflect\nPath: <topic-slug>/learning/")`
  Review the returned candidates and approve or reject each one. The clerk writes approved rules to `coach-insights.md`.
- If CE/CP entries are logged **after** the checkpoint completes (e.g., through learner feedback or late self-discovery), trigger `coach-reflect` immediately — do not defer to the next session. Full session context is available now; it won't be later.

## 5. Review Clerk Report

Check for consistency warnings and address any flagged issues.

## 6. Run Wrapup Script

After all post-checkpoint work is complete, run the wrapup script:

```bash
SAGE_ROOT=$(cat /tmp/.sage-plugin-root)
python3 "$SAGE_ROOT/tools/session_wrapup.py" "$SAGE_ROOT" "<topic_path>" "<topic-slug>"
```

If `coach_metrics_flags` is non-empty, mention the flags in your session summary.
If `insight_updates` is non-empty, update the corresponding CI-# entries in `coach-insights.md`.
If any `errors`, note them but don't block — these are non-critical.

## 7. Patch Metrics into Journal

```
Task(subagent_type="artifact-clerk", prompt="Operation: patch-metrics\nPath: <topic-slug>/learning/\nMetrics file: /tmp/session-metrics-<topic-slug>.txt")
```

The clerk reads the metrics file and appends it to the latest journal entry.

**Fallback:** If the metrics file wasn't created (check `metrics_ok` from step 6), ask the learner to report from their status line: wall time, context percentage and window size, input tokens, and output tokens. For duration, read `duration_ms` from `/tmp/claude-session-metrics.json` and convert to human-readable (e.g., 2535000 → "42m15s").

## 8. Confirm to Learner

Tell them what was saved and when their next spaced review is due.

**Do NOT commit to git automatically.** Suggest the commit message, but let the learner decide when to commit.

## 9. Spaced Review Reminder

"Your next review is due [date]"
