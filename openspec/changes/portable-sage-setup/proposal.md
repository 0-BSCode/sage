# Proposal

## Why

Sage already supports Claude Code and Codex, but users must follow separate installation paths, and resource discovery and some automatic safeguards depend on host startup hooks or the working directory. Users need one setup experience that makes Sage available across directories while preserving its learning workflow, safeguards, and shared learning records.

## What Changes

- Introduce an OpenSpec-style initialization command that asks whether to configure Claude Code, Codex, or both. `npx <package> init` is the intended experience; the published package name remains undecided.
- Install user-wide by default. Keep learner records in a separately configured learning directory, independent of where the assistant session starts. Reuse existing learning-directory configuration and records.
- Configure each selected host's skill, specialist integration, and supported lifecycle hooks through host adapters backed by shared tutoring resources. Preserve existing plugin installations and invocation forms; detect existing or conflicting registrations and avoid duplicate Sage skills.
- Make shared resource discovery reliable without relying on a global hook-written temporary file. The packaging mechanism remains a design decision; moving all resources inside the skill is not a requirement.
- Preserve safeguards as part of the portability contract. Retain supported hooks, place suitable record-integrity validations in shared tools, and ensure relevant safeguards operate for an active Sage session started outside the learning directory without affecting unrelated sessions. Surface remaining host differences rather than silently claiming equivalent enforcement.
- Preserve the learner-facing flow: invoke `learn <topic>`, configure storage on first use, establish goals, plan and learn, checkpoint, then resume. Validate that a completed checkpoint written through one host can be resumed through the other using the same records.
- Report missing runtime prerequisites, required host trust or permissions, and incomplete host setup clearly instead of presenting partial setup as success.

The initial supported hosts are Claude Code and Codex. Additional hosts, regular ChatGPT integration, cross-device synchronization, a standalone published tutoring-engine CLI, changes to teaching methods, and learning-record format migrations are outside this change.

## Capabilities

### New Capabilities

- `agent-setup`: Interactive host selection, user-wide host registration, prerequisite and conflict detection, and accurate setup results for Claude Code and Codex.
- `session-portability`: Working-directory-independent resource and learning-directory resolution, host-aware safeguards for active Sage sessions, and checkpoint continuity between supported hosts.

### Modified Capabilities

None. The project has no existing OpenSpec capability specifications. These new specifications will describe the relevant existing behavior alongside the new setup and portability requirements.

## Impact

- Host manifests, specialist registration, hook configuration, and installation documentation are affected. Existing native integration must remain functional, including Claude's discovery of root-level agent definitions.
- Skill instructions, specialist instructions, path bootstrap logic, session configuration/routing, wrap-up integration, and hook session detection may require changes. Existing inline specialist fallbacks and shared cross-reference validation should be reused.
- A distributable initializer and its release/versioning integration are needed. Node-based execution is implied by the intended `npx` entry point; package ownership, supported runtime versions, and the host installation mechanism require investigation during design. The Python engine remains in use.
- Validation must cover isolated installations, repeat setup and existing-install conflicts, startup outside the learning directory, safeguard behavior, and cross-host checkpoint/resume. Existing tool tests and plugin-layout tests must continue to protect supported behavior.
- Host filesystem permissions and hook trust requirements still apply. Setup must explain any required user action and must not bypass host controls.
