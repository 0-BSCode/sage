# Subagent Reference

You delegate to several subagents via the Task tool. Each agent has its own spec defining its behavior and boundaries — you only need to know when and how to call them.

**What you still own:** All pedagogical decisions, live SRS card grading during reviews, deciding artifact content (you provide session notes, agents handle formatting/writing), and reading artifact files mid-session when needed.

| Agent | Operation | When | Call Pattern |
|-------|-----------|------|-------------|
| artifact-clerk | `brief` | Session start (resume) | `Operation: brief\nPath: <slug>/learning/\nProject: <project-folder-name>` |
| artifact-clerk | `checkpoint` | Session end | `Operation: checkpoint\nPath: <slug>/learning/\nProject: <project-folder-name>\n\n[session notes]` |
| assessment-agent | `select-and-prepare` | Session start (warm-up), post-material checks | `Operation: select-and-prepare\nPath: <slug>/learning/\n\nSession context: [...]\nCount: 3\nMin mastery: developing` |
| assessment-agent | `generate` | After covering new material | `Operation: generate\nPath: <slug>/learning/\n\nTarget:\n- Concept: [...]\n- Difficulty: [1-5]\n- Question type: [free_recall|conceptual|application|analysis|transfer|reverse]` |
| assessment-agent | `evaluate` | After learner answers assessment | `Operation: evaluate\nPath: <slug>/learning/\n\nQuestion ID: q-N\nQuestion text: [...]\nExpected answer: [...]\nLearner response: [...]\nSession: [N]` |
| verification-gate | `verify-claims` | Session start (batch) + topic-section gate at each topic transition + message-counter fallback (5+ messages without a gate) + ad-hoc fallback for unplanned claims | `Operation: verify-claims\nTopic: [...]\n\nClaims:\n1. [...]` |
| verification-gate | `verify-code` | Before presenting code examples | `Operation: verify-code\nLanguage: [...]\nExpected behavior: [...]\n\nCode:\n[...]` |
| verification-gate | `verify-cards` | Before checkpoint (new cards only) | `Operation: verify-cards\nTopic: [...]\n\nCards:\n[card definitions]` |
| reference-clerk | `generate` | Learner requests, concept deeply explored, or after misconception | `Operation: generate\nPath: <slug>/\nConcept: <name>\nContext: [...]\n\nSource material:\n[...]` |
| reference-clerk | `update` | Corrections or additions to existing ref doc | `Operation: update\nPath: <slug>/\nConcept: <name>\nUpdates:\n- [...]` |
| reference-clerk | `audit` | Check coverage gaps | `Operation: audit\nPath: <slug>/` |
| demo-generator | `generate` | Learner confirms demo after `visual_demo` plateau mode | `Operation: generate\nPath: <slug>/learning/\nConcept: <name>\nMisconception: M[N] — [desc]\nCollision point: [...]\nLearner's wrong model: [...]\nCorrect model: [...]` |
| demo-generator | `update` | Demo needs adjustment after feedback | `Operation: update\nPath: <slug>/learning/\nMisconception: M[N]\nUpdates:\n- [...]` |
| capstone-architect | `propose` | Learner requests capstone, `/capstone` command, or coach judges mastery is sufficient | `Operation: propose\nPath: <slug>/learning/\nAudience: <audience string>` |
| capstone-architect | `specify` | After learner selects a project from proposals | `Operation: specify\nPath: <slug>/learning/\nSelected: <project title>\nAudience: <audience string>\n\nProject details:\n<full proposal text>` |

## Key Integration Notes

- **Clerk brief returns a compact summary** — use it to reconstruct context. Do NOT read artifact files yourself unless you need specific detail the brief doesn't cover.
- **Reference docs:** Do NOT write reference docs (`docs/references/ref-*.md`) directly. Always delegate to the reference-clerk agent. Writing inline bypasses quality gates and risks missing sources.
- **Assessment vs ad hoc questions:** Use the assessment agent for structured retrieval practice (tracked, calibrated). Use ad hoc Socratic questions for active teaching dialogue (conversational, not tracked). For ad-hoc factual retrieval questions, read the relevant card or knowledge-map entry to establish the expected answer before asking.
- **Proactive capstone readiness:** At session end, if the knowledge map shows >= 60% of concepts at `solid`/`mastered` and no `capstone.md` exists, suggest to the learner: "Your mastery profile looks strong enough for a capstone project — run `/capstone <topic> <your goal>` when you're ready."
- **Capstone propose→specify chain:** After calling `propose` and presenting proposals to the learner, if the learner selects or accepts a project, you MUST immediately call `specify` to persist it as `capstone.md`. Do not end the session with an accepted proposal but no written spec. The `propose` operation only returns text — it does not write any file.
