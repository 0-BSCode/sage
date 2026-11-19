# Releasing

For native plugins, **merging to main is publishing**, because
installs track this repository directly. These rules exist so every published
change has a version identity and a stated reason.

## The rules

1. **`plugin.json` is authoritative.** The `version` in
   `.claude-plugin/plugin.json` is the single source of truth. The copies in
   `.claude-plugin/marketplace.json` and `.codex-plugin/plugin.json` are
   mirrors and must always be equal. CI fails the build if they diverge.

2. **Every shipping change bumps the version.** A *shipping change* is any
   change under `skills/`, `agents/`, `hooks/`, `tools/`, `.claude-plugin/`,
   or `.codex-plugin/` — the things a user actually installs and runs. Bump
   the version in the same PR. Changes confined to repo docs, tests, or CI
   must *not* bump the version. CI enforces both directions of this on PRs.

3. **Every version bump gets a changelog entry.** Add a section to
   `CHANGELOG.md` in the same PR. CI fails a PR that bumps the version
   without touching the changelog.

4. **Tags are cut by CI, never by hand.** On every push to main, CI tags
   `v<version>` from `plugin.json` if that tag does not already exist
   (`.github/workflows/tag.yml`). Do not create or push release tags manually.

## What the bump size means

The plugin is on the 1.x line but is still maturing; treat versions as:

- **Patch** — fixes and internal changes, including observable behavior
  changes to *internal tools* (CLI tools and agents only the coach invokes —
  they upgrade in lockstep with the skill and are outside the compatibility
  surface). Precedent: `session_duration`'s exit-code change was a patch.
- **Minor** — new user-facing capability.
- **Major** — a change to the **compatibility surface**, which is exactly two
  things:
  1. *Invocation* — how the user invokes or resumes the skill.
  2. *Artifacts* — the learning-journey files written into a user's project.
     These outlive upgrades: a new version must read artifacts written by any
     earlier 1.x version, or ship a migration.

## Setup package

`package.json` mirrors the authoritative plugin version. Changes under `bin/`,
`setup/`, and setup packaging files are shipping changes and require a version
bump plus changelog entry, just like plugin changes. Run `npm test` and
`npm run pack:check` as well as the Python suite and native manifest validation.

The package name is provisional until registry ownership is confirmed. npm
publication is separate from repository-based plugin releases: this repository
does not automatically publish packages or configure registry credentials.
Inspect a local tarball before separately authorized publication. Never publish
from this development workflow or imply that an unpublished npx command works.
The initializer checks actual installed capabilities; its version alone cannot
prove a marketplace plugin has been updated.

## Initial portable-setup release

For 1.3.0, live conversational acceptance in Claude Code and Codex is explicitly
deferred until after deployment. Automated checks and isolated native registration
have passed; live hook delivery, specialist execution and conversational resume
remain unverified. These live checks do not block the initial release or archiving
its implementation change. They still gate claims of fully verified host support.

After deployment, run [the follow-up checklist](portable-setup-post-deploy.md)
against the installed release and add evidence to
[the acceptance report](portable-setup-acceptance.md). Keep deferred items open
until actual results exist. Archiving the implementation does not close them.
