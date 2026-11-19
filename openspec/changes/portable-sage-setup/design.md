# Design

## Context

See `proposal.md` for motivation and `specs/agent-setup/spec.md` and `specs/session-portability/spec.md` for behavior contracts.

The repository already ships one skill, root-level Python tools and native Claude specialist definitions, two plugin manifests, and a shared hook configuration. ADR 0007 explains why root-level `agents/` must remain discoverable by Claude. Specialist instructions already provide generic-subagent and inline fallbacks. ADR 0006 placed the cross-reference invariant in `tools/cross_refs_check.py`, called by wrap-up as well as the Stop hook.

The remaining coupling is concrete: prose bootstraps read `/tmp/.sage-plugin-root`; startup also writes a global learning-root file; hook state is keyed by bare session IDs; and the cross-reference Stop hook gates on cwd. Claude specialist frontmatter contains provider-specific model choices. Existing tests enforce these layout and bootstrap assumptions and must evolve with them.

Read-only inspection of the installed CLIs confirmed native marketplace/install/list commands, machine-readable output, and explicit user scope on Claude installation. Codex's plugin commands use its user configuration rather than a project scope flag. These are capabilities to probe at runtime, not a guarantee that every historical host version supports them.

## Goals / Non-Goals

**Goals:**
- Keep native plugin ownership of installed resources, trust, updates, and registration.
- Introduce a small initializer with independently testable host adapters.
- Make resource lookup and automatic safeguards depend on the loaded installation and active parent session, rather than cwd or a global latest-session file.
- Preserve learning-record formats, invocation syntax, and current safeguard severity.

**Non-Goals:**
- A second plugin manager, a new tutoring engine API, or automated host-permission changes.
- Enforcing that an LLM always follows instructions or proving the truth of a verification result through a hook marker.
- Concurrent editing guarantees for two hosts writing the same learning journey. Cross-host resume is sequential; this change isolates hook/session state, not all learning-record writes.
- npm publication or edits to real user host installations during implementation tests. Packaging and release preparation are included; actual publication is separate.

## Decisions

### 1. A Node initializer delegates installation to native host CLIs

Add a small ESM package at the repository root, with an `init` executable, a shared setup coordinator, and adapters under `setup/hosts/`. Target Node 22 or later and use standard-library argument parsing, process execution, tests, and interactive selection initially. The eventual npm package exposes the OpenSpec-style `npx <package> init` entry point. A dependency-heavy installer framework is unnecessary for two hosts.

Each adapter implements detection, capability checks, installation inspection, conflict detection, registration, and result formatting. Invoke subprocesses with argument arrays, without shell interpolation. Offer the two hosts as a multi-selection; display detection results and require an explicit selection. No project scope is offered in this first version. Noninteractive execution without a selection-capable terminal exits with instructions rather than guessing.

Before registration, preflight all selected hosts and shared prerequisites. Use native marketplace inventory and installed-plugin inventory to distinguish absent, compatible, disabled, outdated, and conflicting installations. Inspect the documented standalone-skill discovery paths for conflicting Sage registrations, including project-local conflicts visible from the launch directory; report conflicts without deleting them.

Reuse the existing `0-BSCode/sage` marketplace and `sage@sage` plugin identity. Claude registration uses marketplace add and `plugin install --scope user`; Codex uses marketplace add and `plugin add`. Use JSON output where supported and inspect registrations after install. Do not rewrite host configuration files or auto-accept command execution, permissions, hook hashes, or trust. Versions lacking the required interfaces receive an upgrade/manual-setup result.

An existing compatible installation is reused without implicit update. Outdated, disabled, conflicting, or unverifiable registrations receive an explicit next action; setup does not silently replace them. When registration fails after another host succeeded, retain the successful registration. A subsequent run reconciles current native inventory, not a stale installer receipt.

Alternative considered: install a standalone skill with `skills add`. Rejected as the complete setup path because it would omit native hook/specialist registration and can duplicate the Codex plugin's Sage name. A custom copier of host settings was also rejected because it would duplicate host plugin management.

### 2. Preserve the plugin layout and derive paths from the loaded resources

