# Response Playbook — Deriving Training and Comms from an Impact Rating

Turns a rated impact into a defensible training and communication response. The
point of a change impact assessment is not the ratings; it's the intervention plan
the ratings justify. These are defaults — deviate freely, but record the reason in
`notes`.

## Training response by rating band

Bands are on the template's 0-3 average — High ≥ 2.50 · Medium 1.50–2.49 · Low 0.50–1.49 ·
No/Minimal < 0.50.

| Rating | Delivery method | Typical duration | Timing (relative to go-live) |
|---|---|---|---|
| **No / Minimal** | None. Awareness comms only, so the group knows it hasn't been forgotten | — | One touchpoint in Readiness |
| **Low** | None, or a one-page job aid if a new screen or document format is involved | — | Awareness comms at T-4 weeks |
| **Medium** | e-Learning or Job Aid; self-paced | 0.5 – 1.5 hrs | T-4 to T-2 weeks |
| **High** | Virtual ILT or Classroom ILT with hands-on exercises in a training client. Where the role itself is redefined — People scored 3 — add a practice environment, job aids and floorwalking/hypercare at go-live | 2 – 16 hrs across modules | T-6 to T-1 weeks; hypercare T-0 to T+4 weeks |

**High covers a wide range on a three-dimension average**, from "new system, same job" to "the
job is being redesigned". Use the People score to split it: People 3 means role change, and role
change needs curriculum plus hypercare, not a course.

**Timing principle:** training decays fast. Anything delivered more than ~6 weeks
before go-live needs a reinforcement touchpoint, and anything after go-live is
remediation, not enablement. State the trade-off when a programme's timeline forces
early delivery rather than silently scheduling it.

### Delivery method selection

Rating sets the *tier*; these factors set the *method* within it:

- **Large dispersed audience (500+, multi-geography)** → e-learning or VILT, never
  classroom. Classroom for 4,000 requisitioners is a schedule that will not survive
  contact with the business.
- **New judgement or decision-making required** → ILT/VILT with discussion. Judgement
  does not transfer through e-learning.
- **Occasional users** (a requisitioner who raises four requisitions a year) → in-app
  guidance and job aids, not courses. They will have forgotten a course by their
  next transaction.
- **Daily power users** (buyers, category managers, AP) → hands-on practice in a
  training client with their own data, plus floorwalking.
- **External audiences (suppliers)** → self-service registration guides, webinars,
  and a supplier enablement helpdesk. You cannot mandate attendance for people who
  do not work for the client, and supplier non-adoption is a top-three cause of
  Ariba benefit shortfall.

### Training effort

`Duration (hrs) × Audience (#) = Total Effort (person-hrs)`, rolled up by delivery method and
by audience on the **Training Plan** sheet. This is
the number that lets a CM lead answer the two questions they will actually be asked:
*how many hours of business time is this costing*, and *how many facilitator days do
we need to fund*. Give the business-time figure in days as well as hours — 12,000
person-hours means nothing; 1,500 working days means a budget conversation.

## Communication response by rating band

| Rating | Cadence | Channels | Sender |
|---|---|---|---|
| **No / Minimal** | 1 touchpoint | Team briefing | Line manager |
| **Low** | 1–2 touchpoints | Newsletter, intranet, team meeting cascade | Programme / CM team |
| **Medium** | 3–4 touchpoints across the timeline | Email, team briefing, manager cascade pack, FAQ | Functional lead |
| **High** | Sustained cadence from awareness to reinforcement | Town hall, line-manager cascade, drop-in sessions, targeted email, FAQ | Named business sponsor |
| **High + High resistance** | Continuous, two-way, with a feedback loop | Sponsor-led town hall, 1:1 or small-group sessions, change champion network, dedicated Q&A forum, post-go-live pulse survey | Executive sponsor + direct line manager |

Resistance, not just magnitude, drives the top tier. A High-impact / Low-resistance change needs
a good broadcast; a High-impact / High-resistance change needs a conversation.

**Sender matters more than channel.** Research and practice both point the same way:
people accept organisational rationale from a senior sponsor, and personal impact
from their own line manager. A programme mailbox is the least credible sender
available. For any High-rated impact, `comms_owner` should be a named person or role, never "the change team".

### Comms wave structure

Anchor `comms_timing` to go-live so the workbook stays valid when dates move:

| Wave | Window | Purpose | Message centre of gravity |
|---|---|---|---|
| **Awareness** | T-12 to T-8 weeks | Something is coming, and why | Business case, scope, timeline |
| **Understanding** | T-8 to T-4 weeks | What specifically changes for *you* | Role-level impact, benefits, WIIFM |
| **Readiness** | T-4 to T-1 weeks | What you must do, and when | Training enrolment, cutover actions, support routes |
| **Go-Live** | T-0 to T+2 weeks | Where to get help | Hypercare, floorwalkers, escalation |
| **Reinforcement** | T+2 to T+12 weeks | It's working, and it's permanent | Adoption metrics, early wins, correction of drift |

High-rated impacts should appear in at least three waves. A single email in
the Readiness wave is not a communication plan.

## Key messages

`key_message` is the sentence the affected person needs to hear, written from *their*
point of view. Rules:

- Lead with what changes **for them**, not what the programme is delivering.
  → "You'll raise requisitions in a guided shopping-style tool instead of emailing
    Procurement, and most orders will approve automatically within a day."
  → Not: "Phase 1 delivers Guided Buying capability to the requisitioner community."
- Name the loss honestly where there is one. Unacknowledged loss is the fastest route
  to resistance; naming it costs nothing and buys credibility.
- Pair every ask with a benefit that is real *for that audience*. "Reduced cycle time
  for the enterprise" is not a benefit to a person whose cycle just got longer — if
  a group genuinely loses out, say so and explain the trade-off rather than
  manufacturing an upside.
- One sentence, no acronyms, survives being read aloud.

## Resistance mitigation

For any impact with High anticipated resistance, `mitigation_actions` must name a
specific action with an owner — not "engage stakeholders". Options that work:

- **Involve the resistant group in the design or validation**, especially where the
  resistance is about lost discretion. Participation converts opposition to ownership
  more reliably than any volume of messaging.
- **Deploy a peer change champion** from within the group. A skeptic converted by a
  respected peer is worth more than any sponsor email.
- **Address the loss directly** in a two-way forum. Not a broadcast.
- **Provide a transition period or exception route** where the design allows.
- **Escalate to the sponsor** where the resistance is about a decision that is
  genuinely still open — and if it is closed, say that plainly instead of running an
  engagement process that implies otherwise.

Link this to the project's other change skills: `network-position` for *who* to
engage, `immunity-to-change` where a supportive individual still isn't moving, and
`critical-few-behaviours` where the register shows many impacts pointing at the same
handful of behaviours.

## Sanity checks on the response plan

- **Does anyone have an impossible week?** Roll up training hours by stakeholder
  group and check the Readiness window. A group carrying 30 hours of training in the
  fortnight before go-live will not complete it, and that is a schedule finding worth
  raising before it becomes a go-live risk.
- **Is every High-rated impact owned by a named person?** Both champion and comms owner.
- **Does any group have High impacts but no High-tier training?** Either the rating or
  the response is wrong.
- **Does any group appear only in the register and never in a comms wave?** A group with a
  No/Minimal rating still needs one touchpoint — silence reads as having been forgotten.
- **Are suppliers and other external audiences in the plan at all?**
