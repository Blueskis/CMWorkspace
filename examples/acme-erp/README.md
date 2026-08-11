# Worked Example — Acme ERP (fictional)

A complete run through the pipeline, used to demonstrate and regression-test it.
**The client, the RFP, and the knowledge-bank entries behind it are all invented.**

## Reproduce it

```bash
# Stage 3 — index the knowledge bank the plan draws on
python skills/cm-proposal-generator/scripts/index_kb.py \
    proposal-assets/knowledge-bank -o /tmp/kb_index.json

# Stage 4 — render the deck
python skills/cm-proposal-generator/scripts/render_html.py \
    examples/acme-erp/proposal_plan.json \
    proposal-assets/templates/html-generic \
    -o /tmp/acme/proposal.html

# Stage 5 — audit coverage and provenance
python skills/cm-proposal-generator/scripts/qa_deck.py \
    examples/acme-erp/rfp_brief.json \
    examples/acme-erp/proposal_plan.json \
    -o /tmp/acme/qa_report.md
```

Open `/tmp/acme/proposal.html` in a browser. Expected: 12 slides, QA passes with 8/8
requirements covered, 0 unattributed blocks, and 1 open `[GAP]`.

## What it demonstrates

**Slide count follows evaluation weight.** Approach is 35% of the score and gets 4 slides;
Team is 10% and gets 1. The plan is at the RFP's 12-slide limit exactly.

**Requirements drive the outline.** All 8 requirement IDs from the brief map to a section,
including `R8` — which appears nowhere in the RFP's scope schedule and was extracted from
the evaluation criteria, marked `confidence: inferred`, and flagged as a clarification
question.

**Provenance is visible.** Every slide footer lists the knowledge-bank entry IDs its
content came from. Nothing on any slide lacks either sources or a `[GAP]`.

**Gaps are honest, and shaped to the real problem:**
- *Commercials* — the fee table's **structure** is sourced from the bank while the
  **numbers** are a gap, because v0.1 does not price. The gap note names the mandatory
  requirement (`R7`) this leaves exposed. Two blocks on one placeholder, so the structure
  still renders rather than the gap swallowing the slide.
- *Team* — role profiles come from the bank; the names do not. Each unstaffed slot is
  flagged amber rather than filled with a plausible-looking name.

**Clearance rules are live.** The case study's source entry is `clearance: anonymised` and
`metrics_verified: false` — so the client cannot be named and the 87% figure cannot ship
until verified. Both are flagged in the KB index and noted in the slide's speaker notes.

## Note on the deck's content

The prose reads as though written for Acme because Stage 3 adapts bank entries to the
client's language and situation — that adaptation is the intended behaviour. The
underlying claims still trace to specific entry IDs, which is what makes the adaptation
auditable rather than invention.
