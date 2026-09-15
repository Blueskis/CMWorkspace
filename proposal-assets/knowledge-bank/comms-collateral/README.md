# Comms Collateral

Past communications that landed well. One entry per artifact, read by
`cm-comms-generator` at Stage 2.

**Tag every entry with its channel** — `email`, `banner`, `deck`, `video` — plus change type
(`technology`, `process`, `people`) and sector. The channel is a tag rather than a folder on
purpose: `retrieve.py` scores tag overlap at +3 against a section match at +2, so
channel-as-tag is the stronger retrieval signal, and per-channel folders would fragment a bank
that is already thin.

## What to put here

The **structure and phrasing that worked**, not the change it described. A go-live email for a
payroll system is useful to a future finance-system go-live because of how it sequenced the
action and the reassurance, not because of the payroll content. Write the body so the reusable
part is obvious: keep the scaffolding, strip the change-specific detail down to a worked
illustration.

Worth capturing after every send:

- The artifact itself, or the parts of it worth reusing
- What the response was, where it is known — open rate, ticket volume, completion rate
- What you would change next time

An entry recording that a comm *failed* is as useful as one recording success, provided the
body says why. Tag those `lessons-learned`.

## Clearance

`clearance` governs whether the client may be named, exactly as it does for proposal content.
Internal staff comms are more sensitive than most bid collateral, not less — a real all-staff
email about a redundancy-adjacent change should almost always be `anonymised` or
`internal-only`, and `internal-only` entries are excluded from retrieval by default.

## Retrieval

Always `--strict-section`, so past comms cannot surface in a proposal run:

```bash
python skills/cm-proposal-generator/scripts/retrieve.py kb_index.json \
    --section comms-collateral --tags email,technology,go-live --strict-section --top 5
```
