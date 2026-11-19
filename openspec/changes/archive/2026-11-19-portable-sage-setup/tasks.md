# Tasks

## 1. Installation-relative resource lookup

- [x] 1.1 Replace global temporary-root bootstrap instructions in the skill and all specialist/reference documents with loaded-skill-relative resolution and explicit root propagation; verify with a resource-closure test using a relocated plugin copy, an unrelated cwd, and no global `/tmp` bridge.
- [x] 1.2 Preserve validated explicit development-root overrides, native root-level specialist discovery, and router/wrap-up interfaces; update `tests/test_plugin_manifests.py` and run manifest/path tests against both host layouts.
- [x] 1.3 Clarify that specialist frontmatter model choices apply only to their native host, while generic/inline execution follows the shared body; verify protocol consistency checks and document path resolution and fallback behavior in `ref-subagents.md` and the development setup instructions.

## 2. Active-session state and operation lifecycle

- [x] 2.1 Add internal Python session-context helpers and a tool for activation, inspection, operation start/completion, and teaching-session close; verify host-qualified hashed IDs, path validation, atomic state writes, and per-session concurrent-update locking in isolated-home tests.
- [x] 2.2 Add explicit context propagation after successful fresh/resume routing, keeping unknown-verb, cancelled setup, picker-only, and archive flows inactive for teaching reminders; verify router/session-context integration tests and unchanged first-run configuration behavior.
- [x] 2.3 Register specialist operations and completion tokens for native, generic, and inline execution; verify correlation fixtures with and without native operation prompts, failed operation completion, and same-ID sessions on different hosts.
- [x] 2.4 Bind session state to the resolved learning directory and installation, close activation after a successful validated session end, and rebind on resume; verify unrelated sessions, environment overrides, denied state access, interrupted-session recovery, and failed-checkpoint cases.
- [x] 2.5 Document the internal session/operation contract and update checkpoint instructions to report unavailable automatic safeguards and inline self-verification accurately; verify documented command examples through the tool's help and integration fixtures.

## 3. Host hooks and safeguard preservation

- [x] 3.1 Add explicit Claude Code and Codex event adapters and Python hook entrypoints, with startup context carrying parent session identity and installation root; verify sanitized fixtures against the documented host schemas, missing identity behavior, and native subagent-to-parent association.
- [x] 3.2 Route verification counting/reset and checkpoint-card warnings through shared session state, preserving the five-response once-per-cycle threshold and warning severity; update `test_verification_counter.py`, `test_reset_verification.py`, and `test_checkpoint_guard.py` with both host payloads and operation lifecycle coverage.
- [x] 3.3 Replace the cross-reference hook's cwd gate with active-session lookup and reuse `cross_refs_check.py`; verify blocking for active sessions outside the learning directory, no effects on inactive sessions inside it, recursive-stop protection, and visible errors for identifiable active sessions.
- [x] 3.4 Wire adapter hook configurations into both manifests and retain only necessary legacy script shims; verify every registered entrypoint exists, both manifests expose the required events, and supported hook execution no longer requires Bash/jq or global root files.
- [x] 3.5 Keep wrap-up validation independent of hooks and best-effort duration behavior intact; verify stale cross-reference reporting with hooks disabled, unsuccessful wrap-up retaining activation, and existing duration tests.
- [x] 3.6 Update `hooks/README.md`, `docs/KNOWN-ISSUES.md`, and relevant ADR guidance to distinguish current safeguards, activation, trust requirements, and unavailable-hook behavior; verify each documented behavior has a corresponding regression scenario.

## 4. Initializer and host registration

- [x] 4.1 Add the Node ESM setup package, executable `init` entrypoint, explicit interactive host multi-selection, and Node runtime requirement; verify selection, empty input, cancellation, noninteractive failure, and CLI help with Node's test runner.
- [x] 4.2 Implement selected-host/shared prerequisite probes and read-only inventory of native plugins, marketplaces, and conflicting standalone skills; verify missing Python, unavailable CLIs, unsupported commands, disabled/outdated plugins, malformed JSON, project-local skill conflicts, and marketplace source collisions using fake CLIs and temporary profiles.
- [x] 4.3 Implement the Claude Code adapter using native user-scoped marketplace/plugin management and post-install inspection; verify subprocess argument arrays, correct user scope, compatible-install reuse, no implicit updates, conflict preservation, and no automatic trust acceptance.
- [x] 4.4 Implement the Codex adapter using native user configuration marketplace/plugin management and post-install inspection; verify native Sage registration rather than duplicate skill linking, compatible-install reuse, missing-capability reporting, and retained hook-review requirements.
- [x] 4.5 Add per-host results, safe repeat setup, partial-failure summaries, actionable native remediation commands, and completion instructions; verify successful-host preservation, incomplete overall readiness, permission/restart guidance, and unchanged learning config/records.
- [x] 4.6 Update README installation and troubleshooting examples for first install, repeat setup, existing manual installations, and standalone-skill conflicts; verify examples against initializer help and isolated CLI fixtures while retaining existing manual plugin commands.

## 5. Packaging and release preparation

- [x] 5.1 Define npm package contents and build/pack checks for the initializer, without relying on files left in the developer checkout or ephemeral npx paths for plugin resources; verify a locally built tarball in a temporary home with fake host executables and confirm no launch-directory writes.
- [x] 5.2 Keep `.claude-plugin/plugin.json` authoritative, mirror a minor version bump in marketplace/Codex/package metadata, and add the changelog entry; verify version-coherence tests and release-hygiene checks cover new setup source and package files.
- [x] 5.3 Extend CI with the required Node setup, initializer tests, tarball inspection, and existing Python/manifest checks; update `docs/RELEASING.md` to distinguish repository plugin release from future npm publication and verify all CI commands locally where available without publishing or creating tags.

## 6. Cross-host acceptance

Tasks 6.2 and 6.3 are **DEFERRED to post-deployment testing**, not completed.
The owner approved initial deployment before live acceptance on 2026-11-19.
They remain unchecked in this archived implementation record; execution and
results are tracked in `docs/portable-setup-post-deploy.md` and
`docs/portable-setup-acceptance.md`. This decision permits archival with two
incomplete tasks and does not establish full conversational compatibility.

- [x] 6.1 Exercise actual checkpoint writers, SRS state, router resume, and specialist brief inputs across two isolated installation roots in both host directions; verify plan position, due reviews, misconceptions, and next-step continuity without record migrations.
- [ ] 6.2 Run real-host smoke sessions in disposable authorized Claude Code and Codex profiles from unrelated working directories; record host versions, native plugin and specialist discovery, trust/restart steps, startup context, verification reminders, card warnings, and stale cross-reference blocking in an acceptance report.
- [ ] 6.3 Complete sequential learning/checkpoint/resume in both real-host directions and an inactive-session isolation check; record evidence in the acceptance report, marking any blocked checks explicitly rather than claiming mocked parity.
- [x] 6.4 Run the complete Python and Node suites, manifest validation, npm pack checks, and `openspec validate portable-sage-setup --strict`; verify the final acceptance report maps both capability specifications to passing evidence or explicit unresolved limitations before declaring implementation complete.

## Workflow follow-up

- Choose the final npm registry name and ownership before separately authorized publication.
- Archive the implemented change with live acceptance explicitly deferred under
  the decision above; complete the follow-up checklist after deployment.
