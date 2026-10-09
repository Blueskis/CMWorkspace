---
name: stakeholder-mapping-v0.1
description: Builds a stakeholder map of an organisation from interview notes, meeting transcripts and recordings, org charts and the organisation's industry and business model, covering both the formal structure (reporting lines, approvals, process hand-offs) and the informal one (who consults, trusts, influences, bypasses or gatekeeps whom). Produces a validated stakeholder_map.json, an evidence-linked QA report that doubles as the next interview agenda, and an interactive 3D viewer (a published Artifact, stakeholder-map.html) where a consultant can select, highlight and double-click stakeholder groups and ask open-ended questions answered only from the map's evidence. Use whenever a CM lead wants to understand who the stakeholders are and how they really work together, build or refresh a stakeholder map, find informal influencers, check whether the sponsor's support actually reaches the floor, or prepare stakeholder engagement — phrases like "stakeholder map", "who are the key influencers", "informal networks", "who do we need on side", "map the organisation from these interviews", or when someone hands over interview notes, transcripts and an org chart.
---

# Stakeholder Mapping

Turns a programme's own documents into a map of who exists and how they actually work together, with every relationship traced to evidence. The point is not the picture. It is that an informal tie ("night shift bypasses central planning") cannot appear without a quote behind it, a rating of how far to trust it, and a note when the quote is hearsay.

**Deliverables:** `stakeholder_map.json` (the master), `qa_report.md` (hard failures, then the warnings that become the next interview round), and the 3D viewer, which opens the map.

## What this produces, and what it does not

A **baseline hypothesis** for a validation conversation, built from whoever was interviewed. Silence is not absence: a group nobody mentioned is flagged, never invented. Sentiment is Unknown unless someone said something. Say this plainly when handing it over. A map presented as complete when it rests on five interviews loses credibility the first time a client points to a missing group.

It is also **sensitive data**. Read `reference/sensitivity.md` before the first interview is loaded, and do not put a map with real names on a shared screen.

## Files in this skill

| File | Use it for |
|---|---|
| `reference/extraction-guide.md` | Groups, formal and informal ties, attribution, confidence, ONA roles. **Read before extracting.** |
| `reference/relationship-taxonomy.md` | The eleven relationship types and how each is drawn. |
| `reference/industry_lenses.json` | Groups each industry usually has. Used by QA only, to warn about gaps. |
| `reference/sensitivity.md` | Names, pseudonymisation, what Ask sends to the model. **Read at intake.** |
| `schemas/context.schema.json`, `schemas/extraction.schema.json` | Contracts for Stage 1 and Stage 2 output. |
| `scripts/build_map.py` | Validates, de-duplicates people, merges re-runs, flags contradictions, computes network metrics, optionally pseudonymises. |
| `scripts/qa_map.py` | Audits a map: hard failures (exit 1) and warnings. |
| `scripts/sync_viewer_core.py` | Embeds the tested viewer logic and the example map into the single-file viewer. |
| `viewer/stakeholder-map.html` | The 3D viewer. Also `viewer/viewer-core.js`, its tested logic. |
| `examples/` | Four fictional worked examples, each with sources, extraction, map and QA report: `airline`, `healthcare`, `financial-services` (the three the viewer ships with) and `aviation-mro` (the fullest: a Teams-style transcript and an org chart image). See `examples/README.md`. |

Reused from the CIA skill, by path, not copied: `skills/change-impact-assessment/scripts/ingest_sources.py`, `transcribe_interview.py`, `reference/interview-evidence.md`, `reference/audio-workflow.md`.

## Process

```
notes / transcripts / recordings / org charts  +  organisation context
      INTAKE ─▶ INGEST ─▶ EXTRACT ─▶ BUILD ─▶ QA ─▶ VIEW
      context.json  ingested/  extraction.json  stakeholder_map.json  qa_report.md  viewer
```

Only EXTRACT is judgement. The rest is deterministic.

### Step 1: Intake (context.json)

Ask for the organisation's **industry and business model** ("aviation MRO: line and base maintenance for regional airlines under a regulator-approved maintenance organisation"), the programme, any known regulators, workforce shape (shifts, unions, licensed staff), and **the org chart**. List every org chart unit in `org_chart_units`; QA fails if any has no group. Take whatever interview material exists and do not wait for a complete set. If the user has no documents and only a narrative, say the result will be a structured hypothesis with nearly everything Unknown or Low confidence.

