# Sage

Turn Claude Code into a personal tutor that tracks what you've mastered, catches what's slipping, and circles back until it sticks.

<!-- TODO: Add a gif/screenshot showing a session in action — ideally capturing a retrieval question, the learner answering, and a knowledge map or SRS update in one flow -->

## Features

- **Teaches through questions, not lectures** — the coach uses Socratic dialogue to make you reason through concepts instead of passively reading explanations
- **Spaced repetition** — an SM-2 scheduling engine tracks every concept and quizzes you at the right time, before you forget
- **Seamless resume** — stop anytime, pick up exactly where you left off. Overdue reviews are handled first automatically
- **Fact-checked teaching** — a verification gate checks claims, code examples, and flashcard answers against current sources before they reach you
- **Capstone projects** — once you've built enough mastery, the coach designs portfolio-worthy projects tailored to what you've learned

## Install

```bash
/plugin marketplace add 0-BSCode/sage
/plugin install sage@sage
```

## Getting started

```
/sage <topic>
```

The coach starts by asking about your goals, prior knowledge, and how much time you have. It builds a structured learning plan from your answers, then jumps straight into teaching. Each session ends with a checkpoint, so you can close the terminal and come back anytime.

## Usage

Examples:
- `/sage React hooks`
- `/sage distributed systems`
- `/sage statistics for ML`

### Resuming

Run `/sage <same topic>` again. The coach detects your existing artifacts, loads your last savepoint, handles any overdue reviews, then continues from where you stopped.

## What a session produces

Your learning progress lives in human-readable files you own — not in a chat history. Everything is structured markdown and JSON, created in your working directory:

```
<topic-slug>/
└── learning/
    ├── plan.md
    ├── journal/
    │   ├── index.md
    │   └── session-01.md
    ├── knowledge-map.md
    ├── cards.md
    ├── cards.srs.json
    ├── weak-spots.md
    ├── coach-errors.md
    ├── coach-insights.md
    ├── questions.json
    ├── metrics/
    │   ├── dashboard.md
    │   └── history.json
    └── docs/
        ├── references/
        └── demos/
```

Artifacts are automatically git-committed so you never lose progress.

For cross-topic consolidation, start all your learning topics from the same parent directory. A shared `cross-refs/` directory at the parent level tracks concept overlaps across topics.

<details>
<summary><h2>How it works</h2></summary>

The plugin has three layers:

**Skill** (`/sage`) — the coach. Runs the session, makes pedagogical decisions, and interacts with you directly. Uses Socratic questioning, retrieval practice, and deliberate difficulty.

**Agents** (7 subagents) — delegated specialists:
| Agent | Role |
|-------|------|
| artifact-clerk | File I/O, format compliance, cross-artifact validation |
| assessment-agent | Calibrated question generation and evaluation |
| verification-gate | Fact-checking gate for claims, code, and flashcards |
| reference-clerk | Standalone reference document generation |
| demo-generator | Interactive HTML demos for persistent misconceptions |
| capstone-architect | Portfolio-worthy capstone project design |
| learning-git | Artifact version control |

**MCP Tools** (38 tools) — deterministic operations the agents call:
| Category | Tools |
|----------|-------|
| SRS Engine | `srs_init`, `srs_sync`, `srs_due`, `srs_grade`, `srs_stats`, `srs_forecast` |
| Cards | `card_append`, `card_validate`, `card_fix` |
| Journal | `journal_append`, `journal_validate`, `journal_fix` |
| Knowledge Map | `kmap_add_concept`, `kmap_update_status`, `kmap_changelog_append`, `kmap_fix_legend`, `kmap_ensure_sections`, `kmap_validate` |
| Weak Spots | `weak_spot_append`, `weak_spot_validate`, `weak_spot_fix` |
| Assessment | `assessment_init`, `assessment_add`, `assessment_add_batch`, `assessment_select`, `assessment_record`, `assessment_coverage`, `assessment_stats`, `assessment_calibrate` |
| Plateau Detection | `plateau_detect` |
| Coach Metrics | `coach_snapshot`, `coach_trends`, `coach_compare` |
| Coach Reflection | `coach_reflect`, `coach_evaluate` |
| Demos | `demo_append`, `demo_validate` |
| Session Metrics | `session_metrics` |

</details>

## FAQ

<details>
<summary><strong>What Claude Code plan do I need?</strong></summary>

Sage uses Opus and spawns multiple subagents per session. The **Max plan** is recommended. Pro plan users will likely hit rate limits mid-session, which interrupts the teaching flow. Token consumption is tracked per session in your journal entries.
</details>

<details>
<summary><strong>How long is a typical session?</strong></summary>

As long as you want. The coach adapts to quick sessions (30–45 min), deep dives (60–90 min), or short spaced review sessions (15–30 min). When you're ready to stop, just say so — the coach wraps up, checkpoints your progress, and you can pick up later.
</details>

