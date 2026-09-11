# Process Design Extract — Source-to-Contract (To-Be)
**Ref:** SIG-02
**Source:** Signavio Process Manager — collection "PH_S2C_TOBE_v2.4"
**Status:** Design Authority approved 2026-05-28
**Extract date:** 2026-06-02

---

## Hierarchy

**L1:** Source-to-Contract
**L2 process groups:** Sourcing Event Execution · Supplier Selection & Award ·
Contract Authoring · Contract Lifecycle Management · Supplier Management

---

### PH-S2C-010 — Create and Publish Sourcing Event
**Swimlanes:** Category Manager · Buyer · Ariba Sourcing · Supplier

Category Manager builds the event from a template (RFI / RFQ / Reverse Auction), attaches the
requirement, sets the timeline and invites suppliers from the Ariba Network supplier pool.
Event publishes to all invited suppliers simultaneously. Sealed-bid by default — bids are not
visible to anyone, including the Category Manager, until the event closes.

*Replaces:* individual supplier emails and a manually built comparison spreadsheet.

**Mandated threshold:** all spend above €100k must go through a competitive sourcing event in
the system. Previously a policy expectation with no enforcement mechanism.

---

### PH-S2C-020 — Bid Evaluation and Award
**Swimlanes:** Category Manager · Evaluation Panel · Ariba Sourcing

System auto-generates the bid comparison on event close. Scoring is entered in-system against
pre-declared weighted criteria. Award decision and its rationale are recorded in the system and
form the audit trail.

Second-round negotiation runs as a further in-system round; offline negotiation is not
supported by the design.

---

### PH-S2C-030 — Contract Authoring
**Swimlanes:** Category Manager · Legal · Ariba Contracts

Contract is generated from a clause library against an approved template. Deviations from
standard clauses trigger mandatory Legal review workflow. Version control and approval history
are held in the system.

*Replaces:* Word documents emailed between Category Manager and Legal.

---

### PH-S2C-040 — Contract Lifecycle Management
**Swimlanes:** Contract Owner · Ariba Contracts (system)

All contracts held in the repository with structured metadata (expiry, value, renewal notice
period, owner). System issues automated expiry alerts at 180 / 90 / 30 days to the named
Contract Owner.

**Every contract requires a named Contract Owner.** This role does not exist today.

---

### PH-S2C-050 — Supplier Registration and Qualification
**Swimlanes:** Supplier · Category Manager · Compliance · Ariba SLP

Suppliers self-register on the Ariba Network and complete a qualification questionnaire
(financial, compliance, ESG, information security). Compliance reviews and approves.
Supplier maintains their own bank details, certifications and contact data — the client no
longer maintains these on the supplier's behalf.

Suppliers not registered on the Network **cannot be transacted with** post go-live.

**Scope:** ~1,200 active suppliers, of which ~340 represent 90% of spend and are targeted for
wave 1 enablement.
