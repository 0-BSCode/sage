# The router stays the sole parser of the invocation

`SKILL.md` passed `$ARGUMENTS` to `session_router.py`. Claude Code substitutes that from the
slash command; Codex has no argument substitution, so the port needed another way for the
invocation to reach the router.

The obvious fix — have the coach extract the verb and topic from the learner's message and
pass them as a quoted string — would have undone [ADR 0002](0002-mandatory-command-verbs.md).
That ADR accepted a breaking change to make the verb mandatory, on the grounds that a Topic
named "archive" is unambiguous only because `learn` is always present. That holds while the
*learner* types the verb. If the coach infers it, "archive my react notes" is ambiguous
again — precisely the collision that got `learn`-as-implicit-default rejected.

It would also have disabled the fallback that was cited as making it safe. The
`unknown_verb` branch fires on an *unrecognized* verb; a coach doing extraction emits `learn`
or `archive`, always recognized. Making the coach the parser removes the parser's own
guard against a bad parse.

So the coach passes the learner's request through **verbatim** and `parse_invocation` remains
the only parser on every Host. On Claude that is still `$ARGUMENTS`; elsewhere it is the
learner's message text. A request with no leading verb reaches `unknown_verb` and gets the
grammar message, which is the designed behavior rather than a failure.

Consequence: the `unknown_verb` message becomes the primary way the grammar is taught on a
Host with no slash commands, so the router's hardcoded `/sage` prefixes
(`session_router.py:115,145`) are dropped in favor of bare `learn <topic>` /
`archive <topic>`.