<details>
<summary><strong>Where does my learning data go?</strong></summary>

Everything stays on your machine — nothing is sent to a remote server. All learning data is plain markdown and JSON files you own. On first run, Sage asks you to pick a directory (your "learning root"). That choice is saved to `~/.config/sage/config.json`. You can also set it via the `SAGE_LEARNING_ROOT` environment variable. Each topic gets its own subdirectory under the learning root.
</details>

<details>
<summary><strong>Can I use this for non-programming topics?</strong></summary>

Yes — the learning techniques work for any topic. The core loop (Socratic questioning, spaced repetition, retrieval practice) is topic-agnostic. The verification gate checks general factual claims, not just code — though it's most precise for technical subjects where authoritative documentation is readily available.
</details>

<details>
<summary><strong>Can I learn multiple topics at once?</strong></summary>

Yes. Each topic gets its own isolated directory (e.g., `react-hooks/learning/`, `distributed-systems/learning/`). If you start all your topics from the same learning root, Sage maintains a shared `cross-refs/` directory that tracks concept overlaps across topics — so if "closures" comes up in both your JavaScript and your Python journey, the coach knows and can reference your existing understanding.
</details>

<details>
<summary><strong>I closed my terminal mid-session. Did I lose progress?</strong></summary>

If you end a session normally, everything is checkpointed and git-committed — your exact position, pending reviews, open questions, and energy level are all saved. Run `/sage <same topic>` to resume and the coach picks up from your last savepoint.

If you hard-close the terminal mid-session, your previous sessions are safe (already committed), but the current session's final state may be partially lost. Run `/resume` from the same directory to reopen the conversation where you left off, or run `/sage <topic>` to start a fresh session from the last completed checkpoint.
</details>

<details>
<summary><strong>How does spaced repetition work?</strong></summary>

Sage uses the SM-2 algorithm (the same one behind Anki). As you learn concepts, the coach creates flashcards (called **cards** in Sage) in `cards.md`. An SRS engine schedules reviews at increasing intervals based on how well you recall each card (graded 0–5). When you resume a session, overdue reviews are handled before new material. You don't need to manage any of this — the coach handles scheduling and grading during normal conversation.
</details>

<details>
<summary><strong>How does fact-checking work?</strong></summary>

A dedicated verification gate subagent checks every factual claim, code example, API signature, and card answer against current documentation before presenting it to you. This runs automatically at multiple points: before the learning plan is finalized, before each new concept is introduced, and before cards are saved. Wrong cards are especially dangerous because spaced repetition would cement the error — so all cards are verified before they're persisted.
</details>

<details>
<summary><strong>What if the coach gets something wrong?</strong></summary>

Tell the coach — it will immediately correct the material (cards, references, anything affected), explain what it got wrong, and log the mistake. More importantly, it generates a behavioral rule from the error so it doesn't make the same mistake in future sessions. These rules persist across sessions and are automatically loaded on resume.
</details>

<details>
<summary><strong>What if I'm stuck and not making progress?</strong></summary>

Sage has a built-in plateau detector. When it notices you're repeatedly struggling with the same concepts (wrong mental model, fragile recall, application gaps), it automatically switches teaching strategies — from teach-back exercises to interleaved application scenarios to interactive HTML demos — rather than drilling the same way harder.
</details>

<details>
<summary><strong>Can I look at or edit the learning files directly?</strong></summary>

Yes, all artifacts are human-readable markdown and JSON. You can read `plan.md` to see your full learning path, `knowledge-map.md` for a visual overview of concept mastery, `cards.md` for your cards, and `journal/` for session-by-session notes. Editing them directly isn't recommended — the coach validates artifact formats on session start and can fix minor issues, but manual edits that change the structure may cause problems.
</details>

<details>
<summary><strong>What are capstone projects?</strong></summary>

Once you've built enough mastery in a topic (demonstrated through retrieval practice, not just exposure), the coach designs a portfolio-worthy project tailored to what you've learned. You don't need to ask — the coach offers it when you're ready. These are meant to consolidate your knowledge into something you can show, not just another exercise.
</details>

<details>
<summary><strong>How do I get a reference doc for a concept?</strong></summary>

Ask the coach during a session — something like "can we create a reference doc for X?" The coach delegates to a specialist that produces a standalone deep-dive with worked examples, diagrams, tradeoff tables, and self-test questions, all cross-referenced to your cards and knowledge map. The coach may also generate reference docs on its own after sessions where a concept was deeply explored.
</details>

## Contributing

Open an issue for bugs or feature ideas. PRs welcome too.

## Requirements

- Python 3.8+
- Claude Code
- No pip packages required (stdlib only)

## License

MIT
