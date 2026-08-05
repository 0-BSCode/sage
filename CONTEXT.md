# Sage

A plugin that turns an agentic coding tool into an evidence-based tutor, teaching through questioning rather than lecturing. Ships to Claude Code and Codex CLI; see **Host** below.

## Language

### Learning Structure

**Learner**:
The person using Sage to build durable mastery of a topic through coached sessions.
_Avoid_: student, user

**Learning Root**:
The user-configured directory where all learning topic directories live.
_Avoid_: project root, sage directory, base path

**Topic**:
A single subject the learner is studying (e.g., "react-hooks", "statistics"). The *subject* — distinct from the **Project** directory that realizes it on disk.
_Avoid_: course, module, subject

**Project**:
The on-disk container for a **Topic** — the `<slug>/` directory under the learning root that holds `learning/`, any `capstone/`, and is keyed by the topic's **Cross-Refs** shard. Exactly one Project per Topic. "Project" is the right word when the referent is the directory/unit (discovery, archival, the cross-ref registry); "Topic" is the right word when the referent is the subject. The code has always used "project" for this; it is now a defined term, not a loose synonym for Topic.
_Avoid_: folder (when the container-with-artifacts meaning is intended), topic (when the directory, not the subject, is meant)

**Archive** (verb):
To retire a **Project** by moving its directory to `<learning_root>/.archive/<slug>/` (numeric-suffixed on collision), co-locating its cross-ref shard there, and scrubbing every reference to it from the cross-refs `INDEX.md`. An **Archived Project** no longer appears in the `learn` picker. Archival is **one-way by design**: there is no `unarchive` command and none is planned. Nothing is deleted — the artifacts stay readable under `.archive/` for reference, and an `archive-meta.json` stash preserves the removed INDEX fragments so a human can restore by hand — but returning to a topic means starting a fresh **Project**, not reactivating the old one. Archiving is a deliberate, confirmed choice to give up the **Knowledge Map**, **Card**, and SRS state, keeping only the artifacts as a record.
_Avoid_: delete, remove, retire (as the on-disk operation); unarchive, restore (no such operation exists)

**Artifact**:
A structured file within a topic's `learning/` directory that tracks learning state. Includes plan, journal, knowledge map, cards, weak spots, and coach errors.
_Avoid_: file, document, output

**Session**:
A single learning interaction between the coach and the learner. Produces journal entries, card updates, and a savepoint. **One Session is exactly one Sitting** — a Session is assumed to be an unbroken stretch of work, so a break long enough to end the **Sitting** ends the Session. Distinct from the *Claude Code session*, the editor's process-level unit (`CLAUDE_CODE_SESSION_ID`, one transcript file), which survives compact/resume and so can span several Sessions.
_Avoid_: conversation, chat; bare "session" when the Claude Code session is meant — always qualify it

**Sitting**:
An unbroken stretch of activity in a Claude Code transcript, bounded by a quiet gap longer than 30 minutes. A **Session**'s recorded `Duration` is the wall time of its Sitting. Load-bearing in code well before it was a defined term (`SITTING_GAP_SECONDS`, `current_sitting()` in `tools/session_duration.py`). Because one Session is one Sitting, the *last* Sitting in a transcript is by definition the current Session's — which is why duration is measured from the last long gap rather than from the top of the file.
_Avoid_: session (the transcript-level unit), block, stretch, sprint

**Savepoint**:
A snapshot of where a session ended, enabling seamless resume. Stored in the journal entry.
_Avoid_: checkpoint, bookmark