Keep `skills/sage/`, `agents/`, and `tools/` in their existing repository locations. In the skill, resolve the real filesystem location of the loaded `SKILL.md`; its plugin root is two directory levels above the containing skill directory. Pass that absolute root explicitly to router/wrap-up tools and specialist payloads. Never calculate it from the process cwd or a guessed plugin cache path.

Specialists use the explicit root supplied by their caller; Python tools derive internal sibling imports from their own files, as several already do. Existing `SAGE_ROOT` exports remain a documented explicit development override, validated before use. The normal installed path no longer reads global `/tmp/.sage-plugin-root` or `/tmp/.sage-learning-root` slots. Native hook commands retain host-supported plugin-root substitution to locate their entrypoint; that hook substitution is not assumed to exist in subsequent shell calls.

Keep each specialist's Markdown body canonical at root-level `agents/`. Claude alone consumes its native frontmatter; shared delegation instructions explicitly treat provider/model metadata as host configuration rather than a required model choice. Generic Codex specialists follow the body with the selected host model. This avoids two copies of every specialist protocol and preserves Claude's native discovery convention.

Alternative considered: moving everything into the skill. Rejected for this change because native registration already works and would require compatibility generation. A separately installed Python engine package would add another versioned distribution with no immediate need.

### 3. Normalize hook context through host adapters and shared Python handlers

Use small host-specific hook configurations that pass a literal host identifier and native event payload to shared Python handlers under `tools/`. Keep protocol names and output severity consistent with the existing hooks. Python can parse JSON, manage state, and perform checks directly, removing the Bash/jq dependency from the supported runtime hook path. Retain legacy script shims only where needed for compatibility and test their delegation.

The adapters normalize host, parent session ID, event, agent identity, recursive-stop state, and operation correlation into a common internal context. Missing fields are not filled with cwd, newest transcript, or another session's ID. Native subagent event payloads do not universally include the original operation prompt: correlate subagent IDs with explicit operation registrations instead of relying on prompt substring matching alone.

The SessionStart handler emits concise model context containing the actual host, parent session identity, and installation root. It does not activate Sage just because the plugin is loaded. During the existing setup phase, the skill invokes a new internal session-context tool with that explicit context, the resolved topic, and learning directory. Activation follows successful configuration/routing; picker-only, invalid, or cancelled requests do not activate a teaching session. A fresh invocation or resume refreshes the binding. Archive operations use their existing completion checks without activating teaching reminders.

Before invoking a specialist, the coach registers its operation and passes an operation token to the specialist. Where native hooks provide subagent IDs, correlate them with the registered operation. The shared operation-completion path, invoked by the specialist or inline fallback, records completion explicitly; native events can supply additional lifecycle signals but must not mark a failed verification as completed merely because a subagent stopped. Verification markers retain their existing limited meaning: completion of the operation, not proof of factual correctness.

Persist internal session context under `~/.config/sage/runtime/<host>/<hash-of-parent-session-id>/`, with restrictive access, atomic writes and per-session locking for concurrent hook updates. Store validated installation/learning/topic paths and operation state. No raw session ID becomes a path component. Child operations target the parent's namespace. Separate host adapters prevent same-ID collisions across hosts. Keep the resolved learning root bound to the active session even if another session uses an environment override.

The Stop handler consults active context, not cwd. It retains recursive-stop protection, the existing once-per-cycle verification reminder threshold, and the cross-reference block. Successful end-of-session wrap-up closes the teaching activation only after required validation/corrections complete. Native SessionEnd performs best-effort cleanup; resume rebinds the same session deliberately. A hard close cannot be relied upon to checkpoint or run cleanup. Startup/activation must validate retained state before reuse.

When trusted hook context is unavailable, resource discovery still works. Sage explicitly reports unavailable automatic safeguards and retains protocol checks and shared wrap-up validation. It does not invent a session identity or claim parity. Parse errors with no identifiable active session fail open to avoid blocking unrelated work; errors for an identifiable active session produce a visible diagnostic instead of an apparently clean check.

