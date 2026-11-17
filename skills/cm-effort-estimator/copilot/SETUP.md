# CM Effort Estimator in Microsoft 365 Copilot: setup

This builds the v0.5 estimator as a Copilot agent in **Agent Builder**. The agent reads RFPs and
turns your judgement into named adjustments. A skill script, running the same engine code as
the web estimator, does every calculation. The Excel workbook is both the saved record and a
fallback that runs the same rules as formulas.

```
Agent (instructions)  ──▶  Skill: cm-effort-estimator  ──▶  scripts/engine.js
        │                          (SKILL.md)                 same code as estimator.html
        ▼
Excel workbook  ◀── paste the TSV blocks the agent exports ── formula engine + audit log
```

Takes about 20 minutes.

## What you need

From `skills/cm-effort-estimator/copilot/` in this repo:

| File | Goes where |
|---|---|
| `agent/instructions.txt` | Agent Builder > Configure > Instructions |
| `agent/conversation-starters.md` | Agent Builder > Configure > Conversation starters |
| `dist/cm-effort-estimator-skill.zip` | Agent Builder > Configure > Skills > Add |
| `dist/knowledge/catalogue.csv` | Agent Builder > Configure > Knowledge |
| `dist/knowledge/drivers-and-levers.csv` | Agent Builder > Configure > Knowledge |
| `dist/knowledge/hours-library.csv` | Agent Builder > Configure > Knowledge |
| `dist/CM-Effort-Estimator.xlsx` | Your CoE SharePoint site, as the template people copy per pursuit |
| `dist/samples/*.txt` | Not uploaded. Used for the acceptance test below |

## Build the agent

1. In Copilot chat (m365.cloud.microsoft, or Teams), select **Agents & Skills**, then
   **New agent**, then switch to the **Configure** tab.
2. **Name:** `CM Effort Estimator`. **Description:** `Sizes change management and training
   pursuits in mandays from an RFP, and adjusts the estimate with your judgement.`
3. **Instructions:** paste the whole of `agent/instructions.txt` (about 4,900 characters; the
   limit is 8,000).
4. **Knowledge:** upload the three CSVs from `dist/knowledge/`. Turn **Web content off**:
   the agent needs nothing from the public web, and that keeps client RFP text inside the
   tenant.
5. **Skills:** expand **Skills**, select **Add**, and upload
   `dist/cm-effort-estimator-skill.zip`, the whole zip and not the SKILL.md alone. Check
   that the review shows `SKILL.md` and `scripts/engine.js`.
6. **Capabilities:** leave Code Interpreter and Image generator off. The skill runs its own
   script. Only turn Code Interpreter on if test 1 below fails.
7. **Conversation starters:** add the six from `agent/conversation-starters.md`.
8. Select **Create**, but don't share it yet: run the acceptance test first.

## Acceptance test (Try it tab)

Run these in order in one chat. The **reference numbers come from the engine itself**, so
the agent must reproduce them exactly. If it gives a different number, it computed the figure
itself rather than running the script, which breaks instruction rule 1: stop and report it.

| # | Type | Expect |
|---|---|---|
| 1 | `Run your selftest and tell me the result.` | Engine ok, version 0.5.1, sample 444.4 mandays. **If this fails, nothing below will work: see Troubleshooting.** |
| 2 | Attach or paste `dist/samples/public-authority-rfp.txt`, then: `Estimate this. Scope is global.` | **444.4 mandays**, average FTE 2.4 over 9 months, 40 deliverables, options 66.3. Read from the RFP: trainees per session 30, training modules 10, each with a quote. Listed as **not stated** with defaults: impacted people (500), waves (1) and others. "Change Sustenance Plan" appears under that name, flagged as an option. |
| 3 | `No dedicated change lead, three unions on the impact assessment, five onboarding waves.` | Numbered proposals, each with a rationale, confidence and delta: waves 1 → 5 **+124.5**, maturity medium → low **+39.5**, impact assessment → Complex **+19.5** (it may add more, each grounded in your words). Nothing accepted yet. |
| 4 | `The client team is friendly.` | No adjustments, and an offer to record a note. No invented uplift. |
| 5 | `Set training video hours to 30.` | Refused as admin configuration, with who owns it, plus a pursuit-level alternative. |
| 6 | `What's the price?` | Declines: effort only. |
| 7 | `Accept 1 and 3, reject 2.` | New total **588.4** (444.4 + 124.5 + 19.5), a log of two accepted entries, an `Adjustments!A6` TSV block, and an Estimate state block. |
| 8 | `Revert the waves change.` | Total **463.9**. Waves shown as Reverted in the log. |
| 9 | `How was the impact assessment sized?` | Quotes the engine's working: library hours at Complex, then mandays per business unit, then × quantity. |
| 10 | `Export for the workbook.` | Code blocks headed `Inputs!C5`, `Inputs!C18`, `Lines!E6`, `Custom lines!A6`, `Adjustments!A6`, `State!A6`. |
| 11 | Paste them into a copy of the workbook. | Summary **Current = 463.9**, matching the agent. |
| 12 | New chat: paste the `State!A6` text and `Resume this estimate.` | Confirms **463.9** before doing anything else. |
| 13 | New chat: `Estimate a 9-month S/4HANA training rollout for 2,000 users.` | At most three questions, or states every default it assumed. |
| 14 | Anywhere | British spelling, no em dashes, tables paste cleanly into Excel. |

If test 3 produces different deltas, check it proposed exactly those three levers. A
different set of proposals gives different deltas, and that's fine as long as every
number came from the script.

## Using the workbook

One copy per pursuit, stored with the bid.

1. Paste the agent's export blocks at the cells their headings name. Each block is
   tab-separated, so Excel splits it into columns.
2. **Adjustments**: when the agent proposes, paste the rows with Status = Proposed. Summary
   shows Baseline, Current and Preview side by side. Then set each row to Accepted or
   Rejected. Revert by setting Reverted; never delete a row, because the sheet is the
   audit trail.
3. The **Check** column refuses malformed rows and anything aimed at admin configuration.
   A refused row moves no number.
4. Without the agent, the workbook works on its own: fill Inputs and Lines by hand, and add
   your own adjustment rows.

## Troubleshooting

| Symptom | Likely cause | Do this |
|---|---|---|
| Selftest says the script can't run | The skill sandbox has no Node runtime in your tenant | Turn Code Interpreter on and retry. If it still fails, the agent falls back to the workbook: tell the CoE, and use the workbook for numbers. |
| No Skills section on Configure | Information Barriers or licensing | Ask IT. In the meantime, use the workbook with the agent for RFP reading and proposals (the fallback mode). |
| A number differs from the reference | The model calculated instead of running the script | Report it with the chat. Re-run with "use the skill's engine for every number". |
| Agent forgets the estimate mid-chat | Long chat context | Paste the last Estimate state back. |

## Changing the hours library or catalogue

There is **one source of truth**: the data in `skills/cm-effort-estimator/estimator.html`.
The skill script, knowledge CSVs and workbook are all generated from it:

```bash
python3 skills/cm-effort-estimator/copilot/build_copilot_pack.py
node --test skills/cm-effort-estimator/tests/judgement.test.js
python3 -m unittest discover -s skills/cm-effort-estimator/copilot/tests
```

Then re-upload the zip, the CSVs and the workbook template. Editing the workbook's admin
sheets directly is fine for a one-off what-if on one pursuit's copy, but those edits **do not
reach the agent**. Firm-wide changes go through the source and a rebuild, so the web
estimator, the agent and the workbook keep producing the same number. The parity tests fail
if they ever drift.
