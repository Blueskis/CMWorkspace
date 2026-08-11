# Worked Example — Project Horizon (SAP S/4HANA & Ariba)

A complete end-to-end example: the kind of documents a programme actually hands a CM lead,
and the assessment they produce.

## The inputs

`source_documents/` holds six fictional but realistic documents for an Ariba implementation
at "Meridian Industrial Group":

| Ref | Document |
|---|---|
| `INT-01` | Procurement Operations interview — as-is buying, sourcing, contracts |
| `INT-02` | Business requisitioner & approver workshop (22 attendees) |
| `SIG-01` | Signavio to-be process design — Procure-to-Pay |
| `SIG-02` | Signavio to-be process design — Source-to-Contract |
| `FS-01` | Functional spec — Guided Buying & Approval Framework |
| `FS-02` | Functional spec — Supplier Enablement & Invoice Automation |

They are written to contain what real project documents contain: an as-is that only exists in
interview notes, a to-be that only exists in the design, workarounds nobody documented,
verbatim resistance, two undesigned processes, an unresolved data ownership question, and a
role whose deliverable is quietly eliminated in a functional spec appendix.

## The output

`sample_cia_input.json` — 20 impacts across 5 workstreams and 12 stakeholder groups, derived
from those six documents. Generate the workbook with:

```bash
pip install openpyxl
python3 ../scripts/generate_cia.py sample_cia_input.json -o "Project Horizon CIA v0.1.xlsx"
```

Rating spread: 2 Low, 2 Medium, 8 High, 8 Critical. 5,938 training person-hours (792 days).

## Things worth looking at in the example

- **CI-001** uses `rating_override` — it scores High (3.35) but hits 3,620 occasional users on
  day one, so the response tier is raised to Critical on volume, with the reason recorded.
- **CI-005** is the impact/resistance split in miniature: Medium impact, High resistance. The
  control is trivial to build and closes a behaviour people described openly in a workshop
  without realising it was a control issue.
- **CI-011** (AP team) is the highest-risk row: the business case assumes 70% effort reduction
  and redeployment, and the functional spec records that this has never been confirmed to the
  team in writing.
- **CI-016** is a single-person Critical — easy to miss in a register sorted by headcount.
- **CI-018** documents a process that does not exist. It is carried at Low confidence with the
  gap as the open question, which is how a CIA surfaces a design hole as a go-live risk.
- **CI-019** is deliberately Low: a team that is genuinely barely affected, included so they
  hear something rather than nothing.
- **Suppliers** appear as three separate rows across two tranches — the audience most often
  missing from an Ariba impact assessment.

## Using it as a template

Copy `sample_cia_input.json`, replace `meta` and `impacts`, and re-run the generator. Keep the
`source_documents` refs pointing at your own documents — the validator rejects any row citing a
document that is not declared.
