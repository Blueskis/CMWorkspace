# CM Proposal Section Library

How Stage 2 chooses, names, orders and sizes the proposal's sections.

Read the three rules first — they govern everything below. The catalogues are raw
material, not a template to fill in order.

---

## Rule 1 — Use the client's naming convention, not ours

**The client's terminology wins.** The canonical labels below are internal handles for
finding the right content — they are not slide titles.

> **Terminology warning.** Tender documents call the *bidder* "the Tenderer" and the
> *client* "the Authority", "the Tenderee", "the Purchaser" or similar. The naming rule
> here is about the **client's** words, not ours. Read any instruction about "the
> tenderer's naming" carefully — in a tender document that phrase means the bidder.

Naming precedence, highest first:

1. **The client's own name for the deliverable**, as written in the RFP. If it asks for a
   "Change Sustenance Plan," the section is called Change Sustenance Plan — not "Sustaining
   the Change." Evaluators score by locating their own requirements, and a deliverable we
   have renamed reads as one we have not answered.
2. **The firm's house name**, only where the client doesn't name the deliverable at all and
   the knowledge bank does.
3. **The canonical name** below, as a last resort.

Mirror the client's capitalisation and phrasing too. If the tender writes "Detailed
Stakeholder Engagement Plan," don't shorten it to "Stakeholder Engagement." Where the
client's term differs from our house term for the same thing, use theirs on the slide and
keep ours in the plan's `section_id` so retrieval still works.

## Rule 2 — Size sections by deliverable, not by guesswork

Most CM tenders publish no evaluation weights. Do **not** invent them.

- **Weights published** → size by weight, as the sizing table in Rule 3 describes.
- **No weights** → size by the deliverables the RFP actually asks for. A deliverable the
  RFP names explicitly earns at least one slide. A deliverable it describes in detail, or
  returns to in more than one clause, earns more. A deliverable it never mentions is
  probably not worth a slide even if it's in the canonical list.

Count the clauses. In a requirements-specification tender the emphasis is legible: the
sample CFS chapter spends fourteen sub-clauses on the Change Management Plan's contents
and one line on IP indemnity. That ratio is the sizing signal.

## Rule 3 — Adapt to the delivery methodology

**Read the RFP for whether the programme is Agile, Waterfall, or hybrid, and shape the CM
approach to match.** This is not cosmetic: it changes when change activity happens, what
it attaches to, and what the client will recognise as competent.

| | Agile / iterative | Waterfall / phase-gated |
|---|---|---|
| Change activity attaches to | Sprints, releases, increments | Phases and stage gates |
| Impact assessment | Rolling — re-baselined per release, since scope is not fixed up front | Once, comprehensively, before build |
| Training timing | Just-in-time per release; content versioned to keep pace | Concentrated before go-live |
| Comms rhythm | Continuous, tied to release cadence and ceremonies | Milestone-driven set pieces |
| Readiness measure | Per increment, cumulative | At the gate |
| Risk to name | Change fatigue from repeated small releases | A single large landing with no rehearsal |
| Vocabulary to mirror | Sprint, backlog, ceremony, Product Owner, user story, Definition of Done | Phase, gate, milestone, sign-off, baseline |

**Signals to read.** Agile: sprints, backlog, ceremonies, Product Owner, user stories,
Definition of Done, increments, releases, MVP. Waterfall: phases, stage gates, sign-off,
baselined requirements, UAT windows, a single go-live.

**Hybrid is common and worth naming.** Agile build inside a phase-gated governance
wrapper is the usual public sector shape. Say so explicitly — recognising it is itself a
credibility signal, and it means the CM plan needs both rhythms.

**If the RFP is silent, ask rather than assume**, and record it in `open_questions`.
Proposing a sprint-aligned change approach to a waterfall programme reads as a template
response.

---

## The CM deliverable sections

These ten are what a CM proposal is normally scored on. Rename per Rule 1, size per
Rule 2, shape per Rule 3.

### 1. Change Management Plan and Strategy
- **The spine of the response.** Overall approach, phasing, how change work aligns to the
  delivery plan.
- **kb_section**: `methodology` · **Typical slides**: 2–4
- Usually the most heavily specified deliverable in the RFP. Its sub-components (planning,
  evaluation, communications strategy, schedule, post-implementation review) are often
  enumerated — mirror that enumeration rather than substituting a generic phase diagram.

### 2. Team Structure and Governance
- Team composition, roles, reporting lines into the client, decision rights, escalation.
- **kb_section**: `team` · **Typical slides**: 1–2
- Check whether the RFP requires named individuals, CVs, approval rights over appointments,
  or continuity commitments — all common, all easy to miss. Flag `[GAP]` until staffing is
  genuinely confirmed.

### 3. Stakeholder Analysis and Engagement
- How stakeholders are identified, segmented, analysed, and engaged; engagement methods.
- **kb_section**: `methodology` · **Typical slides**: 1–3
- Where the RFP lists stakeholder groups, map your approach to *their* list explicitly.
  Generic segmentation against a client's own enumerated groups is a wasted opportunity.

### 4. Change Impact Assessment
- Method for identifying and rating impacts; what the output looks like; who validates it.
- **kb_section**: `methodology` · **Typical slides**: 1–2
- Under Agile this is rolling, not one-off (Rule 3). Say how it is re-baselined and how
  often.

### 5. Change Readiness Assessment
- How readiness is measured, when, against what threshold, and what happens if a group
  isn't ready.
- **kb_section**: `methodology` · **Typical slides**: 1
- The "what happens if not ready" half is usually missing from weak proposals. Include it.

