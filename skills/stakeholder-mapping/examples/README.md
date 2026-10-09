# Examples

Four fictional organisations. Every name, quote and company is invented. Each folder holds `source_documents/` (what the consultant was given), `context.json`, `extraction.json` (Stage 2 output), `sources.json`, `stakeholder_map.json` and `qa_report.md`. `tests/test_examples.py` rebuilds all four on every run, requires QA to pass with no hard failures, and checks that every quoted line really appears in a source document.

| Example | Organisation and programme | Shape | In the viewer |
|---|---|---|---|
| `airline/` | Meridian Air, a regional full-service airline replacing its crew management and disruption recovery system | 21 groups, 8 named people, 27 formal and 14 informal ties, 18 evidence items | Yes |
| `healthcare/` | Harbourview Hospital rolling out an electronic medical record and e-prescribing | 20 groups, 8 named people, 24 formal and 12 informal ties, 17 evidence items | Yes |
| `financial-services/` | Crestline Bank replacing its loan origination platform | 19 groups, 8 named people, 24 formal and 12 informal ties, 17 evidence items | Yes |
| `aviation-mro/` | Northwind MRO rolling out S/4HANA Plant Maintenance. Has a speaker-labelled `.vtt` transcript and an org chart `.png`; see its own README | 19 groups, 8 named people | No |

## What to look for

**Airline.** The Operations Control Centre bypasses Crew Planning on bad nights, and Crew Planning only finds out from payroll exceptions. Licensed engineers both hand aircraft availability to the OCC formally and gate it informally. Crew Planning rings the pilots' association chairman before any roster rule goes in, yet the association has asked twice for a seat on the design group and not had one, and is shown as a low-confidence Skeptic because the ballot threat is hearsay. Neither union has been consulted.

**Healthcare.** Nothing is configured for Surgery without the Head of Surgery's say-so, and the evidence for his scepticism is hearsay, so he is Low confidence and the map says so. Ward nurse managers decide whether staff nurses adopt anything, and staff nurses ring their ward manager rather than the IT helpdesk, so the real first-line support route runs through the ward managers. Patient Safety's review queue is the slowest part of the build.

**Financial services.** Relationship managers bypass the loan operations queue by emailing the Head of Loan Operations, so a workaround sits outside any documented process. Technology holds the only release window and nobody can move it. The relationship managers are shown as Skeptic at Low confidence because the evidence is a senior RM's own words about himself plus one hearsay report. Compliance speaks to the regulator's supervisor informally before every filing.

## Rebuild any of them

```bash
cd examples/airline
python3 ../../scripts/build_map.py extraction.json context.json --sources sources.json -o stakeholder_map.json --as-of 2026-10-05
python3 ../../scripts/qa_map.py stakeholder_map.json --sources sources.json -o qa_report.md
python3 ../../scripts/sync_viewer_core.py   # refresh the samples embedded in the viewer
```

The QA warnings in each report are deliberate: groups whose sentiment nobody has evidenced yet. They are the agenda for the next interview round, not defects.
