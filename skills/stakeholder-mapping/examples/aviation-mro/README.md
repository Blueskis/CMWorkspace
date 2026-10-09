# Worked example: Northwind MRO (fictional)

A fictional Singapore aircraft maintenance company rolling out S/4HANA Plant Maintenance. Names, quotes and organisations are invented.

| File | What it shows |
|---|---|
| `source_documents/` | Four interview notes, one Teams-style `.vtt` transcript (speaker-labelled), an org chart as `.png` and its transcription |
| `context.json` | Stage 1: industry, business model, and the thirteen org chart units |
| `extraction.json` | Stage 2 output: 19 groups, 8 named individuals, 25 formal and 13 informal ties, 20 evidence items. Every informal tie cites a quote. One tie rests partly on hearsay (I06, rated Low) |
| `sources.json` | The ingest manifest |
| `stakeholder_map.json` | Stage 3 output, with network metrics |
| `qa_report.md` | Stage 4: passes, with nine warnings that are the next interview agenda (groups whose sentiment nobody has evidenced) |
| `stakeholder_map.shared.json`, `pseudonym_key.json` | The same map pseudonymised for a shared screen, and the key that stays with the team |

What to look for in the viewer:

- **Rajendran** (a senior licensed engineer) has no formal authority over anyone and the highest informal reach on the map: four informal ties, into Quality, Technical Services, Line Maintenance and the Programme Office (as the person go-live waits on). That makes licensed engineers the real go-live gate.
- **Night shift** bypasses central planning. Planning only learns this "in the morning". The formal chain says Planning schedules the shift.
- **Licensed engineers** has Unknown sentiment and the highest influence on the map. That is the gap to close first.
- **Quality and Safety** carries a *Broker* label (full ring) because interviews show it talking to the regulator, the engineers and the Executive Committee. The network numbers on five interviews are too thin to confirm it, so the viewer shows no suggested role there. Labels you assign are kept; suggestions only appear when the numbers support them.

Rebuild:

```bash
cd examples/aviation-mro
python3 ../../scripts/build_map.py extraction.json context.json --sources sources.json -o stakeholder_map.json --as-of 2026-09-18
python3 ../../scripts/qa_map.py stakeholder_map.json --sources sources.json -o qa_report.md
python3 ../../scripts/sync_viewer_core.py   # refresh the example embedded in the viewer
```
