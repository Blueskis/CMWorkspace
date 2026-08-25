# Worked example — Northwind Foods payroll change

A complete `cm-comms-generator` run. **Fictional client, invented change, invented brand.**
Doubles as the regression test for the comms pipeline.

Northwind Foods moves payroll from monthly to semi-monthly and onto a self-service portal.
It is a deliberately `hybrid` change — a process change (pay cadence), a technology change
(the portal), and a people change (managers take on timesheet approval).

## What's here

```
change_brief.json                  one brief: 4 audiences, 7 messages, 4 milestones, 2 open questions
brand_profile.json                 Northwind's approved palette, voice and channel specs
email/comms_plan.json              run 1 — email to A1 (all colleagues)          -> .docx
article/comms_plan.json            run 2 — intranet article to A1                -> .docx
briefing_deck/comms_plan.json      run 3 — manager cascade deck to A2             -> .pptx
banner/comms_plan.json             run 4 — intranet banner to A1                 -> Canva
explainer_video/comms_plan.json    run 5 — portal walkthrough for A1             -> Synthesia (reserved)
```

Five channel runs off **one** brief. That is the structural point: the brief is authored once
and reused, so no two drafts can disagree about a date.

## Reproduce it

```bash
cd <repo root>

# Index the shared bank (the comms sections carry the example entries these plans cite)
python skills/cm-proposal-generator/scripts/index_kb.py \
    proposal-assets/knowledge-bank -o /tmp/nw/kb_index.json

# Draft + QA every channel
for ch in email article briefing_deck banner explainer_video; do
  python skills/cm-comms-generator/scripts/render_markdown.py \
      examples/northwind-payroll/$ch/comms_plan.json \
      --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/$ch/draft.md
  python skills/cm-comms-generator/scripts/qa_comms.py \
      examples/northwind-payroll/change_brief.json \
      examples/northwind-payroll/$ch/comms_plan.json \
      --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/$ch/qa_report.md
  python skills/cm-comms-generator/scripts/route_channel.py \
      examples/northwind-payroll/$ch/comms_plan.json \
      --brief examples/northwind-payroll/change_brief.json \
      --brand examples/northwind-payroll/brand_profile.json \
      -o /tmp/nw/$ch/production_brief.md
done

# --- Build the two .docx artifacts for real ---
for ch in email article; do
  python skills/cm-comms-generator/scripts/build_docx.py \
      examples/northwind-payroll/$ch/comms_plan.json \
      --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/$ch
  NODE_PATH="$(npm root -g)" node /tmp/nw/$ch/build.js
  python skills/cm-comms-generator/scripts/verify_docx.py /tmp/nw/$ch/draft.docx \
      --plan examples/northwind-payroll/$ch/comms_plan.json \
      --brief examples/northwind-payroll/change_brief.json
done

# --- Deck theme (no client .potx ships here, so this is the from-scratch route) ---
python skills/cm-comms-generator/scripts/apply_brand.py \
    examples/northwind-payroll/brand_profile.json -o /tmp/nw/briefing_deck/deck_theme.json

# --- Handoff artifacts for the lanes with no reachable producer ---
python skills/cm-comms-generator/scripts/canva_brief.py \
    examples/northwind-payroll/banner/comms_plan.json \
    --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/banner/canva_brief.json
python skills/cm-comms-generator/scripts/video_spec.py \
    examples/northwind-payroll/explainer_video/comms_plan.json \
    --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/explainer_video/video_spec.json
```

Requires `docx` on the Node path for the `.docx` builds: `npm install -g docx`. The scripts
check and tell you if it is missing.

## Expected output

| Channel | Parts | Blocks | Failures | Gaps | Route |
|---|---|---|---|---|---|
| `email` | 10 | 13 | 0 | 1 | `skill:docx` — 4 steps |
| `article` | 11 | 13 | 0 | 1 | `skill:docx` — 4 steps |
| `briefing_deck` | 9 | 23 | 0 | 1 | `skill:pptx` — 3 steps |
| `banner` | 5 | 5 | 0 | 0 | `mcp:Canva` — handoff only |
| `explainer_video` | 6 | 10 | 0 | 0 | `mcp:Synthesia` — handoff only |

Every channel exits 0. The two `.docx` builds pass the `docx` skill's own OOXML validator and
`verify_docx.py`. `apply_brand.py` prints five contrast ratios, all passing Northwind's 4.5:1
floor. The explainer spec estimates ~101s against a 240s limit and flags two scenes whose script
over-runs their planned duration.

## What it demonstrates

