# CM Pursuit Estimator (effort estimator v0.3)

`cm-effort-estimator-v03.html` — a single self-contained page. Open it directly in a
browser, or publish it as an Artifact. State lives in `localStorage` under
`cm-estimator-v3`; nothing leaves the browser.

## What v0.3 changes from v0.2

- **Two user tabs, four admin tabs.** Estimators see *Scope & RFP* and *Priced
  deliverables*. The Admin role toggle reveals *Past quotes*, *Hours library*,
  *Billing rates* and *CM vocabulary*. The role toggle is UI separation, not a
  security boundary.
- **Country of implementation.** Singapore, Malaysia, Brunei, Vietnam, Cambodia,
  Indonesia and the Philippines, each with its own rate card, billing currency and
  default indirect-tax treatment. Nothing prices until a country is chosen.
- **Rank mix drives price.** Day rates are no longer read off past quotes. Each of the
  eight effort archetypes carries a mix across seven ranks (Analyst → Partner); a
  deliverable's blended day rate is its library tasks costed at their archetypes' mixes
  against the selected country's card. Past quotes now calibrate effort and drive a
  variance flag instead.
- **CM vocabulary is editable.** The synonyms that map RFP wording onto catalogue
  deliverables moved out of the code and into an admin tab. The priced schedule shows
  the client's own term for each deliverable alongside ours.
- **Sidebar across both tabs** — total, fees, buffer/discount/expenses/tax, effort,
  blended rate, average FTE, duration, and person-days by rank.

## Seeded data

The rate card is **illustrative placeholder data**, not a real firm's card — replace it
before quoting anything. The hours library (189 tasks, 53 deliverables, 8 archetypes)
and the public-authority sample RFP carry over from v0.2 unchanged; a second sample
(a rail operator's depot maintenance tender) was written for v0.3 to exercise the
vocabulary mapping against non-public-sector wording.
