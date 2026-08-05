# Resolve transcripts by session id, and fail rather than guess

`tools/session_duration.py` derives a **Session**'s `Duration` from the Claude Code transcript. It now finds that transcript by **session id**, globbing `~/.claude/projects/*/<id>.jsonl`, taking the id from `CLAUDE_CODE_SESSION_ID` when none is passed explicitly. When an id is known but resolves to nothing, the tool **fails** — it does not fall back to guessing. The path-derived lookup survives only for manual invocation outside Claude Code, and warns when it guesses.

## Why not the working directory

The original implementation slugified `os.getcwd()` to locate the transcript directory. This is a faithful transcription of Claude Code's storage layout — transcripts really do live at `~/.claude/projects/<cwd-slug>/<session-id>.jsonl` — but it reads a *storage layout* as an *addressing scheme*, and those differ in one decisive way: **the slug encodes the directory Claude Code was launched in, not the directory the process is currently in.** Claude Code's Bash tool persists `cd` across tool calls, so any earlier `cd` into a subdirectory — verifying a file, running a scoped grep — permanently repoints the lookup at a directory that has never existed. `glob()` returns empty, the tool exits non-zero, and the coach falls through to asking the learner for a stopwatch reading while a correct 768 KB transcript sits untouched on disk.

Supplying a session id did not rescue this, because the id was only used to pick a file *within* the cwd-derived directory. Same id, two working directories, two different answers.

The tempting fix — pass the learning root in as an argument — is the same defect wearing a new hat. The slug tracks the launch directory, which only coincidentally equals the learning root; a session started from a subdirectory or from `$HOME` reproduces the bug exactly. **Any fix that derives the path from some other path is still deriving the path from a path.** The session id is the only identifier that is actually invariant, and it is unique across every transcript on disk (verified against 160).

## Why the environment variable, not plumbing

An earlier design had the id travel from a `SessionStart` hook, through `/tmp/.sage-session-id`, into the end-of-session checklist, into `session_wrapup.py`, into argv. That machinery is unnecessary: **`CLAUDE_CODE_SESSION_ID` is already in the tool's own environment**, inherited by subprocesses, and equal to the transcript's basename. Nothing needs to be plumbed and — importantly — the coach is never asked to supply an id it would have to reconstruct. An id the model guesses wrong is worse than no id at all, because a global glob on a wrong id finds nothing.

This takes a deliberate dependency on an **undocumented** Claude Code variable. The bet is already implicit in this repo: the `~/.claude/projects/<cwd-slug>/` layout the tool reads is equally undocumented. If the variable is renamed, the failure is loud (a `null` duration and a message naming the variable), not silent.

An explicit id argument still overrides the environment. It is the test seam, and the escape hatch.

## Why failing beats falling back

Given a known id that resolves to nothing, the tool could fall back to "newest `.jsonl` by mtime in the cwd directory." It does not.

That fallback returns *a* duration — one belonging to a different session — with exit 0 and no indication anything went wrong. It flows into `patch-metrics`, into the journal, and into coach pacing flags, where a wrong number is indistinguishable from a right one. A `null` announces itself, and the checklist already handles it: step 7 of `docs/ref-session-end.md` asks the learner for the wall time.

This path was already live before the fix and undiagnosed: `session_duration.py <bogus-id>` from a valid directory returned a duration and exit 0, silently discarding the id. Making the id authoritative for *lookup* while leaving it advisory for *failure* would have kept that hole open. **If you trust a signal enough to search on it, you must trust it enough to fail on it** — overriding an authoritative signal with a guess is precisely how the deleted token-metrics collector came to aggregate across every session on the machine.

The cost is real and accepted: the tool now fails *more often* in environments where transcripts are not on local disk. We prefer a visible gap to an invisible fabrication.

## The assumption that makes a Sitting's wall time a Session's Duration

`Duration` is the wall time of the **current Sitting** — the span since the last quiet gap longer than 30 minutes — not the full transcript span. This is necessary because compact/resume keeps the same session id and appends to the same file; one observed transcript spanned 9 days across 3 sittings, so a naive first-to-last would report days.

That substitution is only valid under a stated assumption: **one Session is exactly one Sitting** (now defined in `CONTEXT.md`). A learner who breaks for 50 minutes mid-Session and returns has their Session recorded as the post-break remainder only. We accept this rather than trying to distinguish "a long break inside one Session" from "a new Session on the same transcript" — the 30-minute gap cannot tell them apart, and no other signal in the transcript can either.

This is the part of the decision that is genuinely hard to reverse. The code is trivially changeable; the *meaning of `Duration`* in every journal entry already written is not. Revisiting it means either reinterpreting history or forking the definition at a date.

## Consequences

- **Three failure modes are now distinguishable** rather than collapsing into "No transcript or timestamps found" — a message that said *no transcript* when it meant *no transcript directory for this cwd*, which is what made the failure read as "the data is gone" instead of "you are in the wrong directory."
- **The no-id branch warns on success.** It is the only remaining path that can be confidently wrong, and it is reachable only by a human running the tool from a terminal.
- **`session_wrapup.py --session-id` is now vestigial.** It still forwards correctly; nothing needs to use it. `docs/ref-session-end.md` step 6 is unchanged.
- **Sessions are unaffected by where the coach has `cd`-ed**, which was the point.
