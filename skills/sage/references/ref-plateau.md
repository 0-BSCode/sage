# Plateau Response Protocol

The artifact clerk runs the plateau detector during the brief and includes the results in the `### Plateau Status` section. You do not need to run it yourself — read the brief output.

## When PLATEAU_LIKELY

1. Do NOT run another standard recall session.
2. Check `candidate_modes` from the detector output. The plateau detector uses the weak spot's **category** to choose the best response mode:

| Weak Spot Category | Preferred Mode | Session Design |
|---|---|---|
| `wrong-model` | `teach_back` | Learner explains the topic as if teaching. You play confused junior, ask "but why?" to probe depth. |
| `incomplete-model` | `targeted_redesign` | Design a NEW exercise exposing the missing dimension. The current card/drill missed it — repeating it is wasted time. |
| `fragile-recall` | `interleaved_application` | Mix with other concepts: new drill types + real scenario + explain-as-you-go. |
| `application-gap` | `application_scenario` | Present a realistic end-to-end problem requiring integration of multiple concepts. No compartmentalized recall. |
| any | `visual_demo` | See **Visual Demo Protocol** below. |

Follow the `recommended_mode` from the detector output. If it doesn't match the category-preferred mode, use the detector's recommendation (it has more context).

3. Tell the learner why: "I'm switching modes because [quote reason from detector]. Research shows this breaks plateaus better than more of the same."
4. SRS due cards still get reviewed but as a secondary activity, not the session focus.
5. Include `session_mode: plateau-response` in your session notes for the clerk.

## When NO_PLATEAU_DETECTED

Proceed with standard session (retrieval warm-up → SRS review → new material).

## Visual Demo Protocol

When `visual_demo` appears in `candidate_modes` (it appears whenever stale weak spots exist):

1. **Ask the learner first** — do NOT automatically generate a demo:
   > "Weak spot [WS-number] has persisted across [N] sessions despite [what's been tried]. Would an interactive demo help you see the relationship, or do you just need more practice?"

2. **If the learner says demo:**
   - Identify the collision point from `weak-spots.md`
   - Delegate to the demo-generator agent (see `ref-subagents.md`)
   - After the demo is generated, send it through the verification gate (`verify-demo` operation)
   - Present the demo to the learner
   - **Feedback loop:** After the learner has used the demo, ask them to re-answer the stuck question without looking at the demo. Grade their response. Update the weak spot status in your session notes: "demo shown [date], immediate re-test grade: [grade]"
   - The SRS will schedule a revisit next session based on the grade

3. **If the learner says more practice:**
   - Fall back to `targeted_redesign` or `teach_back` (whichever is appropriate)
   - Do not offer the demo again this session
