# session-portability Specification

## Purpose

Keep Sage learning sessions and their safeguards consistent across Claude Code and Codex, independently of the launch directory, while sharing existing learning records.

## Requirements

### Requirement: Installation-relative resource discovery
Sage SHALL resolve its teaching protocols, specialist instructions, and Python tools from the loaded installation independently of the working directory. Starting another host or another Sage installation SHALL NOT redirect an existing session to different resources through a shared temporary path.

#### Scenario: Start outside the installation
- **WHEN** Sage is invoked from a directory outside its installation and learning directory
- **THEN** it resolves the resources belonging to its loaded installation and can begin the configured learning flow

#### Scenario: Concurrent installations
- **WHEN** another host starts Sage from a different installed copy
- **THEN** the first session continues resolving its own resources without using a path overwritten by the other host

### Requirement: Shared learning-directory resolution
Both hosts SHALL use the existing learning-directory configuration and environment override precedence. A topic's location SHALL be independent of the session working directory. A missing configuration SHALL trigger the existing location preview and confirmation flow before learning records are created.

#### Scenario: Same topic from different directories
- **WHEN** the learner invokes the same topic from two launch directories using the same learning configuration
- **THEN** Sage resolves the same topic records rather than creating directory-specific journeys

#### Scenario: Environment override
- **WHEN** a learning-directory environment override is supplied
- **THEN** Sage uses it ahead of the saved configuration without overwriting that saved configuration implicitly

### Requirement: Cross-host checkpoint continuity
A completed learning checkpoint written through either supported host SHALL remain readable and resumable through the other host without a learning-record migration. Resume SHALL retain plan position, due reviews, misconceptions, and the saved next step.

#### Scenario: Claude checkpoint resumed in Codex
- **WHEN** the learner completes a checkpoint through Claude Code and invokes the same topic through Codex with access to the same learning directory
- **THEN** Codex loads that checkpoint, handles due reviews first, and continues from the saved position

#### Scenario: Codex checkpoint resumed in Claude
- **WHEN** the learner completes a checkpoint through Codex and resumes through Claude Code
- **THEN** Claude Code uses the saved learning evidence and next step without starting a new journey

### Requirement: Explicit active-session identity
Automatic Sage safeguards SHALL associate activity with a host-qualified parent session and its resolved learning directory. They SHALL NOT infer activity solely from the working directory, a globally shared latest-session marker, or the presence of installed Sage resources.

#### Scenario: Active session outside learning directory
- **WHEN** the learner invokes Sage from another directory with hooks enabled and trusted
- **THEN** subsequent relevant hook events apply Sage safeguards to that active session

#### Scenario: Unrelated session
- **WHEN** a session has not activated Sage, including a session launched inside the learning directory
- **THEN** Sage's verification reminders and cross-reference stop checks do not activate for that session

#### Scenario: Isolation across sessions
- **WHEN** verification completes in one active session while another active session exists
- **THEN** only the matching session's reminder and checkpoint-verification state changes

### Requirement: Safeguard behavior preservation
On compatible supported hosts with hooks enabled and trusted, Sage SHALL retain verification reminders, checkpoint-card verification warnings, and the stale cross-reference stop check. Shared wrap-up validation SHALL continue to report stale cross-references independently of hook execution. Warning-only safeguards SHALL remain warnings.

#### Scenario: Verification reminder overdue
- **WHEN** an active verification-tracked session reaches the existing five-response threshold without another verification operation
- **THEN** Sage emits its overdue reminder once until verification resets the reminder cycle

#### Scenario: Unverified cards at checkpoint
- **WHEN** an active session begins a checkpoint operation that mentions cards without the matching verification marker
- **THEN** Sage emits the existing verification warning without claiming it has independently verified the cards

#### Scenario: Stale cross-references outside learning directory
- **WHEN** an active session launched outside the learning directory reaches a normal stop with stale cross-references
- **THEN** the trusted stop hook requests correction before stopping, with recursive-stop protection retained

#### Scenario: Wrap-up without hooks
- **WHEN** session wrap-up runs while hooks are unavailable
- **THEN** shared cross-reference validation still reports stale references and Sage does not report a clean wrap-up until that issue is resolved

### Requirement: Honest capability and failure reporting
Sage SHALL report when resource access, learning-directory permissions, hook trust, or reliable session identity prevents expected functionality. It SHALL NOT treat missing verification or a failed checkpoint as successful. Missing identity SHALL NOT attach safeguards to another session or block unrelated work.

#### Scenario: Learning directory is inaccessible
- **WHEN** host permissions prevent reading or writing the configured learning directory
- **THEN** Sage explains the required access action and does not silently create a replacement journey in the working directory

#### Scenario: Hooks or session identity unavailable
- **WHEN** Sage cannot establish its automatic safeguards for the current session
- **THEN** it reports the affected automatic behaviors and continues only with explicitly identified available protocol and tool checks

#### Scenario: Checkpoint write fails
- **WHEN** saving a checkpoint fails
- **THEN** Sage reports that progress has not been fully saved and identifies the failed operation

### Requirement: Existing learning interface preservation
The shared command grammar and teaching/checkpoint protocols SHALL remain compatible with existing supported invocation forms. Host-specific specialist metadata SHALL NOT require another host to select an unavailable model. Inline specialist execution SHALL retain the existing disclosure that it provides self-verification rather than an independent agent check.

#### Scenario: Existing invocation
- **WHEN** the learner uses the documented Claude Code or Codex Sage invocation with `learn <topic>`
- **THEN** Sage follows the existing first-session or resume workflow

#### Scenario: Specialist executed without native registration
- **WHEN** a host delegates to a generic specialist or performs the documented inline fallback
- **THEN** it follows the shared specialist instructions without requiring Claude-specific model metadata and discloses inline verification limitations
