# Changelog

All notable changes to the sage plugin are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning rules: see [docs/RELEASING.md](docs/RELEASING.md).

## [1.0.2] - 2026-07-20

### Fixed

- `session_duration` no longer reports a silently wrong duration when given a
  session id it cannot find — it now errors with exit code 1. (Classified as a
  patch: the tool is internal to the coach, outside the compatibility surface.)
- Dead documentation reference removed.

## Earlier versions

Versions before 1.0.2 predate this changelog and are not individually
documented.
