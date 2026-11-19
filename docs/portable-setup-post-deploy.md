# Portable setup post-deployment testing

Status: pending deployment and live testing. On 2026-11-19 the owner approved
deferring OpenSpec tasks 6.2 and 6.3 from `portable-sage-setup` until after the
initial release. This checklist survives archival of that implementation change.
No item below is complete based on automated or mock-host tests alone.

Use authenticated authorized Claude Code and Codex profiles, review hooks through
native controls, and use a disposable learning directory. Record the installed
Sage version, host versions, invocation, observed result and evidence for each
check in [the acceptance report](portable-setup-acceptance.md).

## Native installation and safeguards (deferred task 6.2)

- [ ] Install the deployed release through native host management; run the guided
  initializer for both hosts and verify repeat setup without duplicate registration.
- [ ] In each host, start outside the learning directory and confirm skill and
  specialist discovery, hook review/restart behavior, startup identity, installation
  resource resolution and explicit specialist operation completion.
- [ ] In each host, observe the verification reminder threshold and reset, the
  unverified-card checkpoint warning, and stale cross-reference Stop blocking.

## Learning continuity and isolation (deferred task 6.3)

- [ ] Complete a short lesson/checkpoint in Claude Code and resume in Codex.
- [ ] Complete a short lesson/checkpoint in Codex and resume in Claude Code.
- [ ] In both directions, confirm due reviews, misconceptions, plan position and
  saved next step in the conversation as well as the learning records.
- [ ] Confirm that an unrelated session inside the learning directory receives no
  Sage safeguards, and that another sitting requires its own completed checkpoint.

If a check fails, record the failure and open a focused fix before marking the
item complete. Full conversational compatibility remains unverified until the
relevant live checks pass; this does not prevent the initial deployment.
