# Sage

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](./LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org)

Turn Claude Code into a personal tutor that tracks what you've mastered, catches what's slipping, and circles back until it sticks.

## Features

- **Teaches through questions, not lectures** — the coach uses Socratic dialogue to make you reason through concepts instead of passively reading explanations
- **Spaced repetition** — an SM-2 scheduling engine tracks every concept and quizzes you at the right time, before you forget
- **Seamless resume** — stop anytime, pick up exactly where you left off. Overdue reviews are handled first automatically
- **Fact-checked teaching** — a verification gate checks claims, code examples, and flashcard answers against current sources before they reach you
- **Capstone projects** — once you've built enough mastery, the coach designs portfolio-worthy projects tailored to what you've learned

## See it in action

```
You:  /sage async programming
Sage: Before I design your plan, I need to understand your learning
      landscape. What's your current experience with async? What does
      success look like? What do you expect to be hardest?
You:  I've used async/await in JS and Python but never understood how
      it works underneath. I want to deeply understand the mental model.

      ● Verifying 12 claims against current documentation...
      ✓ All verified (1 correction applied: "resolved" → "fulfilled")

Sage: Here's your plan — 6 milestones, ~16 sessions.
      [plan with milestones, techniques, and session structure]

      Let's start. Before I explain anything — when you write
      await fetch(url), what do you think is actually happening
      with your code's execution?
You:  The await line gets offloaded from the call stack so it
      doesn't block...
Sage: Good instinct. But you said it's offloaded to "another stack."
      JS is single-threaded — it can't run code somewhere else.
      So if JS isn't doing the waiting... what is?
```

## Requirements

- Python 3.8+
- Claude Code
- No pip packages required (stdlib only)

## Install

```bash
/plugin marketplace add 0-BSCode/sage
/plugin install sage@sage
```

## Usage

### First session

```
/sage <topic>
```

The coach starts by asking about your goals, prior knowledge, and how much time you have. It builds a structured learning plan from your answers, then jumps straight into teaching. Each session ends with a checkpoint, so you can close the terminal and come back anytime.

Examples:
- `/sage React hooks`
- `/sage distributed systems`
- `/sage statistics for ML`

### Resuming

Run `/sage <same topic>` again. The coach detects your existing artifacts, loads your last savepoint, handles any overdue reviews, then continues from where you stopped.

If you hard-close the terminal mid-session, your previous sessions are safe (already checkpointed), but the current session's final state may be partially lost. Run `/resume` from the same directory to reopen the conversation where you left off, or run `/sage <topic>` to start a fresh session from the last completed checkpoint.

## Configuration

On first run, Sage asks you to pick a directory (your "learning root") where all topic directories are created. That choice is saved to `~/.config/sage/config.json`.

### Changing the learning root

To point Sage at a different directory later, use any of these (highest precedence first):

1. **Environment variable** — set `SAGE_LEARNING_ROOT=/new/path`. Overrides the config file for that session.
2. **Edit the config file** — open `~/.config/sage/config.json` and change `learning_root`:
   ```json
   { "learning_root": "/new/path", "version": 1 }
   ```
3. **Re-trigger the first-run prompt** — delete `~/.config/sage/config.json`. The next `/sage <topic>` run will ask you to pick a directory again.

Existing topic folders aren't moved automatically — if you want to keep past progress, move them into the new learning root yourself.

## What a session produces

Your learning progress lives in human-readable files you own — not in a chat history. Everything is structured markdown and JSON, created in your learning root:

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
    └── metrics/
        ├── dashboard.md
        └── history.json
└── docs/
    ├── references/
    └── demos/
```

All artifacts are saved at the end of each session via a checkpoint, so you never lose progress.

For cross-topic consolidation, start all your learning topics from the same parent directory. A shared `cross-refs/` directory at the parent level tracks concept overlaps across topics.

<details>
<summary><h2>How it works</h2></summary>

The plugin has two layers:

**Skill** (`/sage`) — the coach. Runs the session, makes pedagogical decisions, and interacts with you directly. Uses Socratic questioning, retrieval practice, and deliberate difficulty.

**Agents** (6 subagents) — delegated specialists:
| Agent | Role |
|-------|------|
| artifact-clerk | File I/O, format compliance, cross-artifact validation |
| assessment-agent | Calibrated question generation and evaluation |
| verification-gate | Fact-checking gate for claims, code, and flashcards |
| reference-clerk | Standalone reference document generation |
| demo-generator | Interactive HTML demos for persistent misconceptions |
| capstone-architect | Portfolio-worthy capstone project design |

These agents are backed by ~30 Python CLI tools handling SRS scheduling, card management, knowledge map updates, assessment, plateau detection, and coach metrics.

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

Everything stays on your machine — nothing is sent to a remote server. All learning data is plain markdown and JSON files you own. Each topic gets its own subdirectory under your configured learning root.
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

## License

[MIT](./LICENSE)
