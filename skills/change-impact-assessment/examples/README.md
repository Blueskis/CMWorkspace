# Worked Example — Project Horizon (SAP S/4HANA & Ariba)

A complete end-to-end example: the kind of documents a programme actually hands a CM lead, and
the assessment they produce in the client's CIA template.

## The inputs

`source_documents/` holds six fictional but realistic documents for an Ariba implementation at
"Meridian Industrial Group":

| Ref | Document |
|---|---|
| `INT-01` | Procurement Operations interview — as-is buying, sourcing, contracts |
| `INT-02` | Business requisitioner & approver workshop (22 attendees) |
| `SIG-01` | Signavio to-be process design — Procure-to-Pay |
| `SIG-02` | Signavio to-be process design — Source-to-Contract |
| `FS-01` | Functional spec — Guided Buying & Approval Framework |
| `FS-02` | Functional spec — Supplier Enablement & Invoice Automation |
| `INT-03` | **Teams meeting transcript (`.vtt`)** — Category Management as-is discovery, 5 speakers, verbatim |

They are written to contain what real project documents contain: an as-is that only exists in
interview notes, a to-be that only exists in the design, workarounds nobody documented, verbatim
resistance, two undesigned processes, an unresolved data ownership question, and a role whose
deliverable is quietly eliminated in a functional spec appendix.

`INT-03` is a genuine Teams-format `.vtt` and exists to demonstrate the transcript path. Run the
ingester over the folder to see it normalised into speaker turns with timestamps:

```bash
# from examples/
python3 ../scripts/ingest_sources.py source_documents -o /tmp/ingested
```

## The output

`sample_cia_input.json` — 21 impacts across 5 L1 areas and 15 stakeholder groups, derived from
those seven sources. Generate with:

```bash
pip install openpyxl
python3 ../scripts/generate_cia.py sample_cia_input.json -o "Project Horizon CIA v0.1.xlsx"
python3 ../scripts/generate_cia.py sample_cia_input.json --extended -o "Project Horizon CIA v0.1 (working).xlsx"
```

Rating spread on the template's 0–3 average: 3 Low, 5 Medium, 13 High. 5,942 training
person-hours (792 days).

## What the transcript demonstrates

`CI-013` and `CI-021` are both drawn from `INT-03`, and between them they show why a verbatim
transcript is different evidence from a written note:

- **Verbatim quotes carry the resistance.** *"That's a phone call. Always has been. That's — I
  mean, that's the job, isn't it. That's where I actually earn my money."* The self-interruption
  and the tag question are a person defending their professional identity, not their diary. A
  note would have recorded "second-round negotiation currently by phone".
- **The same speaker is not opposed.** *"Get the admin off me and I'll be the first one
  cheering."* Reading only the first quote would produce the wrong mitigation entirely.
- **Hearsay is not design.** A colleague says *"we've been told the new system does have a
  negotiation round"* — evidence that a message landed, not evidence about the system. It does
  not go anywhere near the `to_be` field.
- **`CI-021` exists only because of a live correction.** One Category Manager put annual events
  at "a hundred and forty, hundred and fifty"; a colleague immediately corrected it to "closer
  to two hundred" once unlogged three-quote exercises are counted. That exchange revealed a
  whole class of sourcing activity that is invisible in every reported number — a finding a
  curated note would have flattened into "~150 events/year" and lost.
- **Timestamps are the citation.** `INT-03 @00:01:08` lets a reviewer jump to the audio and hear
  the tone, which is usually the part being disputed.
- **The unanswered question is a finding.** Asked whether the new model has a waiver route for
  urgent sourcing, nobody in the room knew. Recorded as an open design gap, same pattern as
  `CI-018`.

## Things worth looking at in the example

- **The L4 split.** `Raise Requisition` (L3) breaks into four L4 activities — occasional user,
  high-frequency user, restricted non-catalogue category, and emergency purchasing — because it
  means four different things to four audiences. That split is what makes the register usable.
- **CI-005** is the impact/resistance split in miniature: Low overall (0.67 — no new system,
  minor process change) but High resistance, because the control closes a behaviour people
  described openly in a workshop without realising it was a control issue. The reason it scores
  Low is that the whole substance of the change sits in **Others**, where the template has no
  dimension for policy.
- **CI-001** carries a `rating_override` to High on volume — it scores 2.67 but lands on 3,620
  occasional users on day one. The override is written into Others so the template's own
  arithmetic in the Overall Impact column stays untouched.
- **CI-011** (AP team) is the highest-risk row: the business case assumes 70% effort reduction
  and redeployment, and the functional spec records that this has never been confirmed to the
  team in writing.
- **CI-016** is a single-person High — easy to miss in a register sorted by headcount.
- **CI-018** documents a process that does not exist. It is carried at Low confidence with the
  gap as the open question, which is how a CIA surfaces a design hole as a go-live risk.
- **CI-019 and CI-020** are deliberately Low, with People scored 0 — teams that are genuinely
  barely affected, included so they hear something rather than nothing.
- **`CI-021` is Low confidence on purpose.** Its own headline number is disputed on the record,
  so nothing in the row can be sized until the spend analysis settles it — that is what a
  baseline row looks like when the evidence is real but incomplete.
- **Suppliers** appear as three rows across two tranches — the audience most often missing from
  an Ariba impact assessment, because they are not on the client's org chart.
- **Technology saturates.** Almost every row scores Technology 3, because the programme replaces
  the system outright. That is the template's anchor working correctly, and it means People and
  Process are carrying all the discrimination in the average.

## Using it as a template

Copy `sample_cia_input.json`, replace `meta` and `impacts`, and re-run the generator. Keep the
`source_documents` refs pointing at your own documents — the validator rejects any row citing a
document that is not declared.
