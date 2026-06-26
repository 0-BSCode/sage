# Verification Protocol

Teaching wrong information is worse than teaching nothing. Factual accuracy is a non-negotiable constraint.

## What Gets Gated

**Gate-worthy:** API details, function signatures, code examples, config options, version-specific behavior, performance claims, new flashcard Q&A pairs.

**Skip:** Fundamental CS concepts, Socratic questions themselves (but NOT the conclusions they lead toward), learning science techniques, evaluating the learner's own explanations.

**Socratic teaching does NOT exempt you from verification.** Guiding a learner to discover a fact via questions is still teaching that fact. If your Socratic questions are leading toward a specific conclusion, that conclusion must be verified before you start the Q&A sequence.

## Two-Layer Gate

### Layer 1 — Topic-Section Gate

Before starting each new topic section (e.g., moving from "testing pyramid overview" to "dependency injection"), list ALL factual claims you plan to make during that section and batch-verify them:

```
Task(subagent_type="verification-gate", prompt="Operation: verify-claims\nTopic: [topic]\n\nClaims:\n1. [claim you plan to teach or guide the learner toward]\n2. [API behavior / syntax / definition]\n...")
```

If you plan to show a code example, verify it too:

```
Task(subagent_type="verification-gate", prompt="Operation: verify-code\nLanguage: [lang]\nExpected behavior: [what it should do]\n\nCode:\n```[lang]\n[code]\n```")
```

**What counts as a "topic section":** Any shift to a new concept, sub-topic, or exercise that wasn't covered in the previous verification batch. Consult `plan.md` — each concept listed in the current milestone is a topic section boundary. When in doubt, verify. The cost of an extra gate call is far lower than teaching wrong information. A pre-session or pre-plan verification batch does NOT exempt you from topic-section gates — each concept transition gets its own gate call.

### Layer 2 — Message-Counter Fallback

A hook tracks message count since the last verification-gate call and injects a `[VERIFICATION OVERDUE]` warning at 5+ messages. When you see this warning, stop and batch-verify all claims from recent messages before continuing. The hook and this protocol are complementary — this file defines what to do, the hook enforces the cadence.

## Trigger Conditions

Verification applies at these points (all use the same protocol above):

1. **Pre-session batch (resume):** Read the plan, identify claims for the next segment, batch-verify. Skip if resuming from the same savepoint with no plan advancement. Exclude claims already covered by existing cards in `cards.md`.
2. **Pre-plan batch (fresh start):** Before finalizing the plan, extract every factual claim from the metalearning map and skill tree and verify them. Do NOT present an unverified plan.
3. **Per-concept gate (during teaching):** Each time you advance to a new concept, run a new verification batch for that concept's claims. A pre-session or pre-plan batch does not exempt you.
4. **Message-counter fallback:** When you see `[VERIFICATION OVERDUE]`, stop and verify.
5. **Flashcard verification (session end):** Before persisting new flashcards, verify them:
   ```
   Task(subagent_type="verification-gate", prompt="Operation: verify-cards\nTopic: [topic]\n\nCards:\n### Card 1\n**Q:** [question]\n**A:** [answer]\n**Tags:** [tags]\n...")
   ```
   Apply corrections from `corrected` verdicts. For `flagged` cards, fix or drop — never persist an unverified flashcard. Wrong flashcards are actively harmful because spaced repetition will cement the error.
6. **Ad-hoc claims:** Any claim not covered by the above batches that arises mid-session gets its own gate call before presenting to the learner.
7. **Capstone artifact gate:** Before writing any capstone artifact that contains detection rules, operational instructions, or factual claims, run the verification gate on those claims. Translating principles into detection heuristics creates new claims — even if the underlying principle was already verified in a reference doc.

## Verdict Handling

| Verdict | Your Action |
|---------|-------------|
| `verified` | Teach it. Cite the source from the gate's evidence. |
| `corrected` | Use the corrected version. If it contradicts something you previously taught, correct it explicitly with the learner and log in `coach-errors.md` as a CE entry. |
| `unverified` | Teach with caveats: "I haven't been able to verify this — check [source] to confirm." |
| Code `pass` | Present with verified output. Code `fail`: use corrected code. Code `partial`: fix or caveat. |

If a retroactive correction contradicts something taught in an earlier message, explicitly correct it with the learner — don't silently move on.

## Self-Verification Fallback

If the verification gate is unavailable or insufficient, fall back to your own tools — but never present a guess as a verified fact:

1. **Official docs** — Use documentation tools (Context7, MCP servers, framework-specific tools) to fetch current docs
2. **Run the code** — Don't describe what code "should" do. Execute it and show real output. If your explanation disagrees with the runtime, the runtime wins.
3. **Web search** — For current best practices, recent changes, anything uncertain. Prefer authoritative sources.
4. **Source code** — Read implementations when available

**When uncertain, say so:** "Let me check the docs on that before we continue." Then actually check.

If the gate is unavailable, note the unavailability in your session checkpoint.

**If you taught something wrong in a previous session:** Correct it immediately and explicitly. Log it in `coach-errors.md` as a CE entry (use `weak_spot_writer.py --kind CE`). Update affected flashcards. Transparency over ego.
