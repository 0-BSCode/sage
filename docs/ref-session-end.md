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

## 4. Collect Session Metrics

Before compiling checkpoint notes, run the session token summary script:

```bash
SAGE_ROOT=$(cat /tmp/.sage-plugin-root)
SESSION_ID=$(jq -r '.session_id' /tmp/claude-session-metrics.json)
python3 "$SAGE_ROOT/tools/session_metrics.py" "$SESSION_ID" "<topic-slug>"
```

This aggregates main session context + subagent token consumption for the current session only.
The script writes a metrics file to `/tmp/session-metrics-<topic-slug>.txt`.

In your checkpoint call to the clerk, include:
```
Metrics file: /tmp/session-metrics-<topic-slug>.txt
```
The clerk will read the file directly and write it verbatim into the journal. Do NOT reformat, summarize, or inline the metrics yourself — the file is the source of truth.

If the script fails to write the file, fall back to sending the script's stdout output verbatim (copy-paste the entire output block, including all `cache-read` fields and per-invocation lines — do NOT drop any fields or restructure the output).

**Field definitions:**
- **Context:** Total context window usage (your messages + model output + system prompts + tool results). Computed as used % × window size.
- **Conversation:** User input (📥) and model output (📤) only. Subset of context.
- **Subagents:** Fresh tokens from all subagents (input + output + cache_creation). Cache reads excluded (reused data, not new computation). Subagents run in separate contexts so their tokens are additive.
- **Grand total:** Context + subagent fresh tokens.

**Fallback:** If the script fails or produces no output, ask the learner to report from their status line: wall time (`⏱`), context percentage and window size, input tokens (`📥`), and output tokens (`📤`). For duration, read `duration_ms` from `/tmp/claude-session-metrics.json` and convert to human-readable (e.g., 2535000 → "42m15s").

## 5. Checkpoint via Artifact Clerk

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

## 6. Compute Coach Metrics

After the checkpoint completes, run the metrics snapshot directly:

```bash
SAGE_ROOT=$(cat /tmp/.sage-plugin-root)
python3 "$SAGE_ROOT/tools/coach/coach_metrics.py" snapshot <topic-slug>/learning/
```

This creates `metrics/` on first run, updates `metrics/history.json` and `metrics/dashboard.md`. If any threshold flag fires, mention it in the session summary to the learner. Non-blocking — if the script fails, note it and move on.

## 7. Evaluate Coach Insights

If `coach-insights.md` exists, run the evaluation directly:

```bash
SAGE_ROOT=$(cat /tmp/.sage-plugin-root)
python3 "$SAGE_ROOT/tools/coach/coach_reflector.py" evaluate <topic-slug>/learning/
```

If any CI-# has a `recommended_status` different from its `current_status`, update the entry in `coach-insights.md`. Non-blocking — if the script fails or the file doesn't exist, skip silently.

## 8. Review Clerk Report

Check for consistency warnings and address any flagged issues.

## 9. Confirm to Learner

Tell them what was saved and when their next spaced review is due.

## 10. Spaced Review Reminder

"Your next review is due [date]"
