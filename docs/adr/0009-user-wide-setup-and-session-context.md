# User-wide setup and explicit host-qualified session context

Sage retains the native plugin layout from ADR 0007. A Node initializer selects
Claude Code, Codex, or both and delegates user-wide registration to their native
CLIs; no parallel standalone skill registration or host settings rewrite is used.

Loaded skill paths determine the plugin root. Specialists receive the absolute
root explicitly. Global temporary root files are no longer part of discovery.

Python event adapters distinguish host and parent session identity. Startup
context supplies identity but does not activate Sage. The skill activates only
a routed learning session; explicit specialist operation tokens record actual
completion rather than inferring success from a generic worker's exit event.
State uses atomic locked updates in a host-qualified runtime directory.

This supersedes ADR 0007's shared-hook-file/bootstrap details while retaining its
root-level native agent discovery decision. It extends ADR 0006: cross-reference
validation remains shared, and active-session lookup replaces the Stop hook's
working-directory gate. Advisory checks remain advisory. No learning-record or
invocation migration is introduced.

The agent must follow the explicit operation protocol; hooks and markers cannot
prove factual correctness or guarantee saving after a hard close. Unknown session
identity is reported rather than guessed. Additional hosts require new adapters
and acceptance evidence, not a second copy of the teaching protocol.
