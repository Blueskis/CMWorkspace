# Extraction guide: from sources to extraction.json

The model's only job in this skill is Stage 2. Everything before it is ingestion and everything after is scripts. Read `skills/change-impact-assessment/reference/interview-evidence.md` first: attribution rules there (who said it decides whether it is testimony, claim, design intent or hearsay) apply unchanged.

## 1. Groups before people

A **group** is a set of people who share a role, a reporting line and a stake in the change, and who a consultant would engage together. Start from the org chart units, then add groups the chart cannot show: licensed or certified staff, shift supervisors across units, a union, a regulator, customers, the implementation partner. A group needs a tier (0 executive to 4 frontline, 5 external). If a unit on the org chart is not a group, `qa_map.py` fails the run, so either add it or list it under another group's `org_units`.

Name an **individual** only when what they do matters on its own: a sponsor, a person others consult, a gatekeeper, a broker between groups. Do not list everyone interviewed. Ties between individuals are drawn on the main view as ties between their groups, so naming a person never hides their influence.

## 2. Formal ties

Taken from documents: org charts, RACI, process models (BPMN lanes), governance terms of reference. Types: `reports_to`, `approves`, `hands_off_to`, `escalates_to`, `governs`. Cite the document as evidence (`attribution: document`). A formal tie asserted only in an interview ("I report to the COO") is testimony, not document, and says so.

## 3. Informal ties

Taken from what people say they actually do. Types: `consults`, `trusts`, `influences`, `bypasses`, `conflicts_with`, `gatekeeps`. Signals to listen for:

| Signal in an interview | Likely tie |
|---|---|
| "I ring X before I ..." / "we check with X first" | `consults` |
| "Nothing goes ahead without X nodding" | `influences` or `gatekeeps` |
| "We just do it ourselves and tell them after" | `bypasses` |
| "They don't understand how it works on the floor" | `conflicts_with` (if repeated across sources) |
| "If X says it's fine, everyone uses it" | `influences` |

**Every informal tie needs at least one evidence item.** The build fails without one.

## 4. Attribution and confidence

| Attribution | Use when |
|---|---|
| `testimony` | The speaker did or saw it themselves |
| `claim` | The speaker asserts it about others, first-hand knowledge uncertain |
| `hearsay` | "I heard that ..." |
| `document` | A written source |

Confidence on a tie: **High** = two independent sources or first-hand testimony from a party to the tie. **Medium** = one first-hand source. **Low** = claim or hearsay only. `qa_map.py` warns when a High tie rests on hearsay alone.

## 5. Sentiment, influence, ONA role

- **Sentiment**: Advocate, Neutral, Skeptic, or **Unknown**. Prefer Unknown to a guess. Unknown groups become the next interview agenda.
- **Influence / interest** (1 to 5): influence = ability to help or block the change, formally or informally. Interest = how much the change affects them.
- **ONA role** (optional label): Central Connector, Broker, Peripheral, Energiser, De-energiser. Your label is kept as written. `build_map.py` computes betweenness and degree and suggests a role where the numbers say so; the viewer shows suggestions as a lighter ring. Disagreement between your label and the suggestion is worth a look.

## 6. Industry lens

`reference/industry_lenses.json` lists groups each kind of organisation usually has (an aviation MRO: regulator, licensed engineers, quality and safety, shift supervisors, union). It is used only by QA to warn "expected but not evidenced". Never add a group because the lens lists it; ask about it in the next interview.

## 7. Open questions

Each group can carry `open_questions`: what the evidence cannot yet answer. Write them as questions you would ask in the room. They are shown on double-click.

## 8. Re-runs

Keep ids stable. Re-run with `build_map.py --merge previous_map.json`: new evidence is added to existing items, only touched items get a new `last_updated`, and a changed sentiment is recorded as a conflict (both evidence items kept, confidence Low, the newer value shown) instead of silently overwriting.