References used to verify the adapter contract: [Claude hooks](https://code.claude.com/docs/en/hooks) and [Codex hooks](https://developers.openai.com/codex/hooks), inspected 2026-11-17. Both describe session identity and model context from startup hooks; Codex documents parent-session identity for subagent hooks. Adapter tests and real-host smoke checks remain necessary because host versions and payload shapes differ.

### 4. Preserve storage semantics and reuse existing checks

Keep `SAGE_LEARNING_ROOT` precedence over `~/.config/sage/config.json`. Setup does not select a learning directory or mutate records; the first learning session retains the preview/confirmation flow. Resolve and validate the resulting absolute path before binding a session. Permission failure produces an access action, never a fallback journey in cwd.

Keep the cross-reference rule in `cross_refs_check.py` and route both wrap-up and hooks through it. Preserve the existing verification-before-teaching and card-check protocols. Do not add a new blanket blocking card gate: today's checkpoint guard is advisory. Pass session context explicitly to wrap-up where lifecycle cleanup needs it, while keeping the current router grammar and topic record format compatible. Claude transcript duration stays best-effort; Codex retains the existing learner-supplied fallback.

### 5. Validate contracts at three levels

- Unit/fixture tests: setup coordination with fake CLIs; JSON result parsing; conflict inventory; event normalization; state isolation; malformed/missing identity; permission errors; reminder/reset cycles; cross-reference behavior outside the learning directory.
- Isolated integration tests: build the npm tarball, run its initializer against fake native CLIs in a temporary home, verify no launch-directory writes or learning-record changes, and validate manifest/resource closure without the development checkout or global `/tmp` bridge. Exercise actual Python checkpoint writers/readers using representative records in both adapter directions.
- Real-host acceptance: with disposable host profiles, confirm native registration, restart/trust instructions, specialist discovery, each safeguard, and sequential Claude-to-Codex and Codex-to-Claude learning resume. Record host versions and outcomes; mocked tests alone do not establish conversational behavior or hook parity. Run these only in isolated authorized environments.

## Risks / Trade-offs

- Host plugin and hook interfaces vary by version → Probe required interfaces, use normalized fixture contracts, and gate support claims on real-host smoke results.
- Native plugin installation follows the repository marketplace release, independently of the initializer version → Check installed manifest/resource capabilities after registration and report unsupported releases; do not imply lockstep versions or auto-upgrade existing installs.
- Session context requires reliable identity and model-followed activation → Supply startup context and explicit operation tools; report unavailable context rather than guessing. This improves scoping but is not an enforcement boundary against an agent bypassing tools.
- User-wide hooks observe unrelated sessions → Remain inactive until Sage activation, use host-qualified state, and test inactive sessions even inside the learning directory.
- Shared learning-root cross-references can include work from another concurrent journey → Retain the existing root-wide consistency rule; simultaneous writes to learning records are outside this change and must not be advertised as safe.
- Host permissions can prevent access to runtime state or the learning directory → Surface the affected capability and required access; never loosen permissions automatically.
- Updates change hook hashes → Keep review/restart instructions in setup and documentation; preserve the host's trust model.

## Migration Plan

1. Introduce shared session/context helpers and adapter hook configurations with tests, retaining the existing plugin roots and invocation forms.
2. Update skill/specialist bootstrap instructions and hook handlers together. Stop depending on global temporary root files; obsolete files can remain ignored rather than deleting another active installation's state.
3. Add the initializer and isolated setup tests. Existing manual marketplace installation remains supported. Existing standalone links are reported for manual reconciliation.
4. Validate both host profiles, existing learning fixtures, and the complete Python suite. Build and inspect the npm tarball before release preparation.
5. Ship as a minor user-facing capability under the repository's release rules. Keep the Claude manifest version authoritative and mirror it in marketplace, Codex, and package metadata. Extend release-hygiene checks to initializer files and metadata. Add pack/build checks, but do not publish npm artifacts or change registry credentials in this work.
6. Rollback consists of reverting the shipping change or selecting a prior plugin release through native host management. No learning-record migration is needed. New internal runtime state is ignored by older versions; existing learning data remains readable.

## Open Questions

- The npm package's final registry name and ownership must be chosen before publication; local tarball tests and implementation use the repository's setup executable independently of that name.
- Minimum supported host versions will be documented from successful capability checks and real-host acceptance, rather than guessed from CLI version strings.
