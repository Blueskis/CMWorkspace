# CM Proposal Section Library

The canonical sections a change-management proposal draws from. Stage 2 selects and
orders from this list — it is a library, not a mandatory sequence.

`kb_section` is the knowledge-bank folder Stage 3 retrieves from for that section.

## Core sections (include unless there's a reason not to)

### 1. Cover & Title
- **Purpose**: client name, engagement title, RFP reference number, submission date, our entity.
- **Slides**: 1
- **kb_section**: — (generated from `rfp_brief.json` metadata)
- **Watch for**: RFP reference numbers and legal entity names must be exact. Evaluators do check.

### 2. Executive Summary
- **Purpose**: our understanding of the ask, our answer, why us — in one slide.
- **Slides**: 1–2
- **kb_section**: `boilerplate`
- **Evidence needed**: nothing new — this is a synthesis of the rest of the deck, so **write it last** even though it sits near the front.
- **Watch for**: this is often the only slide a busy evaluator reads properly. It must stand alone.

### 3. Our Understanding of Your Situation
- **Purpose**: prove we read the RFP and understand the client's context, drivers, and constraints.
- **Slides**: 1–2
- **kb_section**: — (drawn from `rfp_brief.json`, not the bank)
- **Evidence needed**: the client's own stated drivers, in their language.
- **Watch for**: the single highest-signal section for "did they actually read this." Nothing generic. If we can name the specific system, the specific reorganisation, the specific regulatory deadline — do.

### 4. Change Management Approach / Methodology
- **Purpose**: how we'd run the change work — phases, activities, deliverables per phase.
- **Slides**: 2–4
- **kb_section**: `methodology`
- **Evidence needed**: the firm's own CM methodology entries; the diagnostic frameworks in this plugin cited as methods we'd apply.
- **Watch for**: usually the heaviest-weighted section in scoring. Size it to the evaluation criteria, not to how much methodology content the bank happens to hold.

### 5. Stakeholder Engagement & Communications
- **Purpose**: how we identify, segment, and engage the affected population.
- **Slides**: 1–3
- **kb_section**: `methodology`
- **Evidence needed**: engagement approach, comms planning artifacts, and the stakeholder mapping method the firm uses — network analysis to surface informal influencers is the usual one, and it needs a knowledge-bank entry to be citable.
- **Watch for**: frequently scored separately from the main approach — check the criteria before folding it into section 4.

### 6. Training & Capability Building
- **Purpose**: how we build the skills the change requires.
- **Slides**: 1–2
- **kb_section**: `methodology`
- **Evidence needed**: training needs analysis approach, delivery modalities, materials the firm has built before.
- **Include when**: the RFP mentions training, enablement, adoption, or system rollout. Skip for pure strategy/advisory briefs.

### 7. Governance, Measurement & Reporting
- **Purpose**: how the client sees progress and how we know it's working.
- **Slides**: 1–2
- **kb_section**: `methodology`
- **Evidence needed**: adoption metrics, reporting cadence, escalation routes. A recurring structured delivery-risk review at phase gates fits naturally here.
- **Watch for**: name real metrics, not "KPIs to be agreed." Clients read that as "we haven't thought about it."

### 8. Relevant Experience / Case Studies
- **Purpose**: proof we've done this before, in this sector or with this system.
- **Slides**: 1–3 (one per case study)
- **kb_section**: `case-studies`
- **Evidence needed**: KB case-study entries only.
- **Watch for**: **highest fabrication risk in the deck.** Client names, metrics, dates, and durations come from the KB entry verbatim or not at all. Check each case study's `clearance` field before using the client's name — some are anonymised for a reason.

### 9. Team
- **Purpose**: who would actually do the work.
- **Slides**: 1–2
- **kb_section**: `team`
- **Evidence needed**: KB bios. Named individuals must be genuinely available for the dates — flag as `[GAP]` if the practitioner hasn't confirmed staffing.
- **Watch for**: many RFPs require CVs in an annex and score on named-role experience.

### 10. Delivery Plan & Timeline
- **Purpose**: phases, milestones, and what happens in the first 30/60/90 days.
- **Slides**: 1–2
- **kb_section**: `methodology`
- **Watch for**: must reconcile with the RFP's own dates. A timeline that ends after the client's go-live is an automatic mark-down.

### 11. Commercials
- **Purpose**: fees, rate card, assumptions, what's excluded.
- **Slides**: 1–2
- **kb_section**: `commercials`
- **Watch for**: **v0.1 does not calculate pricing.** Populate the structure from the bank and leave the numbers as `[GAP]` for the practitioner. Never generate a fee figure.

### 12. Why Us
- **Purpose**: differentiators tied to this client's stated criteria.
- **Slides**: 1
- **kb_section**: `credentials`
- **Watch for**: only claim differentiators the bank supports. "Deep sector expertise" with nothing behind it is worse than omitting the slide.

## Conditional sections (include only when the RFP calls for them)

| Section | Include when the RFP mentions… | Slides | kb_section |
|---|---|---|---|
| Risk & Mitigation | risk register, delivery assurance, risk-sharing | 1 | `methodology` |
| Transition / Exit | incumbent handover, knowledge transfer, exit plan | 1 | `methodology` |
| Sustainability / ESG | social value, ESG, sustainability scoring | 1 | `credentials` |
| Diversity & Inclusion | D&I, EEO, supplier diversity | 1 | `credentials` |
| Data Protection & Security | GDPR, data handling, security clearance | 1 | `boilerplate` |
| Subcontractors / Partners | consortium bids, partner declarations | 1 | `boilerplate` |
| Assumptions & Dependencies | anything requiring client-side resourcing | 1 | `boilerplate` |
| Compliance Matrix | a numbered requirement schedule to respond against | 1–2 | — (generated from the requirement map) |

The compliance matrix is worth adding unprompted on any RFP with a numbered requirement
schedule — it's a direct, evaluator-friendly rendering of the Stage 5 coverage check.

## Ordering

Default order is the numbering above, with conditional sections slotted before Commercials.

Override it whenever the RFP prescribes a response structure — evaluators score against
their own schedule, and a deck they have to reorder in their heads scores worse regardless
of content quality.
