# Worked example — Northwind Foods payroll change

A complete `cm-comms-generator` run. **Fictional client, invented change, invented brand.**
Doubles as the regression test for the comms pipeline.

Northwind Foods moves payroll from monthly to semi-monthly and onto a self-service portal.
It is a deliberately `hybrid` change — a process change (pay cadence), a technology change
(the portal), and a people change (managers take on timesheet approval).

## What's here

```
change_brief.json      one brief: 4 audiences, 7 messages, 4 milestones, 2 open questions
brand_profile.json     Northwind's approved palette, voice and channel specs
email/comms_plan.json  channel run 1 — email to A1 (all colleagues)
deck/comms_plan.json   channel run 2 — manager cascade deck to A2 (people managers)
```

Two channel runs off **one** brief. That is the structural point: the brief is authored once
and reused, so the two drafts cannot disagree about a date.

## Reproduce it

```bash
cd <repo root>

# Index the shared bank (the comms sections carry the example entries these plans cite)
python skills/cm-proposal-generator/scripts/index_kb.py \
    proposal-assets/knowledge-bank -o /tmp/nw/kb_index.json

# --- Email channel ---
python skills/cm-comms-generator/scripts/render_markdown.py \
    examples/northwind-payroll/email/comms_plan.json \
    --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/email/draft.md

python skills/cm-comms-generator/scripts/qa_comms.py \
    examples/northwind-payroll/change_brief.json \
    examples/northwind-payroll/email/comms_plan.json \
    --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/email/qa_report.md

# --- Deck channel: brand the template, then render through the PROPOSAL generator ---
python skills/cm-comms-generator/scripts/apply_brand.py \
    examples/northwind-payroll/brand_profile.json \
    proposal-assets/templates/html-generic -o /tmp/nw/deck/template

python skills/cm-proposal-generator/scripts/render_html.py \
    examples/northwind-payroll/deck/comms_plan.json \
    /tmp/nw/deck/template -o /tmp/nw/deck/deck.html

python skills/cm-comms-generator/scripts/render_markdown.py \
    examples/northwind-payroll/deck/comms_plan.json \
    --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/deck/draft.md

python skills/cm-comms-generator/scripts/qa_comms.py \
    examples/northwind-payroll/change_brief.json \
    examples/northwind-payroll/deck/comms_plan.json \
    --brand examples/northwind-payroll/brand_profile.json -o /tmp/nw/deck/qa_report.md
```

## Expected output

| | Email run | Deck run |
|---|---|---|
| Parts / slides | 10 parts | 9 slides |
| Blocks | 13 | 23 |
| Failures | 0 | 0 |
| Warnings | 2 | 1 |
| Open `[GAP]`s | 1 | 1 |
| Exit code | 0 | 0 |

`apply_brand.py` prints five contrast ratios, all passing against Northwind's 4.5:1 floor.
`render_html.py` reports `Rendered 9 slides`.

## What it demonstrates

**One brief, two channels.** The email and the deck draw on the same `change_brief.json` and
target different audiences (`A1` and `A2` respectively).

**Audience-subset coverage.** The email targets `A1` only. `M5` — the manager training
message — is aimed at `A2` and `A3`, so the QA report lists it as *out of scope for this run*
rather than failing the email for omitting it. This is the check that makes single-audience
runs workable, and it is the main behavioural difference from `qa_deck.py`.

**Three-state provenance.** Blocks cite knowledge-bank entry IDs
(`cc-go-live-email-example`), `brief:` references into the brief
(`brief:audiences.A1.required_action`), or carry an explicit gap. Every `brief:` reference is
resolved against the brief — a dangling one fails the run.

**Honest gaps, one per channel, both real.** The email's gap is open question 1: nobody has
confirmed whether agency-paid contractors see a change in payment timing, so the reassurance
is flagged rather than guessed. The deck's gap is the cover arrangement for a manager on leave
during an approval window — the first question managers ask, and genuinely undefined.

**An indicative date, hedged.** `T4` (paper payslips withdrawn) is
`date_confidence: "indicative"`. Both drafts say "around the end of November" and the deck's
speaker notes tell the manager to say so out loud. Stage 4 fails the run if an indicative date
appears with no hedging language.

**A recoloured template, honestly labelled.** `apply_brand.py` puts Northwind's greens onto the
generic PoC template. That does not make it Northwind's approved deck, and the QA report's
human checklist says so.

**Stated limits fail, defaults warn.** Northwind's profile states a 50-character subject limit,
which the draft respects. It states no `max_words`, so the channel library's 300-word default
applies as a *warning* — the email body is 337 words. That distinction is deliberate: an
invented limit should not fail a run.

## Negative tests

Nine ways the pipeline should refuse to proceed. Each exits non-zero; all operate on copies in
`/tmp`.

| # | Break | Expected failure |
|---|---|---|
| a | Empty a block's `sources` | unattributed block |
| b | Remove `M4` from every section | uncovered must-land message |
| c | Point a source at `brief:audiences.A9.nonexistent` | dangling brief reference |
| d | Set `subject_max_chars` to 10 | subject over a stated limit |
| e | Add `M99` to a section's `message_ids` | unknown message — mapping error |
| f | Put "restructure" in the copy | prohibited term |
| g | Blank `approval.approved_by` | fails in **both** `qa_comms.py` and `apply_brand.py` |
| h | Point a deck slide at a layout the template lacks | rejected by `build_deck.py` via the renderer |
| i | Remove the help route from the draft | help route absent |

## Before using any of this for real

Delete the `*-EXAMPLE.md` entries from `proposal-assets/knowledge-bank/comms-*` and this
example folder, or they will be retrieved into a real communication. The Northwind brand
profile is invented and approved by a person who does not exist.
