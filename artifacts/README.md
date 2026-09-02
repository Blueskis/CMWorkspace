# CM Effort Estimator v0.4

`cm-effort-estimator-v04.html` — a single self-contained page. Open it directly in a
browser, or publish it as an Artifact. State lives in `localStorage` under
`cm-estimator-v8`; nothing leaves the browser.

## What v0.4 changes from v0.3

v0.4 makes the tool purely an **effort** estimator — mandays only. Pricing is somebody
else's workbench.

- **No pricing, anywhere.** The rate card, billing rates admin tab, tax/currency table,
  discount / expenses / tax inputs, and the indicative-price block in the sidebar are all
  gone. Nothing on the page shows a currency, a day rate or a total price.
- **No country of implementation.** The scope tab no longer asks where the work is
  delivered — effort does not depend on it. The Manday estimate tab, exports and
  assumptions drop every mention of country.
- **Past quotes → Past project effort.** The admin tab that used to hold priced quote
  lines is now a mandays-only reference: project, year, industry, deliverable, qty,
  mandays, and mandays-per-unit (derived). It still calibrates effort where the hours
  library has no tasks for a deliverable — a deliverable with library tasks always
  prefers the library — and stands in for the effort database the CoE will host later.
- **Ranks stay — effort only.** The Analyst → Partner rank layer, team mixes per
  archetype, mandays-by-rank in the sidebar and exports, and average FTE are unchanged.
  Only the rate card and cost maths that used to sit on top of ranks came out.
- **Exports carry effort only.** CSV (`btn-export-csv`, renamed from
  `btn-export-invoice`) and the Markdown copy keep deliverable lines, stream subtotals,
  buffer, total mandays, archetype subtotals and mandays by rank — no price, fee, tax or
  currency rows.
- Storage key bumped to `cm-estimator-v8`; any v0.3 state (country, rate overrides,
  discount/expenses/tax) under `cm-estimator-v7` is dropped on load rather than restored.

## What v0.3 changed from v0.2

- **Country of implementation, rank mix and billing rates** were introduced (and are now
  removed again in v0.4, above): Singapore, Malaysia, Brunei, Vietnam, Cambodia,
  Indonesia and the Philippines, each with its own rate card, currency and default
  indirect-tax treatment; a deliverable's blended day rate came from its library tasks
  costed at their archetypes' rank mixes.
- **Complexity per deliverable.** Every line carries a Simple / Standard / Complex grade
  from the Hours library. Changing it re-resolves every task in that deliverable through
  the archetype matrix at that grade.
- **Virtual / blended / physical mode of conduct** on sessions, workshops, training
  delivery and change agent cadences. Physical carries more effort and seats fewer
  people, so it drives both mandays per session and the number of sessions needed.
- **Free-text deliverables.** Type a name, set quantity and complexity; the effort
  archetype is inferred from the wording, shown, and correctable.
- **CM vocabulary is editable**, out of the code and into an admin tab. The estimate
  shows the client's own term for each deliverable alongside ours.
- **Mandays** replaced "person-days" throughout, including both exports.

## Seeded data

The hours library (189 tasks, 53 deliverables, 8 archetypes) and the public-authority
sample RFP carry over from v0.2 unchanged; a second sample (a rail operator's depot
maintenance tender) exercises the vocabulary mapping against non-public-sector wording.