**One brief, five channels, four producers.** Every plan draws on the same
`change_brief.json`; the briefing deck targets `A2` while the rest target `A1`. Each routes to
a different tool, and `route_channel.py` works out which without any of the plans naming one.

**Audience-subset coverage.** The email targets `A1` only. `M5` — the manager training
message — is aimed at `A2` and `A3`, so the QA report lists it as *out of scope for this run*
rather than failing the email for omitting it. This is the check that makes single-audience
runs workable, and it is the main behavioural difference from `qa_deck.py`.

**Three-state provenance.** Blocks cite knowledge-bank entry IDs
(`cc-go-live-email-example`), `brief:` references into the brief
(`brief:audiences.A1.required_action`), or carry an explicit gap. Every `brief:` reference is
resolved against the brief — a dangling one fails the run.

**Honest gaps, all real.** The email and article share open question 1: nobody has confirmed
whether agency-paid contractors see a change in payment timing, so the reassurance is flagged
rather than guessed. The deck's gap is the cover arrangement for a manager on leave during an
approval window — the first question managers ask, and genuinely undefined. `verify_docx.py`
proves each gap is still **visible** in the built `.docx`; a gap lost in production would make
an incomplete draft read as finished.

**An indicative date, hedged.** `T4` (paper payslips withdrawn) is
`date_confidence: "indicative"`. Both drafts say "around the end of November" and the deck's
speaker notes tell the manager to say so out loud. Stage 4 fails the run if an indicative date
appears with no hedging language.

**Full comms and signposts are scored differently.** The banner carries `M4` and a destination
and passes; it is not failed for omitting `M1`, `M2` and `M6`, which live in the channels it
points at. It is also not required to carry a signature — a banner is unattributed by nature.
Force the banner to full-comm coverage and it fails, which is the check working, not a bug.

**Copy and design are approved separately.** No client `.potx` or Canva Brand Template ships
here, so the deck and the banner both carry
`design_provenance: "generated-unapproved"`. QA passes the copy and *warns* on the design —
the artifacts still need client sign-off before anything is published.

**Two lanes with no producer, still delivering.** The banner and explainer video route to
connectors that are unreachable — Canva needs authorizing, and no Synthesia connector exists.
Both exit 0 and produce a real handoff artifact: a design brief with per-field copy and canvas
dimensions, and a video spec with a scene table, VO timing and a WebVTT caption file.

**Stated limits fail, registry defaults warn.** Northwind's profile states a 50-character
subject limit, which the draft respects. It states no `max_words`, so the registry's 300-word
default applies as a *warning* — the email body is 337 words. That distinction is deliberate:
an invented limit should not fail a run.

**QA gates production.** `route_channel.py` re-runs the audit itself and emits no route while a
hard failure stands. Break any block's provenance and the router refuses before a single
external call is made.

## Negative tests

Ways the pipeline must refuse to proceed. Each exits non-zero; all operate on copies in `/tmp`.

**Plan-level (v0.1, still enforced)**

| # | Break | Expected failure |
|---|---|---|
| a | Empty a block's `sources` | unattributed block |
| b | Remove `M4` from every section | uncovered must-land message |
| c | Point a source at `brief:audiences.A9.nonexistent` | dangling brief reference |
| d | Set `subject_max_chars` to 10 | subject over a stated limit |
| e | Add `M99` to a section's `message_ids` | unknown message — mapping error |
| f | Put "restructure" in the copy | prohibited term |
| g | Blank `approval.approved_by` | fails in `qa_comms.py` and `apply_brand.py` |
| h | Remove the help route from a full comm | help route absent |

**Routing and production (v0.2)**

| # | Break | Expected failure |
|---|---|---|
| i | Route a plan whose QA fails | `BLOCKED: QA has N failure(s)` — no route emitted |
| j | Route with a blank `approval.approved_by` | blocked before any external call |
| k | Hand `build_docx.py` a banner plan | wrong channel for this producer |
| l | Hand `canva_brief.py` an email plan | wrong channel for this producer |
| m | Strip a signpost's messages and its `cta` | signpost with nothing to say / nowhere to go |
| n | Add a sentence to the plan the document lacks | `verify_docx.py` — text did not survive |
| o | Set `channel` to something unknown | router rejects it against the registry |
| p | Blank `approval.approved_by` for `apply_brand.py` | refuses to emit a theme |
| q | Hand `video_spec.py` an email plan | wrong channel for this producer |

## Before using any of this for real

Delete the `*-EXAMPLE.md` entries from `proposal-assets/knowledge-bank/comms-*` and this
example folder, or they will be retrieved into a real communication. The Northwind brand
profile is invented and approved by a person who does not exist.
