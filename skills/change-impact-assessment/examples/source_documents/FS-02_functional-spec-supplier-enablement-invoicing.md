# Functional Specification — Supplier Enablement & Invoice Automation
**Ref:** FS-02
**Document:** PH-FS-021 v1.2
**Author:** Solution Architect, Supplier & Finance Integration
**Approved:** 2026-06-01

---

## 1. Supplier enablement

### 1.1 Network registration
All transacting suppliers must hold an active Ariba Network account. Enablement runs in
three tranches:

| Tranche | Suppliers | Spend coverage | Target |
|---|---|---|---|
| 1 — Strategic | 340 | ~90% | T-10 weeks |
| 2 — Tail (managed) | 460 | ~8% | T-4 weeks |
| 3 — Tail (self-service) | ~400 | ~2% | T+8 weeks |

Suppliers not enabled by go-live cannot receive POs or submit invoices. Legacy PO/invoice
processing is switched off at T+0 for tranche 1 and 2 suppliers.

### 1.2 Supplier-maintained data
Suppliers maintain their own: contact details, remittance/bank details, tax registrations,
insurance and certification documents, and ESG questionnaire responses.

The client's Master Data team **no longer creates or amends supplier records** for these
fields. Their role becomes review and approval of supplier-submitted changes.

Bank detail changes require dual approval (Compliance + Finance) and trigger a mandatory
call-back verification.

## 2. Invoice automation

### 2.1 Channels
- PO-flip in the Ariba Network (preferred)
- cXML integration for high-volume suppliers
- Network-hosted invoice entry for tranche 3

Paper and PDF-to-email invoicing is decommissioned for enabled suppliers at T+0.

### 2.2 Touchless processing
Three-way match (PO / GR / invoice) runs automatically. Tolerances: ±2% or €50 on price,
0% on quantity. Matched invoices post without human intervention.

Design target: **85% touchless** by T+3 months, against a current manual-entry baseline
of 0%.

### 2.3 AP role change
The AP team moves from data entry and matching to **exception management only**. Exception
categories: price/quantity mismatch, missing GR, blocked supplier, duplicate detection,
tax code failure.

Volume assumption in the business case: AP transactional effort reduces by ~70%. The
business case assumes redeployment rather than reduction, but this has not been confirmed
in writing to the team.

Current AP headcount: 11 (UK 7, PL 4).

### 2.4 Payment queries
Suppliers self-serve payment status in the Network. The AP shared mailbox
(currently ~400 supplier queries/month) is expected to reduce substantially and is
targeted for decommissioning at T+6 months.

## 3. Reporting and analytics

Spend analytics replaces the current quarterly spend cube produced manually by the
Procurement Analyst. Category Managers get self-service dashboards.

The Procurement Analyst role's primary current deliverable is therefore eliminated.
No revised role definition exists yet.

## 4. Known gaps

- Tranche 3 self-service enablement has no assigned owner.
- No decision recorded on what happens to non-enabled tail suppliers after T+8 weeks.
