# Portable setup acceptance

Checked 2026-11-19. Implementation is present; full authenticated conversational
acceptance is not complete. Do not interpret mock-host or direct-handler checks
as proof of live hook delivery or model adherence.

## Automated evidence

| Contract | Evidence | Result |
|---|---|---|
| Explicit host selection and cancellation/no selection | `setup/tests/init.test.js` selection parser and noninteractive CLI cases | Passed; live interactive host acceptance remains below |
| User-wide registration and host-specific native commands | Setup adapter fixtures plus native CLI registration below | Passed |
| Prerequisites and malformed/unsupported host output | Fake-CLI tests for Python/host absence, unsupported flags, malformed JSON | Passed |
| Repeat setup, conflicts, no implicit updates | Installer tests for standalone skills, marketplace collision, scopes, disabled/outdated installs, version skew | Passed |
| Partial failures and accurate completion guidance | Installer tests for preserved success/retry and post-install inspection | Passed |
| Trust/access controls and learning storage preservation | No auto-trust flags; setup fixtures preserve config; completion instructions identify remaining actions | Passed at tool level; actual hook trust remains unverified |
| Resource lookup independent of cwd and other installations | `test_resource_paths.py`, relocated copies and symlinks with spaces, no global root files | Passed |
| Shared learning-directory precedence and access failures | Existing config tests plus `test_session_context.py` | Passed |
| Host-qualified parent identity and state isolation | Session/hook tests, hashed keys, concurrent subprocess updates, explicit token correlation, interrupted-operation recovery | Passed |
| Safeguard severity and lifecycle | Counter/reset/card-warning/cross-reference tests in both adapters | Passed via actual Python handlers; live host delivery remains unverified |
| Sequential checkpoint continuity | `test_cross_host_resume.py` runs card/journal/SRS tools in relocated installations in both directions; preserves plan, misconceptions, savepoint and due reviews | Passed at record/tool level; conversational resume remains unverified |
| Native specialist layout and existing invocation/protocols | Manifest coherence checks and Claude native validation | Passed statically; conversational specialist execution remains unverified |

Commands completed successfully:

```bash
npm test
npm run pack:check
PYTHONPATH=tools:tools/srs:tools/assessment:tools/coach:tools/plateau:tools/demo:tests .venv/bin/python -m unittest discover -s tests -q
claude plugin validate . --strict
openspec validate portable-sage-setup --strict
git diff --check
```

Results: 13 Node tests, 344 Python unittest cases, packed initializer isolation
checks, native manifest validation, and strict OpenSpec validation passed.
The existing plateau detector's additional script-level checks also passed.
Claude's validator reported a non-blocking missing marketplace icon warning.

Review regression checks cover the installed Codex cache separately from its
marketplace checkout, including a custom CODEX_HOME and a damaged cached tool.
A disposable native Codex install reconfirmed the versioned cache layout; its
list output omits installedPath while the installation receipt provides it.
Unknown or missing cache resources require manual reconciliation.

Each learn/resume activation now creates a new sitting ID. Previous checkpoints
cannot satisfy closure, previous verification markers are reset, and late worker
completion cannot update the new sitting. Closure also checks that activation
has not changed while wrap-up runs.

Wrap-up returns optional metrics, reflection and transcript-duration failures in
warnings. Blocking errors remain in blocking_errors (also exposed as errors for
existing callers); learning-directory and cross-reference failures still prevent
closure. Both hosts have regression coverage for these outcomes.

The system Python was 3.9; a local Python 3.12.15 environment ran the complete
unittest suite because an existing test module uses Python 3.10+ annotations.
pytest was unavailable and dependency fetching failed on DNS. All current Python
test cases are unittest-based; CI continues to run them through pytest on 3.12.

## Native host registration

Used temporary HOME/config directories, a copied local marketplace, and unrelated
launch directories. Real user profiles and credentials were not copied or edited;
temporary profiles were removed afterward. Native registration was exercised
directly rather than changing the production-source-only initializer to accept a
test marketplace.

| Host | Version | Local marketplace registration | User-wide Sage install and inventory |
|---|---|---|---|
| Claude Code | 2.1.326 | Passed | `sage@sage`, 1.3.0, user scope, enabled |
| Codex CLI | 0.160.1 | Passed | `sage@sage`, 1.3.0, installed and enabled |

An initial Codex test profile lacked its explicitly configured CODEX_HOME
directory; after creating that disposable directory, native registration passed.
This was a test-profile setup issue, not a host registration success claim.

## Remaining acceptance gates

OpenSpec tasks 6.2 and 6.3 remain unchecked because neither disposable host profile
was authenticated: Claude reported `loggedIn: false`; Codex reported `Not logged
in`. Hooks were not automatically trusted. No credentials were copied and no live
lesson was run through another profile to bypass this boundary.

Before claiming full host support, run the following in authenticated disposable
profiles with hooks reviewed through native controls:

1. Invoke Sage from outside the learning directory; verify actual startup context,
   root resolution, specialist execution and explicit operation completion.
2. Reach the reminder threshold, exercise an unverified-card checkpoint warning,
   and confirm stale cross-references trigger the native Stop hook. Verify an
   unrelated session is unaffected, even inside the learning directory.
3. Complete a short lesson/checkpoint in Claude and resume in Codex, then reverse
   direction. Confirm due reviews, misconceptions, plan position and next step in
   the conversational brief, not just the files.
4. Record actual trust/restart behavior and host versions, then complete tasks
   6.2 and 6.3 only when that evidence exists.

The npm name is provisional and the package has not been published. The local
initializer targets the official marketplace source; until the updated plugin is
released there, it correctly reports older installed layouts as requiring action.
