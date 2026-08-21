# Sample FSD — Procurement RICEFWA: Supplier Block / Unblock (S/4HANA)

Sample functional specification document for a Procurement SAP RICEFWA that allows
blocking and unblocking of registered suppliers in SAP S/4HANA (RICEFW ID MM-WA-014).

**Deliverable:** `FSD_MM-WA-014_Supplier_Block_Unblock.docx` (~24 pages, 29 tables, 10 figures)

## Contents
1. Document control (version history, approvals, related documents)
2. Business background (drivers, benefits, 10 business rules)
3. Functional description and scope (in/out of scope, assumptions, dependencies)
4. Process flow — swimlane diagram and step-by-step description, status model
5. Application system — landscape, systems/clients, development objects, entry points
6. Data model — standard fields updated, custom tables
7. Program flow and layout — screen layouts, field specs, workflow, validations,
   mass report selection screen, program logic, output layout
8. Effect on standard transactions
9. Non-functional requirements
10. Security and authorisation
11. Test scenarios · 12. Open items · Appendix A: reason code catalogue

## Figures

All 10 screenshots are mock-ups built as HTML in `figures/`, rendered headlessly
with Chromium at 2x scale. They illustrate a proposed design — they are not captures
of a live SAP system.

| File | Figure |
|---|---|
| `f01_landscape.png` | Application system landscape |
| `f02_flow.png` | End-to-end swimlane process flow |
| `f03_launchpad.png` | Fiori launchpad tile group |
| `f04_bp.png` | Transaction BP — block indicators |
| `f05_selscreen.png` | ZMM_SUPBLK_MASS selection screen |
| `f06_worklist.png` | Manage Supplier Block Requests worklist |
| `f07_detail.png` | Block request detail with impact preview |
| `f08_inbox.png` | My Inbox approval task |
| `f09_log.png` | ALV result list / application log |
| `f10_errors.png` | Validation messages, message class ZSUPBLK |

## Rebuilding

```bash
# 1. Re-render figures
cd figures
for f in f*.html; do
  chromium --headless --force-device-scale-factor=2 --window-size=1180,1600 \
    --screenshot=${f%.html}.png file://$PWD/$f
done

# 2. Rebuild the document (requires the `docx` npm package)
node build/gen.js FSD_MM-WA-014_Supplier_Block_Unblock.docx
```