### Step 2: Ingest

```bash
python3 skills/change-impact-assessment/scripts/ingest_sources.py /path/to/sources -o ingested/
```

Correct `ingested/sources.json` by hand (types, titles, dates). **Open every PDF and image with the Read tool**: an org chart is a picture. For recordings, ask for the meeting platform's `.vtt` transcript first; otherwise follow `skills/change-impact-assessment/reference/audio-workflow.md`. An unattributed transcript cannot say who said it, so label speakers before quoting.

### Step 3: Extract (extraction.json)

Read `reference/extraction-guide.md`, then write `extraction.json` against `schemas/extraction.schema.json`: groups, named individuals worth naming, formal ties from documents, informal ties from interviews, and an evidence list of short verbatim quotes with source id, speaker **role**, and attribution. Rules that matter most:

- Every informal tie cites evidence. No exceptions.
- Sentiment is Unknown unless said. Never infer a person's stance from their seniority.
- Do not add a group because the industry lens expects one. QA reports it as a gap; the next interview confirms it.
- Keep ids stable across re-runs.

### Step 4: Build and QA

```bash
python3 skills/stakeholder-mapping/scripts/build_map.py extraction.json context.json \
    --sources ingested/sources.json -o stakeholder_map.json
python3 skills/stakeholder-mapping/scripts/qa_map.py stakeholder_map.json \
    --sources ingested/sources.json -o qa_report.md
```

`build_map.py` prints every problem and writes nothing on failure. Fix the extraction and re-run, at most three times; after that, hand over with the open failures listed. Hard failures: an org chart unit with no group, a dangling id, an informal tie without evidence, a leaked name in a pseudonymised map. Warnings are the agenda for the next round (groups with nothing behind their sentiment, expected industry groups not yet mentioned, hearsay holding up a confident tie, unresolved contradictions).

**To refresh after new interviews:** extract only the new material, then `build_map.py new_extraction.json context.json --merge stakeholder_map.json -o stakeholder_map.json`. A contradiction between rounds keeps both pieces of evidence, drops the item to Low confidence, and shows the newer value; resolve it in the room.

### Step 5: Share safely, then view

```bash
python3 skills/stakeholder-mapping/scripts/build_map.py extraction.json context.json \
    --pseudonymise --key-out pseudonym_key.json -o stakeholder_map.shared.json
python3 skills/stakeholder-mapping/scripts/qa_map.py stakeholder_map.shared.json --key pseudonym_key.json
```

Open the viewer artifact and **Load map** with the file you intend to show. The viewer never uploads it. It opens on a fictional example; the picker in the toolbar switches between Airline, Healthcare and Financial services.

## The viewer

| Do this | Result |
|---|---|
| Click a group | Selects it and lights its neighbours. Everything else dims. |
| Shift-click | Adds to the selection. Escape or click empty space clears it. |
| **Double-click** a group | Opens its detail panel: summary, key individuals (shown as satellites around the group), formal and informal ties, evidence quotes, open questions. A notes box exports with the map. |
| Filters | Formal or informal, sentiment, network role, level, tie type. |
| Ask | Free-form questions about the selected groups (or the whole map). Answers use only the map's evidence and cite it as `[E2]`; citations are links to the quote. If the evidence does not cover it, the answer says so and suggests what to ask next. |
| Flatten to 2D, Table | A plan view and a table, for slides and for screen readers. |

**Reading the picture.** Height is formal level (executive at the top, external parties on the outer ring at mid height). Position round the circle is business unit. Colour is sentiment. A ring marks a network role; a lighter ring is a suggestion from the numbers, not a label. A small amber dot means evidence disagrees. Dashed arcs are informal ties. The map is deliberately not a free-floating force graph: depth means something here, so the layout is stable between sessions.

Ask runs through the viewer's `sample` capability (the viewer's own Claude account). If it is unavailable the panel is hidden and the rest works. If three.js or WebGL is unavailable the page shows the table.

## Tests

```bash
python3 skills/stakeholder-mapping/tests/run_tests.py
```

Python (`test_build_map.py`, `test_qa_map.py`) and Node (`viewer.test.js`). Add a test before changing behaviour.

## What v0.1 does not do

Derive relationships from email, chat or calendar metadata; track change over time beyond `last_updated`; score engagement plans (use `network-position` for a prioritised engagement matrix from this map's people); or tell you the map is right. Informal ties are what people said, which is evidence, not proof.
