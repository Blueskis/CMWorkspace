# Worked example — payroll-cadence

A complete, self-contained run through `cm-comms-generator`, using the same fictional
payroll change that appears as the Change Comms Console's own placeholder text (Marcus
Bell, Chief People Officer, ~2,400 UK/Ireland staff, portal activation deadline of 14
September 2026). No client data.

## What each file demonstrates

- **`change_brief.json`** — Stage 1 output. Two audiences (`A1` all staff, `A2` line
  managers), seven messages (`M1`–`M7`, the six mandatory questions plus the managers'
  extra training-action message), one confirmed timeline event (`T1`).
- **`comms_plan.json`** — Stages 2–3 output. Four `channel_run`s: an email and a banner
  for `A1`, an email and a briefing deck for `A2`. Every mandatory message reaches every
  audience it targets through at least one channel; every block carries `sources`.
- **`build_manifest.json`** — Stage 4 output, from `route_channels.py`. Routes each run to
  its producer (`docx` for the emails, `pptx` for the deck, `canva-poster` for the banner
  with its verbatim-ignored caveat carried in the manifest note).
- **`qa_report.md`** — Stage 5 output, from `qa_comms.py`. **PASS** — full coverage, full
  provenance, no cross-channel date or figure conflicts.

## Reproduce it

```bash
python skills/cm-comms-generator/scripts/route_channels.py \
    examples/payroll-cadence/comms_plan.json \
    skills/cm-comms-generator/schemas/channel_registry.json \
    -o /tmp/build_manifest.json

python skills/cm-comms-generator/scripts/qa_comms.py \
    examples/payroll-cadence/change_brief.json \
    examples/payroll-cadence/comms_plan.json \
    -r skills/cm-comms-generator/schemas/channel_registry.json \
    -o /tmp/qa_report.md
```

## What this example does not cover

Newsletter and video channels aren't exercised here — see
`reference/channel-library.md` for how those route. This example is deliberately the
"everything passes" case; the test list at `reference/qa-test-list.md` is where the
failure modes (uncovered message, missing provenance, conflicting dates, unconfirmed
date reaching a channel unmarked) are exercised against deliberately broken fixtures.
