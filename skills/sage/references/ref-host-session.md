# Host session lifecycle

Read this during setup and apply it around every specialist operation. These are
internal commands; the learner still invokes `learn <topic>` normally.

## Activate only after successful routing

Use `host` and parent `session_id` from the `[SAGE HOST CONTEXT]` startup message.
Never infer identity from cwd, a subagent ID, or another conversation. Resolve the
plugin root from the loaded skill as described in `SKILL.md`. After a `fresh` or
`resume` router result and any required storage confirmation, run:

```bash
python3 "<root>/tools/session_context.py" --host "<host>" --session-id "<parent-id>" activate --root "<root>" --request "<verbatim learn request>"
```

Pass the learner request as a safely quoted argument, not executable shell text.
Do not activate for a picker, unknown verb, archive, or cancelled setup. The saved
learning directory must be accessible; do not fall back to cwd on access failure.
If startup identity is missing, say automatic reminders and stop safeguards are
unavailable, identify the required hook review/restart action, and continue with
explicit verification and tool validation only. Never manufacture identity.

## Register each specialist operation

Before every delegation or inline specialist operation:

```bash
python3 "<root>/tools/session_context.py" --host "<host>" --session-id "<parent-id>" start "<clerk-name>" "<operation>"
```

For an artifact-clerk checkpoint mentioning cards, add `--cards`. Surface any
returned warning; this is advisory and does not claim cards were verified.
Pass the returned `token`, host, parent ID, and absolute plugin root to the worker.
The worker reads its spec, performs the operation, and finishes it with:

```bash
python3 "<root>/tools/session_context.py" --host "<host>" --session-id "<parent-id>" complete "<token>" --status completed
```

Use `--status failed` when execution fails. For `verify-cards`, only record
`completed` after all new cards meet the verification protocol; unresolved or
unverified cards do not earn a successful marker. If the worker cannot execute the
completion command, the coach records its actual outcome after reading the
report. Never mark completion just because a subagent stopped. An optional native
`--agent-id` records exact correlation when available; do not guess it. Generic
and inline workers use the same explicit token without needing native metadata.
Completion tokens are lifecycle signals, not proof of factual correctness.

If automatic state could not be activated, perform the same specialist protocol
without lifecycle commands and disclose the absent safeguards. Inline verification
is self-verification, not an independent specialist check.

## Finish after saving

After the checkpoint, corrections, duration patch, and all specialist operations
have completed, run:

```bash
python3 "<root>/tools/session_context.py" --host "<host>" --session-id "<parent-id>" close
```

This reruns shared wrap-up validation against the bound learning directory and
closes activation only when the result is clean. Resolve stale cross-references
and retry. Report `errors` or a false `session_closed`; do not claim a clean
checkpoint. A hard close still cannot guarantee saving the current lesson.