### 6. Change Agent Network
- Identification, recruitment, training, tasking and sustaining of change agents,
  champions or superusers.
- **kb_section**: `methodology` · **Typical slides**: 1
- Frequently a named RFP deliverable with its own training requirement attached. Check.

### 7. Communications
- Channels, materials, cadence, approval workflow, and the change narrative itself.
- **kb_section**: `methodology` · **Typical slides**: 1–2
- Watch for approval lead times and client ownership of materials — both are common
  contractual conditions that belong in the response, not just the contract.

### 8. Training
- Needs analysis, curriculum, delivery modes, materials, trainers, logistics, evaluation.
- **kb_section**: `methodology` · **Typical slides**: 2–3
- Often the most operationally prescriptive part of a CM tender: class sizes, languages,
  venues, instructor qualifications, feedback thresholds, re-run obligations. Each is a
  discrete requirement. Do not compress them into "we will deliver role-based training."

### 9. User Adoption / Feedback and Evaluation Metrics
- Success measures, adoption tracking, pulse surveys, post-implementation review, reporting.
- **kb_section**: `methodology` · **Typical slides**: 1–2
- Name real measures with real cadences. "KPIs to be agreed" reads as unpreparedness.

### 10. Knowledge Transfer
- Handover to the client team, capability building, sustaining change after exit.
- **kb_section**: `methodology` · **Typical slides**: 1
- Increasingly a scored deliverable with a deadline attached (e.g. "within three months
  before the end of the warranty period"). Mirror the timing the RFP states.

## Deliverables outside the canonical ten

RFPs routinely name deliverables the list above doesn't cover — Transition Management
plans, Change Intervention plans, Change Risk Management plans, Change Sustenance Plans,
Orientation Programmes. **A named deliverable gets a home in the response whether or not
it appears above.** Either give it its own section or fold it into the nearest one and say
so. Never drop it because the canonical list doesn't have a slot.

## Framing sections

Not CM deliverables, but a proposal usually needs them.

| Section | Purpose | kb_section | Slides |
|---|---|---|---|
| Cover | Client legal name, engagement title, tender reference, date | — | 1 |
| Executive summary | The ask, the answer, why us — standalone. **Write last.** | `boilerplate` | 1–2 |
| Our understanding | Prove we read it: their drivers, constraints, context in their words | — (from the brief) | 1–2 |
| Relevant experience | Proof we've done this, in this sector or at this scale | `case-studies` | 1–3 |
| Delivery plan and timeline | Phasing, milestones, first 30/60/90 days | `methodology` | 1–2 |
| Commercials | Fee structure, assumptions, exclusions | `commercials` | 1–2 |
| Why us | Differentiators tied to this client's stated priorities | `credentials` | 1 |

Conditional, only when the RFP raises them: Risk & Mitigation · Transition/Exit ·
Sustainability/ESG or Social Value · Diversity & Inclusion · Data Protection & Security ·
Subcontractors/Partners · Assumptions & Dependencies · Compliance Matrix.

**Highest-risk section: Relevant experience.** Client names, metrics and dates come from
the knowledge-bank entry verbatim or not at all. Check `clearance` before naming any
client, and `metrics_verified` before quoting any number.

A **compliance matrix** is worth adding unprompted to any tender with a numbered
requirement schedule — it renders the Stage 5 coverage check in a form evaluators can score
directly.

---

## Ordering

1. **The RFP's prescribed structure wins outright**, where one exists. Evaluators score
   against their own schedule.
2. **Otherwise follow the RFP's own clause order** for the deliverable sections. A tender
   that discusses team before scope is telling you something about its priorities.
3. **Otherwise**: Cover → Executive summary → Our understanding → the CM deliverable
   sections in the canonical order above → Relevant experience → Team → Delivery plan →
   Commercials → Why us.

## Worked example — the CFS Chapter 8 sample

`examples/cfs-ch8/` names sixteen of its own deliverables. Rule 1 in practice:

| Canonical section | What this RFP calls it | Clause |
|---|---|---|
| CM Plan and Strategy | Change Management Strategy and Approach; Change Management Plan | 3.1.1, 3.1.2(a) |
| Team Structure and Governance | Change Management Team Structure | 3.1.2(b) |
| Stakeholder Analysis and Engagement | Detailed Stakeholder Engagement Plan | 3.1.2(c) |
| Change Impact Assessment | Change Impact Assessment | 3.1.2(g) |
| Change Readiness Assessment | Change Readiness Assessment | 3.1.2(f) |
| Change Agent Network | Change Agent Identification and Training | 3.1.2(a)(vi) |
| Communications | Comprehensive Communications Plan | 3.1.2(d) |
| Training | User Training Plan and Materials | 3.1.2(k), 5 |
| Adoption / Evaluation Metrics | Success Measurement Framework | 3.1.2(l) |
| Knowledge Transfer | Handover plan | 3.1.2(m) |

Plus five it names that the canonical list doesn't carry — Transition Management plan
(3.1.2e), Change Intervention plan (3.1.2h), Change Risk Management plan (3.1.2i), Change
Sustenance Plan (4, optional scope), and Orientation Programme (6). Each needs a home.

It is an **Agile** programme — sprints, backlog, ceremonies, Product Owner, user stories,
Definition of Done all appear in clause 6.1.5–6.1.6, with no waterfall vocabulary anywhere.
Per Rule 3 the impact assessment is rolling, training is just-in-time per release, and the
proposal should use the tender's own Agile vocabulary.
