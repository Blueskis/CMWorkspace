# Change Impact Assessment — CHG-014: New Asset Accounting (FI-AA) Go-Live

**Client:** CivicBoard (fictional) | **Go-live:** 1 Jan 2027 | **Assessed by:** Colonel Tan | **Date:** 2 Sep 2026

## Summary

New Asset Accounting replaces batch depreciation with real-time posting and introduces
three parallel depreciation areas. Highest impact falls on Fixed Asset Accountants
(process + system) and Statutory Reporting Analysts (reporting logic); Internal Audit
impact is procedural only.

## Impact register

| # | Impacted role | Impact type | Impact level | What changes | Readiness action |
|---|---|---|---|---|---|
| 1 | Fixed Asset Accountant | Process + System | **High** | Depreciation posts real-time per transaction, not at month-end batch. Manual reconciliation step is removed. | Hands-on training on real-time posting; walk through 3 sample asset transactions before go-live. |
| 2 | Fixed Asset Accountant | System | **High** | Must now post to 3 depreciation areas (statutory, tax, group) instead of 1. | New job aid: "Which depreciation area for which posting." |
| 3 | Finance Month-End Close Lead | Process | **Medium** | Month-end close checklist loses the "run depreciation batch" step; add "verify real-time postings complete" step. | Updated close checklist; 30-min briefing. |
| 4 | Statutory Reporting Analyst | Process | **High** | Statutory reports now pull from the dedicated statutory depreciation area automatically; manual GL-to-asset reconciliation is retired. | Training on new report source; parallel-run 1 reporting cycle before go-live. |
| 5 | Internal Auditor (Finance) | Policy/Control | **Low** | Control point moves from "review month-end batch log" to "review real-time posting exception report." | Briefing note only; update audit test scripts. |

## Overall readiness gap

- **Highest risk:** Fixed Asset Accountants (6 headcount) lose a control they currently
  rely on (manual reconciliation) with no direct replacement workflow trained yet. `[GAP]`
- **Recommended mitigation:** Add a 2-week hypercare period with FI-AA SME on standby for
  this role group specifically.

## Coverage note

5 of 5 affected roles mapped to at least one impact and one readiness action.
No unmapped roles.
