# Worked Example — Acme ERP (fictional)

A complete run through the pipeline, used to demonstrate and regression-test it.
**The client, the RFP, and the knowledge-bank entries behind it are all invented.**

## Reproduce it

```bash
# Stage 4 — index the knowledge bank the plan draws on
python skills/cm-proposal-generator/scripts/index_kb.py \
    proposal-assets/knowledge-bank -o /tmp/kb_index.json

# Stage 5 — build the deck
python skills/cm-proposal-generator/scripts/render_pptx.py \
    examples/acme-erp/proposal_plan.json \
    proposal-assets/templates/pptx-generic/pptx-generic.potx \
    -o /tmp/acme/proposal.pptx

# Stage 6 — audit the plan, then the file
python skills/cm-proposal-generator/scripts/qa_deck.py \
    examples/acme-erp/rfp_brief.json \
    examples/acme-erp/proposal_plan.json \
    -o /tmp/acme/qa_report.md

python skills/cm-proposal-generator/scripts/qa_pptx.py /tmp/acme/proposal.pptx \
    --original proposal-assets/templates/pptx-generic/pptx-generic.potx \
    -o /tmp/acme/qa_pptx.md
```

Expected: 12 slides; `qa_deck` passes with 7/7 slide-needing requirements covered, 0
unattributed blocks, 1 open `[GAP]`; `qa_pptx` passes with 0 package problems, 0 fidelity
failures, 0 overflow.

**The same plan renders to HTML with no edits**, which is the point of the shared
placeholder vocabulary:

```bash
python skills/cm-proposal-generator/scripts/render_html.py \
    examples/acme-erp/proposal_plan.json \
    proposal-assets/templates/html-generic -o /tmp/acme/proposal.html
```

## What it demonstrates

**Slide count follows evaluation weight.** Approach is 35% of the score and gets 4 slides;
Team is 10% and gets 1. The plan is at the RFP's 12-slide limit exactly.

**Requirements drive the outline, and `kind` decides what covering one means.** Seven of
the eight requirements need a slide and all seven map to a section — including `R8`, which
appears nowhere in the RFP's scope schedule, was extracted from the evaluation criteria,
marked `confidence: inferred`, and flagged as a clarification question. The eighth, `R6`
("responses must name the proposed engagement lead… CVs in Annex B"), is a
`submission-rule`: it constrains the document, so QA lists it as a pre-submission
checklist item rather than demanding a slide answer it.

**Provenance is visible.** Every slide footer lists the knowledge-bank entry IDs its
content came from. Nothing on any slide lacks either sources or a `[GAP]`.

**Template fidelity is provable.** `qa_pptx.py --original` confirms the master, layouts and
theme are byte-identical to the template and that no slide sets a font or literal colour.
The one exception is deliberate: `[GAP]` panels carry fixed amber, are named
`GAP-marker-*`, and are excluded from the drift scan — a review annotation has to stay
legible on any template, including one whose own accent is amber.

**Gaps are honest, and shaped to the real problem:**
- *Commercials* — the fee table's **structure** is sourced from the bank while the
  **numbers** are a gap, because the pipeline does not price. The gap note names the
  mandatory requirement (`R7`) this leaves exposed. Two blocks target one placeholder, and
  the renderer stacks them: the table renders in full with the gap panel beneath it, sized
  to its own content.
- *Team* — role profiles come from the bank; the names do not. Each unstaffed slot is
  flagged amber rather than filled with a plausible-looking name.

**Clearance rules are live.** The case study's source entry is `clearance: anonymised` and
`metrics_verified: false` — so the client cannot be named and the 87% figure cannot ship
until verified. Both are flagged in the KB index and noted in the slide's speaker notes.

## Note on the deck's content

The prose reads as though written for Acme because Stage 4 adapts bank entries to the
client's language and situation — that adaptation is the intended behaviour. The
underlying claims still trace to specific entry IDs, which is what makes the adaptation
auditable rather than invention.

## Note on the template

This example builds on `pptx-generic.potx`, the plain generated stand-in. It is **not** an
approved firm template and a deck built on it must not be presented as one. Everything
upstream of Stage 5 is unchanged when a real template replaces it.
