# Mandatory command verbs for the `/sage` entry point

Adding an archive capability required a way to tell "start a learning session" apart from "archive a topic" at the single `/sage` entry point. We chose to make an explicit leading verb **mandatory** — the grammar is now `/sage <verb> <topic>` with exactly two verbs, `learn` and `archive` — accepting a breaking change to the previous free-form `/sage <topic>` grammar.

Previously the router inferred intent: any argument was treated as a topic to learn, except a small set of bare resume keywords (`continue`, `resume`, `pick`, `list`). Bolting `archive` onto that scheme reintroduces an ambiguity — a topic literally named "archive" is indistinguishable from the archive verb. We considered three options:

- **Argument dispatch with `learn` as an implicit default** (backward-compatible) — `/sage react hooks` still learns, `/sage archive x` archives. Rejected: it only shrinks the ambiguity rather than removing it. A topic named after a reserved verb still can't be expressed without an escape hatch.
- **A separate skill/command** (`/sage-archive`) — rejected: adds a second plugin surface and duplicates the config + project-discovery boilerplate that already funnels through `session_router.py`.
- **Mandatory verb** (chosen) — `/sage learn <topic>` and `/sage archive <topic>`. A topic named "archive" is unambiguous because `learn` is always present: `/sage learn archive`.

Consequences:

- **Breaking change.** Every prior invocation form (`/sage react hooks`, `/sage continue`) is now invalid. The router emits an "unknown verb" error that maps the old forms to the new ones (`/sage continue` → "Did you mean `/sage learn`?"). `argument-hint`, the README, and SKILL.md examples all change.
- The old resume keywords (`continue`/`resume`/`pick`/`list`) are **dropped**, not aliased. `learn` subsumes them: `learn <topic>` starts-or-resumes (the router already branches on journal existence), and bare `learn` opens the project picker. Keeping aliases would make the grammar half-mandatory and undercut the collision guarantee.
- `learn` and `archive` share the router's config resolution and `list_projects` discovery, so the new surface adds one dispatch branch rather than a parallel entry point.
