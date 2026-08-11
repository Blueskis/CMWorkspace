# Functional Specification — Guided Buying & Approval Framework
**Ref:** FS-01
**Document:** PH-FS-014 v1.6
**Author:** Solution Architect, Procurement Workstream
**Approved:** 2026-05-30

---

## 1. Scope

SAP Ariba Guided Buying, integrated with SAP S/4HANA (MM) and Ariba Buying & Invoicing.
Wave 1: UK and PL entities. Wave 2 (DE) out of scope for this specification.

## 2. Guided Buying configuration

### 2.1 Category tiles
14 category tiles configured. Each tile maps to a commodity group and determines the
permitted buying channel:

| Channel | Categories | Buyer involvement |
|---|---|---|
| Hosted catalogue | Stationery, MRO, IT Consumables | None |
| Punch-out catalogue | IT Hardware, Lab Supplies, Travel Goods | None |
| Non-catalogue form | Engineering Services, R&D Consumables, Facilities Works, Professional Services | Above €50k only |
| Blocked (sourcing required) | Any spend > €100k | Full sourcing event |

### 2.2 Mandatory fields at requisition entry
Cost centre, GL account, delivery site, required-by date, and — for non-catalogue —
a structured specification (min. 40 characters) and a suggested supplier.

Requisition **cannot be saved as draft without** cost centre and GL. This is a deliberate
design decision to eliminate downstream data chase (see INT-01 finding: ~33% rework rate).

### 2.3 Free-text purchasing
Free-text purchasing outside the configured channels is **not available**. There is no
"other" tile. Requests that fit no category route to a Procurement triage queue with a
target 2-day response.

## 3. Approval framework

### 3.1 DOA source of truth
Delegation of Authority is held in Ariba and mastered from the HR org structure via daily
interface. The SharePoint DOA spreadsheet is decommissioned at go-live.

### 3.2 Approval limits (Wave 1)

| Grade band | Limit |
|---|---|
| Cost Centre Owner | €25,000 |
| Department Head | €50,000 |
| Category Approver | €250,000 |
| Finance Director | Unlimited |

### 3.3 Enforcement
- An approver **cannot** approve above their limit. The system routes onward automatically;
  there is no override and no "approve anyway" path.
- Approvers **cannot** edit line values or quantities. Return-for-edit only.
- Self-approval is blocked in all cases regardless of value.
- Approval actions are logged with user, timestamp and IP for audit.

### 3.4 Aggregation rule
Requests from the same requester + cost centre + supplier within a rolling 30 days are
aggregated for limit purposes. This closes the split-purchase gap.

### 3.5 Escalation
Tasks not actioned within 3 working days escalate to the approver's line manager.
After a further 2 days, to the Finance Director. Escalation is automatic and visible.

## 4. Goods receipt

Non-stock goods receipt is performed by the named delivery contact on the requisition
(defaults to the requisitioner). Confirmation via the Guided Buying UI or mobile app.
No invoice will be paid without a receipt — the AP-side manual GR workaround used today
is removed.

## 5. Reporting

Requisitioners and approvers get self-service status visibility on their own requests.
Cost centre owners get a live committed-spend view against budget, replacing the monthly
commitment report currently issued by Finance.

## 6. Known gaps at time of writing

- **Emergency/off-hours purchasing is not specified.** Raised at design authority
  2026-05-14 and deferred. Owner: Procurement Workstream Lead. No target date.
- Interface for supplier bank detail changes pending Security review.
