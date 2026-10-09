# Relationship taxonomy

| Kind | Type | Direction means | Example |
|---|---|---|---|
| formal | `reports_to` | from reports to | Planning reports to Maintenance Operations |
| formal | `approves` | from approves to's request | Finance approves the Programme Office's budget |
| formal | `hands_off_to` | work or information passes from to | Technical Services hands engineering orders to Planning |
| formal | `escalates_to` | from escalates issues to | Union escalates to HR |
| formal | `governs` | from sets rules for to | The regulator governs Quality and Safety |
| informal | `consults` | from seeks advice from to | Quality consults the regulator's inspector |
| informal | `trusts` | from relies on to's judgement | COO trusts the Programme Director |
| informal | `influences` | from shapes to's opinion or behaviour | A senior engineer influences Quality |
| informal | `bypasses` | from works around to | Night shift bypasses central planning |
| informal | `conflicts_with` | friction, competing priorities | Engineers conflict with Planning on release timing |
| informal | `gatekeeps` | from controls access or pace for to | Finance gatekeeps contractor purchase orders |

**Strength**: 1 occasional, 2 regular, 3 routine or decisive. **Drawing**: formal = straight solid line; informal = curved dashed arc; `bypasses` and `conflicts_with` are drawn in the critical colour. Kind and type must agree; the build rejects an informal tie with a formal type.
