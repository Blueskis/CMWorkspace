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

They are written to contain what real project documents contain: an as-is that only exists in
interview notes, a to-be that only exists in the design, workarounds nobody documented, verbatim
resistance, two undesigned processes, an unresolved data ownership question, and a role whose
deliverable is quietly eliminated in a functional spec appendix.

## The output

`sample_cia_input.json` — 20 impacts across 5 L1 areas and 15 stakeholder groups, derived from
those six documents. Generate with:

```bash
pip install openpyxl
python3 ../scripts/generate_cia.py sample_cia_input.json -o "Project Horizon CIA v0.1.xlsx"
python3 ../scripts/generate_cia.py sample_cia_input.json --extended -o "Project Horizon CIA v0.1 (working).xlsx"
```

Rating spread on the template's 0–3 average: 3 Low, 4 Medium, 13 High. 5,938 training
person-hours (792 days).

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
- **Suppliers** appear as three rows across two tranches — the audience most often missing from
  an Ariba impact assessment, because they are not on the client's org chart.
- **Technology saturates.** Almost every row scores Technology 3, because the programme replaces
  the system outright. That is the template's anchor working correctly, and it means People and
  Process are carrying all the discrimination in the average.

## Using it as a template

Copy `sample_cia_input.json`, replace `meta` and `impacts`, and re-run the generator. Keep the
`source_documents` refs pointing at your own documents — the validator rejects any row citing a
document that is not declared.
