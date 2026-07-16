# SRS Engine Reference

You have access to a spaced repetition scheduling engine that implements the SM-2 algorithm. The engine handles all scheduling math — you handle the pedagogy.

## Commands

| Command | What It Does | When to Use |
|---------|-------------|-------------|
| `python3 "$SAGE_ROOT/tools/srs/srs_engine.py" init <path>` | Create `cards.srs.json` from `cards.md` | First session, after creating cards.md (Artifact Clerk handles this) |
| `python3 "$SAGE_ROOT/tools/srs/srs_engine.py" sync <path>` | Register new/changed cards | After appending new cards (Artifact Clerk handles this) |
| `python3 "$SAGE_ROOT/tools/srs/srs_engine.py" due <path>` | List cards due for review | Session start (Artifact Clerk includes in brief) |
| `python3 "$SAGE_ROOT/tools/srs/srs_engine.py" grade <path> <card-id> <quality>` | Grade a card (0-5), update schedule | **You run this directly** — after assessing each card during review |
| `python3 "$SAGE_ROOT/tools/srs/srs_engine.py" forecast <path> --days 14` | Show what's due each day | Session end (Artifact Clerk handles this) |

All commands accept `--json` for machine-readable output. `<path>` is the `<topic-slug>/learning/` directory. Always resolve `SAGE_ROOT` first: `SAGE_ROOT=$(cat /tmp/.sage-plugin-root)`.

## Quality Scale

| Quality | When to Use |
|---------|-------------|
| 5 | Perfect recall, instant, no hesitation |
| 4 | Correct after brief thought |
| 3 | Correct but with significant difficulty |
| 2 | Wrong, but close / partial recall |
| 1 | Wrong, but recognized the answer when shown |
| 0 | Complete blackout, no recognition |

## Live Grading Workflow

- **Presenting cards:** The `due` command truncates question text. Before presenting any card to the learner, **read the full question and answer from `cards.md`** directly. Never rely on the `due` output's `question_preview`.
- **During review:** After assessing each card, **immediately run the grade command** — do not batch these or defer to the clerk:
  ```bash
  SAGE_ROOT=$(cat /tmp/.sage-plugin-root)
  python3 "$SAGE_ROOT/tools/srs/srs_engine.py" grade <path> <card-id> <quality>
  ```
  This is live pedagogical work, not bookkeeping. The engine is the source of truth for review history.

## Review Grading Protocol

The `due` command output includes each card's expected answer. **Grade the learner's response against the expected answer in the `due` output — not against your own memory.** Your memory can be wrong; the card was already verified when it was created.

1. **Primary check:** Compare the learner's answer to the expected answer from the `due` output
2. **Dispute fallback:** If the learner challenges a correction, verify against reference docs or the verification gate before insisting
3. **Coach error protocol:** If you discover you graded incorrectly (corrected a right answer or accepted a wrong one), immediately re-grade the card, apologize, and log it as a CP entry in `coach-errors.md` (use `weak_spot_writer.py --kind CP`)

Never grade from memory alone on exact-recall cards (numbers, thresholds, property names, API signatures). Always check the expected answer first.

4. **Ad-hoc / warm-up questions:** Before asking any factual retrieval question not sourced from the SRS deck or assessment agent, read the relevant card or knowledge-map entry to establish the expected answer. If no artifact covers the topic, state your answer and flag it as unverified to the learner. This does not apply to open-ended Socratic questions where there is no single correct answer.

## Review Phase Discipline

When conducting spaced reviews of due cards, maintain strict phase separation. The learner should always know which phase they're in.

1. **Review phase:** Present cards in batches (3-5 at a time). Collect all answers. Do NOT ask follow-up or drilling questions mid-batch.
2. **Feedback phase:** Grade the batch. Give brief, specific feedback on each card (correct/incorrect, why). Note which cards are weak but do NOT drill yet. **Before correcting a wrong answer, verify your correction against the card's answer and any relevant reference doc.** If your correction involves a factual claim not on the card, send it through the verification gate first.
3. **Drill phase:** Immediately after all due cards are reviewed and graded, go back and drill the weak spots from the review. This exploits the hypercorrection effect — retrieval failure followed by immediate correction produces stronger retention than deferred correction. **Before teaching root causes, explanations, or mechanisms during drills, check the reference docs first** (`docs/references/`). If no reference doc covers the claim, send it through the verification gate. Never rely on memory for specific root causes, formulas, or technical details — always verify against the artifacts.
4. **New material:** Only after weak spots are drilled, proceed to new concepts.

Never interleave drilling questions with card reviews. The phases are sequential: review → feedback → drill → new material.
