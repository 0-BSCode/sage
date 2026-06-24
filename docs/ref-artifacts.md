# Artifact Reference

## Artifact Table

Save all files under `<topic-slug>/learning/` relative to the working directory.

| Artifact | File | When |
|----------|------|------|
| **Learning Plan** | `plan.md` | After Phase 1 metalearning questions are answered |
| **Session Journal** | `journal/session-NN.md` | Written by clerk at the end of every session |
| **Knowledge Map** | `knowledge-map.md` | Create after first session, update each session |
| **Flashcards** | `cards.md` | Generate during/after covering new material |
| **Weak Spots** | `weak-spots.md` | Whenever learner demonstrates a weakness that needs drilling — wrong models, incomplete understanding, fragile recall, or application gaps |
| **Coach Error Log** | `coach-errors.md` | Whenever a COACH error occurs — content errors (coach taught something wrong) or process failures (coach violated a workflow discipline). Auto-created on first write. |
| **SRS Schedule** | `cards.srs.json` | Auto-managed by the SRS engine — do not edit manually |
| **Question Bank** | `questions.json` | Auto-managed by the Assessment Agent — do not edit manually |

## Deciding Where an Entry Belongs

Ask: "Is this a learner weakness or a coach error?"

- **Learner weakness (any category)** → `weak-spots.md` (kind `WS`, or `M` as shorthand for wrong-model)
- **Coach taught something wrong** → `coach-errors.md` (kind `CE`)
- **Coach violated workflow discipline** → `coach-errors.md` (kind `CP`)

A coach error is NOT a learner weakness. Never write coach-origin entries to `weak-spots.md`, and never let them contaminate the learner's weakness review. The `weak_spot_writer.py` script enforces this structurally — it refuses to write a CE/CP entry to `weak-spots.md` and refuses to write a WS entry to `coach-errors.md`.

## Weak Spot Categories

When logging a learner weakness, assign one of four categories:

| Category | When to assign |
|---|---|
| `wrong-model` | Learner states something factually incorrect |
| `incomplete-model` | Learner knows part of a concept but systematically misses a dimension |
| `fragile-recall` | Correct knowledge exists but retrieval is unreliable under pressure |
| `application-gap` | Learner understands the concept but defaults to wrong pattern when applying it |

Categories are mutable — a `wrong-model` can become `fragile-recall` after the factual correction sticks but retrieval remains inconsistent. Log category changes in the weak spot's History subsection.

## Coach Error Protocol

When a coach error occurs, three things are mandatory:

1. **Transparency** — tell the learner explicitly that the coach got it wrong, with the correction
2. **Artifact correction** — cards, references, and journal entries embedding the wrong content must be updated
3. **Log the entry** in `coach-errors.md` via `weak_spot_writer.py --kind CE` (or `--kind CP` for process failures)

## Flashcard Rules

- Flashcards require generation (no multiple choice)
- Every card must carry a `type:<X>` tag declaring the cognitive operation it tests
- Generate a deliberate mix across a session — don't generate only `type:fact` cards
- For any concept you are adding a second or later card to, pick a type that is *not* already on the knowledge-map row for that concept
- If you cannot articulate which of the seven operations your new card tests, do not generate it

### Card Type Taxonomy

| Type | Cognitive Operation | Example Prompt |
|------|-------------------|----------------|
| `type:fact` | Declarative recall | "What is X?" |
| `type:why` | Causal/mechanistic reasoning | "Why does X behave this way?" |
| `type:process` | Procedural sequencing | "Walk through the steps of X" |
| `type:discrimination` | Boundary between similar concepts | "When would you reach for X vs Y?" |
| `type:transfer` | Application in a novel context | "Here's a scenario you haven't seen — apply X" |
| `type:reverse` | Effect to cause | "Given this symptom/output, identify the concept or cause" |
| `type:error` | Debugging / flaw detection | "Here's a broken instance — what's wrong and why?" |

## General Rules

- Create `plan.md` before starting execution — it grounds the journey
- Never end a session without a journal entry (clerk writes `journal/session-NN.md`)
- Only promote a concept's status in the knowledge map based on demonstrated retrieval, not mere exposure
- Tell the learner what was recorded and where after each artifact update
