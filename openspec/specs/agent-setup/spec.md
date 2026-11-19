# agent-setup Specification

## Purpose

Provide one user-wide setup experience that configures Sage for selected coding assistants while preserving native integrations and existing learning data.

## Requirements

### Requirement: Interactive host selection
The initializer SHALL offer Claude Code and Codex as independently selectable hosts and SHALL require at least one selection before installation. Detection SHALL inform availability without silently selecting or installing a host.

#### Scenario: Both hosts selected
- **WHEN** the user selects Claude Code and Codex
- **THEN** the initializer configures each selected host and reports an individual result for each

#### Scenario: No selection
- **WHEN** the user submits an empty selection or cancels before installation
- **THEN** the initializer exits without changing host registrations or learning records

### Requirement: User-wide native integration
The initializer SHALL register Sage user-wide through each selected host's supported plugin mechanism, including its skill, supported hooks, and specialist integration. It SHALL preserve the documented host-specific invocation forms and SHALL NOT create project-local Sage configuration in the launch directory.

#### Scenario: Installation from an unrelated project
- **WHEN** the user initializes Sage from a coding project
- **THEN** Sage becomes available in new sessions of the selected hosts outside that project without adding Sage setup files to that project

#### Scenario: Native components retained
- **WHEN** installation completes for a selected host
- **THEN** its registered Sage plugin contains the expected skill, hooks, and specialist resources rather than only a standalone skill registration

### Requirement: Prerequisite checks
The initializer SHALL check required runtimes, hook dependencies, selected host executables, and required plugin-management capabilities before registering plugins. An unavailable prerequisite SHALL produce an actionable error without being reported as a successful installation.

#### Scenario: Missing Python or hook dependency
- **WHEN** Python or a dependency required by the shipped hooks is unavailable
- **THEN** initialization identifies the missing dependency and stops before plugin registration

#### Scenario: Unsupported host CLI
- **WHEN** a selected host lacks the required plugin-management commands
- **THEN** initialization identifies that host and the unsupported capability and provides an upgrade or manual-setup action

### Requirement: Existing installation reconciliation
The initializer SHALL reuse a compatible user-wide Sage installation, avoid duplicate registrations on repeat runs, and identify conflicting sources or standalone Sage skills before installing. It SHALL NOT remove or overwrite an unmanaged installation or unrelated host configuration automatically.

#### Scenario: Repeat setup
- **WHEN** initialization runs again for a host with a compatible user-wide Sage plugin
- **THEN** it reports that installation as already configured without adding another Sage registration or implicitly updating the plugin

#### Scenario: Conflicting standalone skill
- **WHEN** a selected host also discovers a standalone Sage skill that conflicts with the plugin registration
- **THEN** the initializer reports the conflict and a remediation action without deleting the skill or claiming the host is ready

#### Scenario: Marketplace name collision
- **WHEN** the expected marketplace name is registered to another source
- **THEN** the initializer reports the source conflict without replacing that registration

### Requirement: Independent setup outcomes
The initializer SHALL report each selected host as configured, already configured, requiring user action, or failed. It SHALL preserve successful host setup when another host fails and SHALL provide a safe retry path without claiming overall readiness when any selected host remains incomplete.

#### Scenario: Second host installation fails
- **WHEN** one host installs successfully and the other host's installation fails
- **THEN** the summary preserves the successful result, reports the failure with a next action, and a retry does not duplicate the successful installation

### Requirement: Host trust and access controls
The initializer SHALL preserve host-managed hook trust and filesystem permissions. Its completion summary SHALL distinguish plugin registration from runtime readiness and explain any required hook review, new session, or learning-directory access action.

#### Scenario: Hook approval is pending
- **WHEN** a plugin is registered but the host requires hook review
- **THEN** setup reports the remaining user action without approving hooks automatically or describing automatic safeguards as active

### Requirement: Existing learning storage preservation
Initialization SHALL preserve the configured learning directory and existing learning records. When no learning directory is configured, it SHALL explain that the first Sage learning session will collect and confirm that location.

#### Scenario: Existing learning journey
- **WHEN** the user initializes another supported host after studying with Sage
- **THEN** the initializer leaves the learning configuration and records unchanged so the new host can resume them

#### Scenario: Fresh installation
- **WHEN** no learning directory is configured
- **THEN** setup defers learning-directory selection to the first learning session without inventing or writing a default learning directory
