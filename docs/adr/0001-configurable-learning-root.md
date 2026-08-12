# Configurable learning root via config file

The plugin needs to know where learning topic directories live (the "learning root"). This path was previously hardcoded to the author's machine, breaking the plugin for all other users.

We chose a config file at `~/.config/sage/config.json` with env var override, over three alternatives:

- **Hardcoded path** (status quo) — only works on one machine.
- **Env var only** — invisible to new users who won't know to set it.
- **Auto-detect from CWD** — unreliable since users may run sessions from different directories.

The config file is created on first run via a prompt in the skill. Resolution order: `SAGE_LEARNING_ROOT` env var > config file > first-run prompt. The env var override follows standard Unix convention and supports temporary overrides without editing config.

The config uses a `version` field (`{"learning_root": "...", "version": 1}`) so the format can be migrated later as the plugin grows.

See: https://github.com/0-BSCode/ultralearn/issues/1
