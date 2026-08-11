# Process Design Extract — Procure-to-Pay (To-Be)
**Ref:** SIG-01
**Source:** Signavio Process Manager — collection "PH_P2P_TOBE_v3.1"
**Status:** Design Authority approved 2026-05-28
**Extract date:** 2026-06-02

---

## Hierarchy

**L1:** Procure-to-Pay
**L2 process groups:** Requisitioning · Approval · Purchase Order Management · Goods Receipt ·
Invoice Processing

---

### PH-P2P-010 — Raise Requisition (Guided Buying)
**Swimlanes:** Requisitioner · Guided Buying (system) · Category Rules (system)

Requisitioner enters Guided Buying, selects a category tile, and either (a) selects from a
punch-out or hosted catalogue, or (b) completes a non-catalogue request form where the category
permits it. System validates cost centre, GL and delivery site at entry — request cannot be
submitted with incomplete data.

Non-catalogue path is restricted by category: permitted for Engineering Services, R&D
Consumables and Facilities Works; blocked for IT Hardware, Stationery, MRO (catalogue mandatory).

*Replaces:* email to procurement mailbox + manual ME51N entry.

---

### PH-P2P-020 — Requisition Approval (Automated Workflow)
**Swimlanes:** Cost Centre Owner · Category Approver (conditional) · Workflow Engine

Approval routes automatically from the DOA held in the system. Approver receives a task in the
Ariba inbox and mobile app with full line-item detail. Approve/reject/return-for-edit only —
no ability to approve above own limit, and no ability to edit line values.

Values above €50k route additionally to Category Approver. Values above €250k route to
Finance Director.

**Split-purchase detection:** system aggregates requests from the same requester, cost centre
and supplier over a rolling 30 days and routes to the next approval tier where the aggregate
crosses a threshold.

*Replaces:* email approval against SharePoint DOA spreadsheet.

---

### PH-P2P-030 — PO Creation & Transmission
**Swimlanes:** Workflow Engine · Ariba Network · Supplier

PO auto-generates on final approval and transmits to the supplier via Ariba Network. Supplier
confirms order in the Network. No buyer intervention on catalogue orders.

Buyer intervention retained only for: non-catalogue requests over €50k, and any request
flagged by the exception rules.

*Replaces:* manual PO creation in ECC by buyer; PO emailed as PDF.

---

### PH-P2P-040 — Goods Receipt
**Swimlanes:** Requisitioner / Delivery Contact · Warehouse (stock items)

Non-stock: the **requisitioner** confirms receipt in Guided Buying. This is new — today Goods
Receipt for non-stock is done centrally by the AP team from delivery paperwork.
Stock items unchanged (warehouse SAP transaction).

---

### PH-P2P-050 — Invoice Processing (Supplier-Submitted)
**Swimlanes:** Supplier · Ariba Network · AP Team

Supplier submits invoice through Ariba Network against the PO. Three-way match runs
automatically. AP handles exceptions only.

Paper and PDF-email invoices are **not accepted** post go-live for enabled suppliers.

*Replaces:* AP keying invoices from PDF/paper; manual matching.

---

## Notes recorded in the model

- AP team headcount currently 11 (UK 7, PL 4). Design assumes exception-only handling.
- Emergency/urgent purchase path is marked **TBC** in the model — placeholder task
  PH-P2P-015 exists but is not designed.
