---
name: cm-effort-estimator-v0.5
description: Sizes a change management pursuit in mandays, from scope drivers (impacted people, business units, sites, languages, deployment waves, training modules) through a bottom-up hours library, with an open-ended judgement layer where the practitioner types what they know in plain English and the estimator proposes named, reviewable adjustments to the drivers and lines already in the estimate. Ships as a single self-contained HTML artifact — no server, opens from disk. Use whenever a CM practitioner wants to size a bid in mandays, work out the implied team shape and FTE for a pursuit, or adjust an existing manday estimate with judgement that the scope drivers alone don't capture — phrases like "estimate the effort for this RFP", "how many mandays is this", "what team do we need for this", "adjust the estimate for X". Do NOT use this to write proposal content or a pitch deck — that is `cm-proposal-generator`. Do NOT use it to produce a price or a rate card — this is effort in mandays only; pricing is a separate commercial exercise.
---

# CM Effort Estimator

A single HTML artifact that turns RFP scope into a manday estimate, and lets a practitioner
adjust that estimate with judgement the scope drivers can't express on their own.

**v0.4 was the estimator: drivers in, mandays out, bottom-up from an itemised hours
library.** v0.5 adds one thing to it — an open-ended assistant the practitioner can type
judgement into, that proposes named adjustments to the estimate rather than a separate
number bolted on top. Everything v0.4 did (RFP analysis, the hours library, rank mix, global
and local streams, review cycles, delivery buffer) is unchanged.

## What it does

1. **Drivers → deliverables.** Ten volume drivers (impacted people, business units, sites,
   languages, deployment waves, programme duration, training modules, trainees per session,
   hypercare months, complexity) drive the quantity of each of 53 catalogue deliverables,
   itemised down to 189 costed tasks.
2. **RFP analysis, in the browser.** Drop a `.docx`, `.pdf` or pasted scope section in and
   the estimator reads drivers and deliverable signals straight out of the text — nothing
   leaves the browser.
3. **Judgement, named and reviewable (v0.5).** A third tab where the practitioner types
   what they know in plain English. The assistant proposes structured adjustments — each
   one a named write to a driver, a line's complexity or quantity, or a small whitelist of
   globals — with a rationale and a predicted manday delta, shown before anything moves.
   Accept, reject, or revert each one individually; every accepted adjustment stays on an
   audit trail with an exact, order-independent revert. See `reference/judgement-layer.md`
   for the full mechanics.
4. **Team shape.** Effort by consultant rank, average FTE, and implied duration.

## What it does NOT do

| Out of scope | Why |
|---|---|
| Price, rate card, discount, tax | This is effort only, in mandays. Pricing is a separate commercial exercise on top. |
| Write proposal content | That's `cm-proposal-generator` — this estimator doesn't draft slides or sections. |
| Semantic understanding of the RFP | RFP reading is keyword and pattern matching against an editable vocabulary, not a model reading the document. What the assistant reads is the *estimate*, not the RFP text directly, though an RFP excerpt is passed along as context. |
| Reprice the hours library, archetype matrix, rank mix or vocabulary from a judgement note | Those are admin configuration shared across every future pursuit. The judgement layer is barred from touching them, in validation, not just by asking nicely — see `reference/judgement-layer.md`. |

## Using it

Open `estimator.html` directly in a browser — no build, no server. State persists in the
browser's `localStorage`, so a session survives a reload but is private to that browser.

1. **Scope & RFP** — name the pursuit, pick global/local/both, drop or paste the RFP scope.
2. **Manday estimate** — review the deliverable lines the analysis produced (or start from
   standard CM scope), correct quantities and complexity by hand, set the delivery buffer.
3. **Judgement** — type what the drivers and lines don't yet capture. Review what comes
   back, accept what's right, reject or revert the rest.

Deliver the estimate as a first draft the practitioner reviews and can defend line by line,
not a number to repeat unexamined — the same posture `cm-proposal-generator` takes toward
its own output.

## Placeholder norms

The hours library (189 tasks, each costed by an archetype × complexity matrix) ships with
**defensible starting values, not the firm's calibrated benchmarks.** Say so on handover
until the admin tab's past-project effort table has been populated with enough real
engagements to recalibrate the library against — that table exists for exactly this, and
a deliverable with logged past-project rows is preferred over the seeded default the moment
it has enough of them. Same posture the proposal generator takes toward its generic HTML
template: useful to exercise the tool now, not to be mistaken for the firm's own numbers.

## Layout

```
skills/cm-effort-estimator/
├── SKILL.md                     # this file
├── estimator.html               # the whole tool — data, engine, judgement layer, UI
├── tests/judgement.test.js      # node:test, slices the engine + judgement blocks out
│                                #   of estimator.html and runs them standalone
└── reference/
    └── judgement-layer.md       # the adjustment schema, validation rules, and the
                                 #   admin-configuration boundary
```

`estimator.html` is stdlib-browser-only — no build step, no dependencies, no network calls
except the artifact platform's own `sample` capability for the judgement assistant, which
degrades gracefully to "every lever is still yours to set by hand" when unavailable.

## Verification

```bash
node --test skills/cm-effort-estimator/tests/judgement.test.js
```
