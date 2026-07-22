# Releasing

There is no release pipeline: **merging to main is publishing**, because
installs track this repository directly. These rules exist so every published
change has a version identity and a stated reason.

## The rules

1. **`plugin.json` is authoritative.** The `version` in
   `.claude-plugin/plugin.json` is the single source of truth. The copy in
   `.claude-plugin/marketplace.json` is a mirror and must always be equal.
   CI fails the build if they diverge.

2. **Every shipping change bumps the version.** A *shipping change* is any
   change under `SKILL.md`, `agents/`, `hooks/`, `references/`, `tools/`, or
   `.claude-plugin/` — the things a user actually installs and runs. Bump the
   version in the same PR. Changes confined to repo docs, tests, or CI must
   *not* bump the version. CI enforces both directions of this on PRs.

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
