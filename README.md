# Ultralearn

Evidence-based ultralearning coach for Claude Code. Uses spaced repetition, retrieval practice, Socratic questioning, and mastery tracking to help you deeply learn any topic.

## Install

```bash
claude plugin install ultralearn
```

## Usage

```
/ultralearn <topic>
```

Examples:
- `/ultralearn React hooks`
- `/ultralearn distributed systems`
- `/ultralearn statistics for ML`

### Fresh start

The coach asks 3-4 metalearning questions (your goals, prior knowledge, timeline), builds a structured plan, then immediately starts teaching. Every session produces:

- A learning plan with milestones
- Flashcards with spaced repetition scheduling (SM-2 algorithm)
- A knowledge map tracking concept mastery
- Weak spot tracking with categorized entries
- Session journals with savepoints for seamless resume

### Resuming

Run `/ultralearn <same topic>` again. The coach detects existing artifacts, loads your savepoint, handles overdue reviews first, then continues from where you stopped.

### Where artifacts are saved

Learning artifacts are created relative to your current working directory:

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

For cross-topic consolidation, start all your learning topics from the same parent directory. A shared `cross-refs/` directory at the parent level tracks concept overlaps across topics.

## How it works

The plugin has three layers:

**Skill** (`/ultralearn`) -- the coach. Runs the session, makes pedagogical decisions, interacts with you directly. Uses Socratic questioning, retrieval practice, and deliberate difficulty.

**Agents** (7 subagents) -- delegated specialists:
| Agent | Role |
|-------|------|
| artifact-clerk | File I/O, format compliance, cross-artifact validation |
| assessment-agent | Calibrated question generation and evaluation |
| verification-gate | Fact-checking gate for claims, code, and flashcards |
| reference-clerk | Standalone reference document generation |
| demo-generator | Interactive HTML demos for persistent misconceptions |
| capstone-architect | Portfolio-worthy capstone project design |
| learning-git | Artifact version control |

**MCP Tools** (38 tools) -- deterministic operations the agents call:
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

## Requirements

- Python 3.8+
- Claude Code
- No pip packages required (stdlib only)

## License

MIT