**Host**:
The agentic coding tool Sage runs inside — Claude Code, Codex CLI, Gemini CLI, Cursor. A Host supplies the skill entry point, and may or may not supply lifecycle hooks and a subagent facility. Sage's protocol and engine are Host-neutral; only the manifests and the hook wiring are per-Host. Distinct from the *Claude Code session*, which is one Host's process-level unit.
_Avoid_: agent (means a **Clerk** in Sage's vocabulary), harness, editor, platform

**Clerk**:
One of the six operational subagents (`agents/*.md`) the coach delegates to — artifact-clerk, assessment-agent, verification-gate, reference-clerk, demo-generator, capstone-architect. Clerks exist for context isolation and make no pedagogical decisions. A Host without a subagent facility runs their operations inline, at the cost of context, not correctness.
_Avoid_: agent (unqualified — ambiguous with **Host**), subagent (when the Sage-defined role is meant), helper

### Mastery Tracking

**Knowledge Map**:
A table tracking every concept within a topic, its mastery status, and when it was last tested.
_Avoid_: progress tracker, skill tree

**Card**:
A flashcard with a question and answer, scheduled for spaced review by the SRS engine.
_Avoid_: flashcard, quiz item

**Weak Spot**:
A specific misconception or knowledge gap identified during a session, tracked for targeted drilling.
_Avoid_: error, mistake, gap

**Coach Error**:
A mistake made by the coach (wrong fact, incorrect grading), distinct from learner weak spots. Tracked separately in `coach-errors.md`.
_Avoid_: bug, mistake

### Cross-Topic

**Cross-Refs**:
A registry of concept overlaps between topics, stored in `cross-refs/` at the learning root. Updated when knowledge maps change.
_Avoid_: cross-references, links, connections

### Versioning & Release

**Plugin Version**:
The version of the plugin, as declared in `.claude-plugin/plugin.json` — the single source of truth. The copy in `marketplace.json` is a **mirror** that must always be equal; a disagreement is a defect in the mirror, never in `plugin.json`.
_Avoid_: treating the marketplace copy as independently meaningful

**Shipping Change**:
A change to anything a user actually installs and runs: the skill definition, tools, agents, hooks, references, or plugin manifests. Every Shipping Change bumps the Plugin Version in the same change set; changes confined to repo docs, tests, or CI must not.
_Avoid_: release (the merge event), change (unqualified)

**Release**:
The landing of a Shipping Change on the sage repo's main branch. There is no separate release pipeline — merging to main *is* publishing, because installs track the repository directly. Every Release is identified by its Plugin Version (tag `v<version>`) and described by a Changelog entry.
_Avoid_: deploy, publish (as a distinct later step — no such step exists)

**Changelog**:
The user-facing record of Releases (`CHANGELOG.md` in the sage repo), one entry per Plugin Version. The website reflects it; the file is the source of truth.
_Avoid_: release notes (no separate artifact exists)

**Compatibility Surface**:
The two things a Breaking Change can break: **invocation** (how the learner invokes and resumes the skill) and **Artifacts** (which outlive upgrades — a new version must read artifacts written by any earlier 1.x version, or ship a migration).
_Avoid_: API (nothing here is an API in the conventional sense)

**Breaking Change**:
A change that alters the Compatibility Surface; requires a major version bump. Changes to Internal Tools are never Breaking Changes on their own, even when observable behavior changes.
_Avoid_: breaking (for internal-tool behavior changes)

**Internal Tool**:
A CLI tool or agent only the coach invokes — never the learner directly. Internal Tools upgrade in lockstep with the skill and sit outside the Compatibility Surface. (Precedent: `session_duration`'s exit-code change was a patch.)
_Avoid_: API, public tool

## Relationships

- A **Learning Root** contains one or more **Projects**
- A **Topic** is realized on disk as exactly one **Project** (subject ↔ container, 1:1)
- A **Project** contains multiple **Artifacts** in its `learning/` directory
- **Archiving** a **Project** moves its directory under `.archive/` and removes it from `learn` discovery; its **Cross-Refs** shard is co-located and its **INDEX.md** references are scrubbed
- A **Session** produces updates to **Artifacts** and ends with a **Savepoint**
- A **Session** occupies exactly one **Sitting**; one Claude Code session may contain several **Sessions**, each its own **Sitting**, all appended to one transcript
- A **Knowledge Map** tracks **Concepts**, each at a mastery level
- A **Card** belongs to a **Topic** and is scheduled by the SRS engine
- A **Weak Spot** is a learner gap; a **Coach Error** is a coach mistake — they are never mixed
- **Cross-Refs** track overlaps between **Topics** at the **Learning Root** level

## Example dialogue

> **Dev:** "When a learner starts a new **Session**, does the coach create a new **Topic**?"
> **Domain expert:** "No — the **Topic** directory is created during the first session's planning phase. On resume, the coach loads the existing **Artifacts** and continues from the **Savepoint**."

> **Dev:** "Are **Weak Spots** and **Coach Errors** stored in the same file?"
> **Domain expert:** "Never. **Weak Spots** go in `weak-spots.md`, **Coach Errors** go in `coach-errors.md`. The `weak_spot_writer.py` tool enforces this — it refuses to write a CE entry to `weak-spots.md`."

## Flagged ambiguities

- "learning root" vs "sage directory" — resolved: **Learning Root** is the canonical term. It's user-configured, not hardcoded.
- "session" (three meanings) — resolved: **Session** is the learning interaction; **Sitting** is the gap-bounded stretch of activity the duration is measured over; the *Claude Code session* is the editor's process-level unit and must always be named in full. Surfaced by the `session_duration.py` cwd-resolution fix, which reads `CLAUDE_CODE_SESSION_ID` and reports a Sitting's wall time as a Session's `Duration` — legitimate only under the **one Session = one Sitting** assumption, which is now stated rather than implied by a constant.
- "topic" vs "project" — resolved: they are *not* synonyms. **Topic** is the subject; **Project** is the on-disk container (1:1). "Project" was undefined-but-load-bearing in the code (`list_projects`, `cross-refs/<project>.md`, INDEX's `| Project |`); it is now a defined term. Use "Project" for the directory/unit, "Topic" for the subject. Surfaced by the `/sage archive` feature, which operates on the container.
