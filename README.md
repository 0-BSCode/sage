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

## Contributing

Open an issue for bugs or feature ideas. PRs welcome too.

## Good to know

Uses Opus with multiple subagents. Pro plan users may hit rate limits mid-session. Max plan recommended. Token consumption is tracked per session in your journal entries.

## Requirements

- Python 3.8+
- Claude Code
- No pip packages required (stdlib only)

## License

MIT
