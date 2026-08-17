# Publishing the Assessment to Airtable

Turning the CIA from a file people download into a workspace people work in. Same content,
same rating model, different medium — and Airtable's relational structure lets the
assessment do a couple of things the workbook could not.

## Two routes

### Route A — the Airtable connector (easiest, no tokens)

There is an official Airtable connector for Claude, carrying exactly the tools this needs:
`create_table`, `create_field`, `create_records_for_table`, `list_bases`.

Connect it once at **claude.ai → Settings → Connectors → Airtable**, and enable it for the
chat. After that, ask for the assessment to be published and it happens in conversation —
OAuth, no personal access token, nothing to paste.

Use this when you want it done now and interactively.

### Route B — `push_to_airtable.py` (repeatable, scriptable)

```bash
export AIRTABLE_PAT=pat_xxx
python3 scripts/push_to_airtable.py cia_input.json --check
python3 scripts/push_to_airtable.py cia_input.json --base-id appXXXX --dry-run
python3 scripts/push_to_airtable.py cia_input.json --base-id appXXXX --create
```

Standard library only. Use this when the sync needs to be repeatable, run from a machine
without the connector, or scripted into a refresh cycle.

**Never paste a token into a chat.** Keep it in the environment. The script reads
`AIRTABLE_PAT` and prints setup instructions rather than prompting for a secret.

#### Token scopes

Create a personal access token at **airtable.com/create/tokens** with:

| Scope | Why |
|---|---|
| `schema.bases:read` | Detect existing tables and field types |
| `schema.bases:write` | Create the two tables |
| `data.records:read` | Upsert matching |
| `data.records:write` | Write records |

Then **add the target base to the token's access list** — a token with the right scopes but
no bases attached returns 403, which is the single most common setup failure. The script
names that cause explicitly when it sees a 403.

## What gets created

Two linked tables, not one flat sheet:

| Table | Contents |
|---|---|
| **Sources** | One record per source document — ref, type, title, date, participants |
| **Change Impacts** | The register. 42 fields, one record per process change × stakeholder group, with a link field to Sources |

**The link is the point.** In the workbook, the Traceability sheet counted impacts per
document — one direction only. In Airtable, opening a source record shows every impact
derived from it, and opening an impact shows the documents behind it. When a business owner
challenges a row in validation, that is one click rather than a filter.

Transcript citations with timestamps (`INT-03 @00:01:08`) resolve to the document record;
the full citation stays in the `Source Ref` text field so the moment is not lost.

## Views replace sheets

The workbook needed separate Training Plan, Comms Plan, Heatmap and Traceability sheets
because a spreadsheet cannot show one dataset five ways. Airtable can, so these become views
over the single table — which also means they cannot drift out of step with the register.

| View | How |
|---|---|
| **Impact Register** | All records. Group by Stakeholder Group or L1 — that grouping *is* the heatmap. |
| **Training Plan** | Filter `Training Required = Yes`; group by Training Method |
| **Comms Plan** | Filter `Comms Required = Yes`; group by Comms Timing |
| **Open Questions** | Filter `Confidence = Low` OR `Notes` is not empty |
| **High Impact** | Filter `Rating = High`; sort by Anticipated Resistance |

Each takes a few seconds in the UI. The script prints the list after a successful sync.

## The one real constraint: formula fields

**Airtable's API cannot create formula fields.** So `Overall Impact` and `Rating` are created
as a number and a single-select, and the script writes the computed values.

To get the live recalculation the workbook had, convert them once in the UI:

```
Overall Impact  →  Formula
  ROUND(({People (0-3)} + {Process (0-3)} + {Technology (0-3)}) / 3, 2)

Rating  →  Formula
  IF({Overall Impact} = BLANK(), "",
  IF({Overall Impact} >= 2.5, "High",
  IF({Overall Impact} >= 1.5, "Medium",
  IF({Overall Impact} >= 0.5, "Low", "No / Minimal"))))
```

The script detects this on the next run and stops writing to those fields, leaving them to
Airtable. Do it once and re-scoring in a workshop updates the rating live, exactly as in the
workbook.

Note the band cut-offs in that formula are this skill's assumption, not the client
template's — see `rating-methodology.md`. If the client sets different cut-offs, change the
formula and `BANDS` in `generate_cia.py` together.

## Sync model

**The JSON stays the master.** Records upsert on `Impact ID`, so re-running after editing
`cia_input.json` updates in place rather than duplicating. That keeps the generator, the
workbook and the base in agreement.

The moment someone edits directly in Airtable, that stops being true. Decide early which is
authoritative:

- **JSON is master** — good while the baseline is being built and re-scored in bulk. Airtable
  is a read/review surface.
- **Airtable is master** — right once validation workshops start and business owners are
  editing their own rows. From that point, stop re-running the sync, or you will overwrite
  their work. Export back to JSON if you need the workbook again.

Say which one is in force when you hand the base over. This is the most likely way to lose
work, and it is a process decision rather than a technical one.

## What Airtable gains, and what it gives up

**Gains:** live and shareable without versioned files; real relationships between impacts and
sources; per-row comments so validation happens in the record rather than in email; filtered
views that cannot drift; interfaces for a steering-committee read-only view; and change
history per field, which matters when a rating is disputed later.

**Gives up:** the client's own CIA template. The workbook mirrors their format exactly, cell
for cell, and the `Change Impact Ratings` rubric sheet travels with it. Airtable is a
different artefact.

**So keep generating both.** Airtable for the working baseline and validation; the workbook
for the formal deliverable, the steering pack, and anything that goes to the client as a
record. They come from the same `cia_input.json`, so they cannot disagree — until someone
starts editing in Airtable, at which point see the sync model above.

## Confidentiality

A CIA in Airtable is a live link containing assessments of named roles — who loses
discretion, whose deliverable is being automated, which teams are expected to resist. That
is more sensitive than it looks once it is a URL rather than a file someone had to be sent.

Before sharing the base: set base permissions deliberately rather than leaving it open to the
workspace, avoid public share links, keep the `Notes / Open Questions` field out of any view
shared with the wider business (it holds the unvalidated inferences), and attribute quotes by
role rather than by name — same rule as the workbook.
