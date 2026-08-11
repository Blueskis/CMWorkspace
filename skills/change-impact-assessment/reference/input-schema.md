# `cia_input.json` — Input Schema

The contract between extraction (your job) and rendering (`scripts/generate_cia.py`).
Write this file, run the script, get the workbook. The script validates before
rendering and refuses to write on hard errors.

```json
{
  "meta": { ... },
  "impacts": [ { ... }, ... ]
}
```

## `meta`

| Field | Req | Notes |
|---|---|---|
| `program_name` | ✔ | e.g. "Project Horizon — SAP S/4HANA & Ariba Implementation" |
| `client` | ✔ | Organisation name |
| `solution_scope` | ✔ | One line: modules and geographies in scope |
| `assessment_owner` | ✔ | Person/role who owns this baseline |
| `version` | ✔ | e.g. "v0.1 — Baseline Draft (pre-validation)" |
| `assessment_date` | ✔ | `YYYY-MM-DD` |
| `go_live_date` | | `YYYY-MM-DD`. Drives the T-minus wave labels on the Cover sheet. |
| `source_documents` | ✔ | Array — see below. Every `ref` cited by an impact must exist here. |

Each `source_documents` entry: `ref` (short stable ID, e.g. `INT-01`), `type`
(`Interview Notes` / `Workshop Notes` / `Process Design` / `Functional Specification`
/ `Org Design` / `Solution Scope` / `Other`), `title`, `date` (optional),
`author_or_participants` (optional).

## `impacts[]`

One row per **process change × stakeholder group**.

### Identification
| Field | Req | Notes |
|---|---|---|
| `impact_id` | ✔ | Unique, e.g. `CI-001`. Duplicates are a hard error. |
| `workstream` | ✔ | L1, e.g. "Source-to-Contract" |
| `process_group` | ✔ | L2, e.g. "Sourcing Event Execution" |
| `process_name` | ✔ | L3, e.g. "Create and Publish RFQ" |
| `process_ref` | | Signavio/BPMN model ID for traceability |

### As-Is → To-Be
| Field | Req | Notes |
|---|---|---|
| `as_is_process` | ✔ | Business language. `"Not documented — see notes"` if genuinely unknown (then confidence must be Low). |
| `as_is_system` | | Current tool(s) |
| `to_be_process` | ✔ | Business language |
| `to_be_system` | | Target module, e.g. "SAP Ariba Guided Buying" |

### Characterisation
| Field | Req | Allowed values |
|---|---|---|
| `change_type` | ✔ | `Process` · `System / Technology` · `Policy & Control` · `Role & Organisation` · `Data & Reporting` · `Ways of Working` |
| `change_nature` | ✔ | `New` · `Modified` · `Eliminated` · `Automated` · `Reassigned` |

### Who is impacted
| Field | Req | Notes |
|---|---|---|
| `stakeholder_group` | ✔ | One group per row |
| `impacted_roles` | | Specific roles/personas |
| `geography` | | Entity/region, or "Global" |
| `headcount_impacted` | | Integer |

### Scoring — all required, integers 1–5 (see `rating-methodology.md`)
`score_people`, `score_process`, `score_technology`, `score_policy`, `score_data`

Weighted score and rating band are **computed as live Excel formulas** — do not
supply them.

| Field | Req | Notes |
|---|---|---|
| `rating_override` | | `Low`/`Medium`/`High`/`Critical`. Use sparingly; requires a reason. |
| `rating_override_reason` | | Mandatory whenever `rating_override` is set. |

### Analysis
| Field | Req | Notes |
|---|---|---|
| `impact_rationale` | ✔ | Why these scores. Quote the source where you can. |
| `resistance_risk` | ✔ | `Low` · `Medium` · `High` |
| `benefit_narrative` | | WIIFM for this group |

### Training response
| Field | Req | Notes |
|---|---|---|
| `training_required` | ✔ | `Yes` · `No` |
| `training_type` | | `Classroom ILT` · `Virtual ILT` · `e-Learning` · `Job Aid` · `In-App Guidance` · `Floorwalking / Hypercare` · `Webinar` · `Not Required` |
| `training_module_ref` | | e.g. `TRN-P2P-04` |
| `training_duration_hrs` | | Number, per learner |
| `training_audience_size` | | Integer; defaults to `headcount_impacted` if omitted |
| `training_timing` | | e.g. `T-4 weeks` |

Total effort (`duration × audience`) is a live formula — do not supply it.

### Comms response
| Field | Req | Notes |
|---|---|---|
| `comms_required` | ✔ | `Yes` · `No` |
| `key_message` | | One sentence, from the audience's point of view |
| `comms_channel` | | Free text; multiple separated by `; ` |
| `comms_timing` | | Wave label, e.g. `Understanding (T-8 to T-4 wks)` |
| `comms_owner` | | Named person or role — not "the change team" for High/Critical |

### Ownership, governance, traceability
| Field | Req | Notes |
|---|---|---|
| `change_champion` | | Business owner for this impact |
| `mitigation_actions` | | Required when `resistance_risk` is High |
| `dependencies` | | Other impact IDs or programme dependencies |
| `source_ref` | ✔ | e.g. `INT-03; FS-014`. Every ref must exist in `meta.source_documents`. |
| `confidence` | ✔ | `High` · `Medium` · `Low` |
| `validation_status` | | `Draft` · `In Review` · `Validated` · `Baselined`. Defaults to `Draft`. |
| `notes` | | Open questions. Required when `confidence` is Low. |

## Validation

Run `python3 scripts/generate_cia.py input.json --validate-only` to check without
rendering.

**Hard errors** (block generation): missing required field, duplicate `impact_id`,
score outside 1–5 or non-integer, value outside an allowed enum, `source_ref` citing
an undeclared document, `rating_override` without a reason.

**Warnings** (render anyway, but report them to the user): Low confidence with no
note, High resistance with no mitigation, High/Critical impact with no change
champion, training required but no delivery method, workstream with no High or
Critical impacts, and any stakeholder group whose training hours in a single window
look unachievable.
