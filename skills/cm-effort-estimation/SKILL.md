---
name: cm-effort-estimation-v1.0
description: Estimates change management effort and produces a priced schedule of deliverables from an RFP scope document (Word, PDF or pasted text) benchmarked against the firm's past project quotes. Reads scope drivers out of the RFP (impacted headcount, business units, countries, languages, waves, duration, training modules), maps the scope onto a standard CM deliverable taxonomy, derives day rates and effort-per-unit from an editable past-quotes table, applies complexity and scale multipliers, and outputs an invoice-style table of deliverables with individual pricing plus totals and assumptions. Use whenever a pursuit lead, bid manager or CM consultant wants to size, cost, price or quote change management work — phrases like "estimate the CM effort for this RFP", "how much should we quote", "price this scope", "build a fee schedule", "what did we charge last time", "cost this change management scope". Also opens an interactive browser estimator when the user wants to tune numbers themselves.
---

# CM Effort & Pricing Estimator

Turns an RFP scope into a defensible, priced schedule of CM deliverables, benchmarked on what the firm actually quoted before. Two ways to run it — do the analysis conversationally, or hand the user the interactive tool. Ask which they want only if it is genuinely unclear; if they pasted a scope, just estimate.

**Interactive tool**: `assets/cm-effort-estimator.html` — a single self-contained file. Opening it in a browser gives the pursuit lead the editable past-quotes table, the derived rate card and the priced schedule, with CSV and Markdown export. It parses .docx and .pdf in the browser; nothing is uploaded anywhere. Offer it when the user wants to iterate on numbers, hand the model to a colleague, or keep their quote history somewhere.

## The estimating model

Price per line = **quantity × effort per unit × day rate**, where quantity comes from scope drivers, effort per unit comes from past quotes (falling back to a standard assumption), and the day rate comes from past quotes indexed to today.

### Step 1 — Read the scope and pull the drivers

From the RFP, extract and state each of these. Where the document doesn't say, mark it as an assumption rather than staying silent — an unstated driver is the single biggest source of a wrong estimate.

| Driver | What it sizes |
|---|---|
| Impacted headcount | Training delivery, comms volume, readiness sampling |
| Business units / functions / process areas | Impact assessments, leadership workshops |
| Countries or sites | Coordination overhead on anything delivered locally |
| Languages | Localisation of collateral and courseware |
| Deployment waves | Readiness assessments, cutover support |
| Programme duration (months) | Workstream management, comms cadence |
| Training modules | Content development |
| Hypercare months | Post go-live support |
| Complexity (1–5) and client CM maturity | Global effort multipliers |

Also note what the RFP explicitly asks for. Anything named in the scope is a line item; the four that are almost always in scope even when unnamed are CM strategy, change impact assessment, stakeholder engagement and CM workstream management.

### Step 2 — Map to the deliverable taxonomy

| Deliverable | Unit | Standard effort/unit (days) |
|---|---|---|
| CM strategy & approach | document | 8 |
| Change impact assessment | business unit | 6 |
| Stakeholder analysis & engagement plan | plan | 5 |
| Change readiness assessment | wave | 4 |
| Communications strategy & plan | plan | 6 |
| Communications collateral | item | 1.5 |
| Leadership alignment workshops | workshop | 2.5 |
| Change agent network set-up & enablement | network | 6 |
| Training needs analysis | analysis | 6 |
| Training strategy & plan | plan | 5 |
| Training content development | module | 4 |
| Train-the-trainer delivery | session | 2 |
| End-user training delivery | session | 1 |
| Business readiness & cutover support | wave | 5 |
| Hypercare & adoption support | month | 10 |
| Adoption measurement & benefits tracking | cycle | 5 |
| Organisation & role design | design | 10 |
| CM lead & workstream management | month | 12 |

Default quantities: impact assessment = business units; readiness and cutover = waves; workshops = max(2, business units); courseware = training modules; train-the-trainer = one session per 12 trainers, sizing trainers at one per 50 users; end-user training = headcount ÷ 20 per session; collateral ≈ 1.5 items per month; management = duration in months.

**These standard effort figures are the fallback, not the answer.** Whenever the user has past quotes for a deliverable, the median of those quotes wins.

### Step 3 — Benchmark against past quotes

Ask for the past-quotes table if it hasn't been provided — one row per priced line from a previous proposal: project, year, industry, deliverable, quantity, days quoted, fee quoted. A CSV, a pasted table or a few remembered lines all work. Then, per deliverable:

- **Implied day rate** = fee ÷ days, indexed forward at ~3% per year from the quote year to the current year.
- **Effort per unit** = days ÷ quantity.
- Take the **median** across matching lines, not the mean — one outlier engagement shouldn't move the price.
- Deliverables with no history use the **blended median day rate** across all lines, and the standard effort above.

Always say which lines are benchmarked on real history and which are assumptions, with the sample count. A pursuit lead defending a number in a bid review needs to know which figures have evidence behind them.

### Step 4 — Apply multipliers

Effort per unit = standard or benchmarked effort × complexity × maturity × scale:

- **Complexity**: 1 → ×0.85, 2 → ×0.92, 3 → ×1.0, 4 → ×1.15, 5 → ×1.35
- **Client CM maturity**: low → ×1.1, medium → ×1.0, high → ×0.92
- **Multi-location** (impact assessment, readiness, change network, training delivery, cutover, hypercare): ×(1 + 0.07 per location beyond the first), capped at ×1.5
- **Multi-language** (collateral, courseware, training delivery): ×(1 + 0.12 per language beyond the first), capped at ×1.6

### Step 5 — Produce the priced schedule

Output an invoice-style table, one row per deliverable, in this shape:

| # | Deliverable | Unit | Qty | Days/unit | Effort (days) | Day rate | Amount |
|---|---|---|---|---|---|---|---|

Then, beneath it: professional fees subtotal, contingency (if any), pursuit discount (if any), travel and expenses, tax, and the total. Close with total person-days, the blended day rate and the implied average team size (effort ÷ (months × 21 working days)) — pursuit leads sanity-check a quote by team size faster than by fee.

Follow the table with the assumptions the price depends on: the drivers used, which were read from the RFP and which were assumed, the rate basis, and the standard exclusions (client-provided SMEs, venues and system access; translation and printing excluded unless priced).

## Judgement calls worth flagging to the user

- **End-user training delivery dominates large estimates.** At one session per 20 users, a 4,000-user programme is 200 sessions. Ask whether the client expects the bidder to deliver end-user training or only to enable client trainers — the difference can be a third of the fee.
- **A quote is not a cost model.** These figures are what was *charged*, so margin is already inside the day rate. Don't add margin on top unless the user says their history is cost-based.
- **Watch the FTE reality check.** If the implied team size is under 0.5 or over 8 FTE, the duration or the scope is probably wrong — raise it before presenting the number.
- **Currency and year mixing.** Past quotes in different currencies must be converted before they can be medianed; the tool assumes one currency throughout.

## Output modes

- **Conversational estimate** — the tables above, in the reply.
- **Interactive tool** — point the user at `assets/cm-effort-estimator.html`, or publish it as an artifact for them.
- **Client-ready** — on request, produce the schedule as a fee proposal section: deliverable, description, and fee, with effort and rates removed if the firm doesn't disclose them.
