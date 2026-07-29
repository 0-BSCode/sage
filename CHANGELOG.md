# Changelog

All notable changes to the sage plugin are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning rules: see [docs/RELEASING.md](docs/RELEASING.md).

## [1.1.0] - 2026-07-29

Over-engineering audit: ~1,900 lines removed from `tools/`, no feature lost.
Every cut was made against evidence of use — invocations recovered from session
transcripts, plus on-disk artifact state where a command writes. Minor, not
major: everything removed is an **Internal Tool**, outside the compatibility
surface.

### Removed

- Uninvoked tool subcommands: `journal_writer validate`, `weak_spot_writer
  validate|fix`, `kmap_writer validate|fix-legend|ensure-sections`,
  `assessment_engine coverage|stats|calibrate`, `coach_metrics trends|compare`,
  and `srs_engine due --sort risk`. None had a caller in the shipped markdown
  or a single invocation in five weeks of session transcripts.
- `tools/srs/find_duplicate_cards.py` — orphaned; `card_writer append` already
  rejects duplicates at write time, which is the root-cause fix.
- Learner-level calibration. `estimated_level` was written only by `calibrate`
  and read only by `stats`; the adaptive selector never consulted it. The
  `learner_calibration` field stays in existing question banks and is ignored.
- Hook debug logging to `/tmp/sage-hook-debug.log`. Nothing read it, and under
  `set -euo pipefail` an unwritable log could kill `enforce-cross-refs` before
  it emitted its block decision — the guard would have failed open, silently.
- `plateau_detector`'s five threshold override flags, `session_wrapup`'s unused
  `topic_slug` positional (extra arguments are ignored, so existing callers
  keep working), and `session_duration`'s `find_transcript`/`run` wrappers.

### Changed

- The demo index is now `docs/demos/index.md` instead of `index.html`. The old
  writer parsed its own generated HTML back out on every append and had already
  dropped a live entry that way; rows are now kept as text and never re-parsed.
  **Existing `index.html` files are not migrated** — convert by hand, or the
  next appended demo starts a fresh `index.md`.
- `assessment_engine init` is now documented. It was always required — every
  other subcommand fails without it — but appeared in no shipped markdown, so
  it was being improvised. The agent is also told to pass `<topic>/learning/`
  explicitly: a path one level too high silently creates a second, empty
  question bank instead of erroring.
- `card_writer validate` and `demo_index_writer validate` documented as manual
  diagnostics.

### Fixed

- The 68 assessment-engine tests never ran. They lived under `tools/`, which
  `testpaths` excluded, so CI collected 296 tests instead of 364.

## [1.0.2] - 2026-07-20

### Added

- `/sage archive <topic>` — retire a topic's project by moving it to
  `.archive/` under the learning root. One-way by design: artifacts stay
  readable, but returning to a topic means starting fresh.

### Changed

- **Breaking:** the `/sage` entry point now requires a leading verb —
  `/sage learn <topic>` or `/sage archive <topic>`. The free-form
  `/sage <topic>` grammar and the bare resume keywords (`continue`, `resume`,
  `pick`, `list`) are no longer accepted; `learn` subsumes them (bare
  `/sage learn` opens the project picker). *Note: this release predates the
  written release rules, under which an invocation change like this would be
  a major bump.*
- Reference docs moved from `docs/` to `references/` so they ship with the
  plugin.
- Session metrics tracking removed (`session_metrics.py` and its wrap-up
  integration).

### Fixed

- Session transcripts are resolved by `CLAUDE_CODE_SESSION_ID` instead of the
  working directory, so durations no longer come from the wrong transcript.
- `session_duration` no longer reports a silently wrong duration when given a
  session id it cannot find — it now errors with exit code 1. (Classified as a
  patch: the tool is internal to the coach, outside the compatibility surface.)
- Dead references to unshipped files removed from coach-facing docs.

## Earlier versions

Versions before 1.0.2 predate this changelog and are not individually
documented.
