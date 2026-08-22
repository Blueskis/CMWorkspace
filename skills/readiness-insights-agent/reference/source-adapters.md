# Source adapters

One JSON file per feedback source, telling `ingest_feedback.py` how to read it. The
mapping is written down rather than inferred because it is a set of judgement calls — which
readiness dimension an item measures, which scale it uses, which column identifies a
segment — and those calls need to be visible and re-runnable, not buried in a one-off
parse.

## Format

```json
{
  "source_id": "S2",
  "label": "Training evaluation - wave 2",
  "instrument": "training_evaluation",
  "document": "../inputs/training_eval_wave2.csv",
  "wave": "W2",
  "collected_from": "2026-07-20",
  "collected_to": "2026-07-31",
  "population": 210,
  "date_column": "submitted",
  "respondent_column": "response_id",
  "segment_columns": { "group": "department", "site": "location", "role": "role" },
  "default_scale": { "min": 1, "max": 5 },
  "quant": [
    { "column": "q_can_apply", "dimension": "skills",
      "question": "I can apply what I learned in my job" },
    { "column": "q_extra_workload", "dimension": "capacity",
      "question": "How much extra workload do you expect?",
      "scale": { "min": 1, "max": 7, "reverse": true } }
  ],
  "verbatim": [
    { "column": "c_what_was_missing", "dimension": "skills",
      "question": "What was missing from the session?" }
  ]
}
```

| Field | Notes |
|---|---|
| `source_id` | `S1`, `S2`, … Unique across the run; signal IDs are built from it. |
| `document` | Resolved relative to the adapter file first, then as given. |
| `wave` | Two sources sharing a wave label are one measurement round. Deltas are computed between waves in collection-date order, so this is what makes trend possible. |
| `population` | People eligible, not responses. Drives the response rate, which Stage 5 uses to force honest confidence ratings. Omit it rather than invent it — an omitted rate is silence, an invented one is a lie with a decimal point. |
| `segment_columns` | Maps output keys to source columns. **`group` is the rollup key** and its values must match the segment names in `programme.json` exactly. Extra keys (`site`, `role`, `tenure`, `shift`) are kept on each signal for later cuts. |
| `default_scale` | Applied to any quant item without its own `scale`. |
| `min_verbatim_chars` | Default 3. Raise it to drop "n/a" and "-" noise. |

## Getting the segment names right

`group` values are matched literally against `programme.json` segment names. "Field Ops",
"Field Operations" and "field ops" are three different segments to the matrix, which
silently splits a base and turns two amber cells into two thin ones. Check the distinct
values before ingesting:

```bash
python -c "import csv,sys;print(sorted({r[sys.argv[2]] for r in csv.DictReader(open(sys.argv[1]))}))" \
    inputs/training_eval_wave2.csv department
```

Where an instrument uses its own vocabulary, normalise it in the source file or add a
mapping column — do not rename the programme's segments to match the survey's.

## Working with what you are actually given

**A spreadsheet with merged headers and a chart on top.** Use the `xlsx` skill to extract
the response rows to a clean CSV first, then adapt that. Keep the original in `inputs/`.

**A vendor PDF report with the numbers already aggregated.** You cannot ingest it — there
are no rows. Either get the raw export, or record the aggregate as programme context and
say in the brief which figures are unverifiable at row level. Do not synthesise rows that
would produce the reported mean.

**Free-text with names in it.** Verbatims carry `respondent_ref`, never names or emails.
If comments name individuals ("Dave in scheduling never replies"), keep the text but flag
it — quoting it into a brief that reaches a steerco is a different decision from analysing
it, and it is the practitioner's to make.

**Two instruments asking the same question differently.** Map both to the dimension and let
the matrix pool them; the pooled cell is more robust than either alone. If the wordings
imply genuinely different things, that is two items, and the difference is often itself the
finding.

**One instrument, one big free-text box, no scores.** Adapt it as verbatim-only. The
segment stays out of the quantitative matrix and shows as no-data there, which is correct:
themes are evidence about what people said, not a substitute for a score nobody collected.
