# Changelog

All notable changes to the sage plugin are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning rules: see [docs/RELEASING.md](docs/RELEASING.md).

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
