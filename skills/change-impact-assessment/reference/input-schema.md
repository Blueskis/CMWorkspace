# `cia_input.json` — Input Schema

The contract between extraction (your job) and rendering (`scripts/generate_cia.py`). Write this
file, run the script, get the client template populated. The script validates before rendering
and refuses to write on hard errors.

```json
{ "meta": { ... }, "impacts": [ { ... } ] }
```

Field names map onto the client template's own columns; the mapping is shown below.

## `meta`

| Field | Req | Notes |
|---|---|---|
| `program_name` | ✔ | e.g. "Project Horizon — SAP S/4HANA & Ariba Implementation" |
| `client` | ✔ | Organisation name |
| `solution_scope` | ✔ | One line: modules and geographies in scope |
| `assessment_owner` | ✔ | Person/role who owns this baseline |
| `version` | ✔ | e.g. "v0.1 — Baseline Draft (pre-validation)" |
| `assessment_date` | ✔ | `YYYY-MM-DD` |
| `go_live_date` | | `YYYY-MM-DD`. Drives the dated comms windows on the Comms Plan sheet. |
| `source_documents` | ✔ | Array. Every `ref` cited by an impact must exist here. |

Each `source_documents` entry: `ref` (short stable ID, e.g. `INT-01`), `type`, `title`, `date`
(optional), `author_or_participants` (optional).

`type` is free text; these are the conventional values, and the ones `ingest_sources.py` emits:
`Interview Notes` · `Interview Transcript` · `Interview Recording` · `Workshop Notes` ·
`Process Design` · `Functional Specification` · `Org Design` · `Solution Scope` · `Document` ·
`Presentation` · `Spreadsheet` · `Other`.

`scripts/ingest_sources.py` writes this array for you from a folder of client files — but it
guesses `type` from the file extension, so **correct it by hand** before generating. Only a
person can tell interview notes from a functional specification.

## `impacts[]` → template columns A–V

One row per **process change × stakeholder group**.

### Process taxonomy → columns A–H
| Field | Col | Req | Notes |
|---|---|---|---|
| `l1` | A | ✔ | Top-level process area, e.g. "Procure-to-Pay" |
| `l1_code` | B | | Numeric; rendered `00` |
| `l2` | C | ✔ | Process group, e.g. "Requisitioning" |
| `l2_code` | D | | Numeric |
| `l3` | E | ✔ | Process, e.g. "Raise Requisition" |
| `l3_code` | F | | Numeric |
| `l4` | G | | Activity/variant, e.g. "Catalogue Purchase — Occasional User". Warned if absent — the template's taxonomy goes to four levels. |
| `l4_code` | H | | Numeric |

Codes are numeric because the template formats those columns `00`. A non-numeric string is
written as text if you need one.

### People → columns I–J
| Field | Col | Req | Notes |
|---|---|---|---|
| `current_roles` | I | ✔ | The roles as they exist today, in the client's own language |
| `headcount_impacted` | J | | Integer |

### As-is / To-be → columns K–L
| Field | Col | Req | Notes |
|---|---|---|---|
| `as_is` | K | ✔ | Current state in business language. Include the workarounds. |
| `to_be` | L | ✔ | Target state in business language, not system language. |

### Impact assessment → columns M–S
| Field | Col | Req | Notes |
|---|---|---|---|
| `people_impact` | M | ✔ | What changes for the person, and why it scores what it scores |
| `score_people` | N | ✔ | Integer **0–3** |
| `process_impact` | O | ✔ | What changes in the flow |
| `score_process` | P | ✔ | Integer **0–3** |
| `tech_impact` | Q | ✔ | What changes in the system they touch |
| `score_technology` | R | ✔ | Integer **0–3** |
| — | S | | **Overall Impact (Average)** — a live Excel formula. Do not supply it. |

Anchors for 0–3 are on the template's `Change Impact Ratings` sheet and restated in
`rating-methodology.md`.

### Change initiative → columns T–V

Columns T and U are composed by the script from the structured fields below, so the template
holds a readable summary reference while the full detail lives on the Training Plan and Comms
Plan sheets.

**Training (→ column T)**

| Field | Req | Notes |
|---|---|---|
| `training_required` | ✔ | `Yes` · `No` |
| `training_type` | | `Classroom ILT` · `Virtual ILT` · `e-Learning` · `Job Aid` · `In-App Guidance` · `Floorwalking / Hypercare` · `Webinar` · `Not Required` |
| `training_module_ref` | | e.g. `TRN-P2P-04` |
| `training_duration_hrs` | | Number, per learner |
| `training_audience_size` | | Integer; defaults to `headcount_impacted` |
| `training_timing` | | e.g. `T-4 weeks` |

**Communications (→ column U)**

| Field | Req | Notes |
|---|---|---|
| `comms_required` | ✔ | `Yes` · `No` |
| `comms_timing` | | Wave names — `Awareness`, `Understanding`, `Readiness`, `Go-Live`, `Reinforcement`; multiple separated by `; ` |
| `comms_channel` | | Free text |
| `comms_owner` | | Named person or role — not "the change team" for High-rated impacts |
| `key_message` | | One sentence from the audience's point of view. Shown on the Comms Plan sheet. |
| `benefit_narrative` | | WIIFM for this group. Comms Plan sheet. |

**Others (→ column V)** — composed from:

| Field | Notes |
|---|---|
| `other_impacts` | Policy, control, compliance, data-ownership, engagement and commercial impacts. The template has no dimension for these, and this is where it intends them to go. |
| `mitigation_actions` | Prefixed `Mitigation:`. Required when `resistance_risk` is High. |
| `rating_override` / `rating_override_reason` | Appended as `RATING OVERRIDE → …` so the template's own arithmetic in column S stays untouched. |

### Governance — JSON-only by default, columns W–AD under `--extended`

| Field | Req | Notes |
|---|---|---|
| `impact_id` | ✔ | Unique, e.g. `CI-001`. Duplicates are a hard error. Also the key for the roll-up sheets. |
| `stakeholder_group` | ✔ | One group per row. The grouping axis for the heatmap and roll-ups. |
| `resistance_risk` | ✔ | `Low` · `Medium` · `High` — rated separately from impact magnitude |
| `change_champion` | | Business owner for this impact |
| `source_ref` | ✔ | e.g. `INT-03; FS-014`. Every ref must exist in `meta.source_documents`. **For transcripts, cite the timestamp**: `INT-04 @00:23:15` — a reviewer can jump straight to the audio and hear the tone, which is often the part being disputed. The validator strips `@…` before checking the ref. |
| `confidence` | ✔ | `High` · `Medium` · `Low` |
| `validation_status` | | `Draft` · `In Review` · `Validated` · `Baselined`. Defaults to `Draft`. |
| `notes` | | Open questions. Required when `confidence` is Low. |

## Validation

```bash
python3 scripts/generate_cia.py input.json --validate-only
```

**Hard errors** (block generation): missing required field, duplicate `impact_id`, a score
outside 0–3 or non-integer, a value outside an allowed enum, `source_ref` citing an undeclared
document, `rating_override` without a reason.

**Warnings** (render anyway, but work through them): Low confidence with no note, High
resistance with no mitigation, a High-rated impact with no champion or comms owner, training
required with no method or duration, comms required with no key message, a High-rated impact
with no training, a missing L4, an L1 with no High-rated impacts, and any source document
nothing was derived from.
