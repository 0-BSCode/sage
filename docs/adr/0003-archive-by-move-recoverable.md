# Archive a Project by moving it, one-way-but-recoverable

`/sage archive <topic>` retires a **Project** (its on-disk container). We chose to **move** the project directory to `<learning_root>/.archive/<slug>/` rather than deleting it or flagging it in place, and to ship the operation **one-way** (no `unarchive` verb) while keeping it **losslessly recoverable** by hand. A dedicated, unit-tested `tools/archive_project.py` performs the move + cross-refs surgery; the router only dispatches to it via a new `mode: "archive"`.

## Why move, not a marker or registry

Discovery is `list_projects()` scanning `<root>/<slug>/learning/journal/index.md`. "Archived" fundamentally means "no longer appears in the `learn` picker, without being destroyed." Moving the directory under a hidden `.archive/` achieves that with almost no change to discovery, is self-evident to a human running `ls`, physically declutters the picker (the actual felt problem), and reverses with a single `mv`. A marker file or a central registry keeps clutter in place and adds hidden state that can desync from the filesystem.

## Cross-refs handling (the hard part)

The learning root's `cross-refs/` registry has two tiers. `INDEX.md` (`| Project | Overlaps With |`) is the **load-driver**: the coach loads every file named in a project's Overlaps-With cell. Per-project shards (`<slug>.md`, `| Concept | Also Covered In | ... |`) carry human-readable notes only.

Archiving a project therefore must scrub **both** its own INDEX row **and** every inbound Overlaps-With cell that names it — otherwise a future session loads a shard that has moved away (file-not-found). This is functionally required, not cosmetic. We do **not** scrub the archived name from sibling shards' `Also Covered In` columns: those never drive loading, so a stale mention is harmless, and chasing it would rewrite ~every shard in the registry (write-risk) and have to be undone on recovery. The archived project's own shard is **moved** (co-located at `.archive/<slug>/cross-refs.md`), not edited.

## One-way by design — no `unarchive`

There is **no `unarchive` verb, and none is planned**. This is a decision, not a deferral. Archiving is an explicitly confirmed act; the confirmation states the irreversibility at the moment it matters. Consenting to archive means consenting to give up the tracking state (knowledge map, cards, SRS schedule) and keep only the artifacts as a readable record. Returning to a topic means starting a fresh Project.

The rejection is deliberate because a *correct* `unarchive` is far more expensive than it looks, and we designed it far enough to know:

- **Stashed INDEX rows are snapshots that go stale, and restoring them verbatim is order-dependent and wrong.** Observed in real data: `ai-empirical-evals` (archived 09:12) stashed `| rag-retrieval-metrics | rag-triad, ai-empirical-evals, product-analytics, observability |`; `observability` (archived 09:33) stashed the same project's row as `| rag-retrieval-metrics | rag-triad, product-analytics |`. They disagree. Pasting the first back would resurrect `observability` while it is still archived — recreating exactly the dangling-load bug archive exists to prevent. A correct restore must re-insert the single slug token into the *current* cell and validate every overlap against what is currently active — a merge, not a restore.
- **Generations are ambiguous.** Numeric-suffixed archives (`alpha`, `alpha-2`) share one `original_slug`, so a typed slug cannot identify a target; it needs a picker keyed on `archive-meta.json`.
- **Restore collides on three surfaces at once** — the project directory, the cross-ref shard, and the INDEX row — because the slug *is* the identity. If a new Project has taken the name (which `/sage learn <topic>` does freely once the old one is archived), restoring requires the learner to rename, which then invalidates historical references to the old slug.

That is a large, well-tested machine for an operation that fires approximately never. Not building it is the cheaper correct answer.

## Recovering by hand

Nothing is deleted, so recovery stays possible without a command. The removed INDEX fragments (own row + stripped inbound cells) are stashed in `<archive-dir>/archive-meta.json` alongside provenance (original slug, archived date passed in by the skill for determinism, inbound-ref count). The stash keeps its place precisely because it makes the rare manual restore tractable; the recipe is documented in the README.

**The trap to avoid when restoring by hand:** do not paste `index.inbound_rows[].row` back verbatim — those are snapshots, per the order-dependence above. Re-add only the archived slug to each inbound project's *current* Overlaps-With cell, and drop any `own_overlaps` entry whose project is no longer active.

## Consequences

- **Collision:** if `.archive/<slug>/` exists (archive → recreate same topic → archive again), the tool uses the lowest free numeric suffix (`.archive/<slug>-2/`). Never overwrites (honors "nothing is deleted"); deterministic, so testable.
- **Quiescent-only invariant:** `archive_project.py` is stateless and assumes at-rest data. If the target is the session's currently-active project, the **skill** runs the end-of-session checklist (journal + savepoint + cross-refs update) to fully persist *before* dispatching archive. The tool never reasons about live session state. Checkpoint updates cross-refs first, then archive moves/scrubs them — sequential, no conflict with the `enforce-cross-refs` Stop hook.
- **Confirmation is mandatory** and names the inbound-reference count, so archiving a heavily-linked hub project gives the learner pause.
- Bare `/sage archive` opens the `list_projects` picker (safer than typing a slug); `/sage archive <topic>` resolves a slug and errors — creating nothing — if no project matches.
