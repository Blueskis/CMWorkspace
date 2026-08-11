# Standard cutover comms line items — default content

Pre-fill library. Use these as the starting draft for each derived line item, then
adapt to the specifics the CM member gave. Never present these verbatim as if they
were the member's own decisions — they are defaults to be corrected.

`{system}` = system/service name. `{sponsor}` = named executive sponsor.

---

## T-21 — Early notice (external audiences / readiness prerequisite only)

- **Purpose**: Give external parties or not-yet-ready users the lead time they need to plan, arrange cover, or complete a prerequisite before the cutover window.
- **Audience**: Customers / vendors / partners / regulators, or users with incomplete training.
- **Channel**: Customer notice or vendor notice; for training, manager cascade (named non-completers).
- **Sender**: Account/relationship owner for external; line manager for readiness chasers.
- **Owner**: Change Management Lead.
- **Approver**: Cutover Manager + Comms/Legal for anything external.
- **Dependencies**: Confirmed cutover window; external contact list; contractual notice periods checked.

## T-14 — First reminder

- **Purpose**: Establish awareness of what is changing, when, and what will be unavailable, early enough that teams can plan work around the cutover window.
- **Audience**: All affected users; line managers.
- **Channel**: Email (all-user), reinforced by intranet article as the persistent reference.
- **Sender**: {sponsor} — the first comms should carry sponsor authority.
- **Owner**: Change Management Lead.
- **Approver**: Cutover Manager.
- **Dependencies**: Cutover window confirmed and locked; distribution list validated.

## T-7 — Second reminder

- **Purpose**: Reinforce the dates, confirm the downtime window, and point users to training, job aids and the support model.
- **Audience**: All affected users; line managers.
- **Channel**: Email (all-user) + Teams/Slack post.
- **Sender**: Programme Director or Cutover Manager.
- **Owner**: Change Management Lead.
- **Approver**: Cutover Manager.
- **Dependencies**: Training/job aids published; support model and hypercare channel confirmed.

## T-3 — Action required (only when users must do something first)

- **Purpose**: Drive a specific, named pre-cutover action — clear open items, save work locally, submit early, re-enrol, etc. — with the deadline and the steps.
- **Audience**: Only the users who must act. Do not broadcast an action-required comms to people with no action.
- **Channel**: Email + manager cascade for tracked completion.
- **Sender**: Operational leader of the affected function (not the project) — the ask lands harder from the business.
- **Owner**: Change Management Lead.
- **Approver**: Cutover Manager.
- **Dependencies**: Freeze cut-off time in the runbook; step-by-step job aid drafted.

## T-1 — Final reminder

- **Purpose**: Final notice of the exact downtime start, what to close or save beforehand, and where to get support while the system is unavailable.
- **Audience**: All affected users; Service Desk; line managers.
- **Channel**: Email + Teams/Slack post.
- **Sender**: Cutover Manager.
- **Owner**: Change Management Lead.
- **Approver**: Cutover Manager.
- **Dependencies**: **Go/No-Go outcome** — this comms must not be pre-scheduled to auto-send; Service Desk briefed.

## Go/No-Go outcome (only where a formal gate exists)

- **Purpose**: Confirm the decision taken at the gate — proceeding, delayed, or standing down — so no one acts on the previous assumption.
- **Audience**: Cutover team; Service Desk; executive stakeholders; affected users if the answer changes their plans.
- **Channel**: Teams/Slack post; email if the decision changes user plans.
- **Sender**: Cutover Manager.
- **Owner**: Cutover Manager (time-critical — the CM lead may not be online at the gate).
- **Approver**: Pre-approved template, all three outcomes drafted in advance; no live approval step.
- **Dependencies**: Go/No-Go meeting held and decision minuted.

## Cutover begins

- **Purpose**: Confirm cutover is underway, the system is offline as planned, and set the expectation for when the next update arrives.
- **Audience**: All affected users; Service Desk; executive stakeholders.
- **Channel**: Teams/Slack post + service desk banner + in-app banner where available.
- **Sender**: Cutover Manager.
- **Owner**: Change Management Lead (or duty comms contact if out of hours).
- **Approver**: Cutover Manager.
- **Dependencies**: Runbook step confirming the system has been taken offline.

## Mid-cutover checkpoint (cutover >24h or across a weekend/holiday)

- **Purpose**: Confirm progress against plan at an agreed checkpoint so silence doesn't get read as failure.
- **Audience**: Executive stakeholders; Service Desk; affected users if the outage is user-visible.
- **Channel**: Teams/Slack post.
- **Sender**: Cutover Manager.
- **Owner**: Cutover Manager.
- **Approver**: Pre-approved template with on-track / delayed variants.
- **Dependencies**: Checkpoint time agreed in the runbook.

## Go-live (T+0)

- **Purpose**: Confirm the system is live and available, what users should do first, and how to get help.
- **Audience**: All affected users; line managers; Service Desk; external audiences if the outage was visible to them.
- **Channel**: Email (all-user) + intranet article.
- **Sender**: {sponsor} — closes the loop with the same voice that opened it.
- **Owner**: Change Management Lead.
- **Approver**: Cutover Manager + Programme Director.
- **Dependencies**: Post-cutover validation complete and signed off; hypercare channel live.

## T+1 to T+5 — Hypercare and support

- **Purpose**: Tell users how to raise issues during hypercare, what's a known issue, and what response to expect.
- **Audience**: All affected users; Service Desk.
- **Channel**: Teams/Slack post + intranet article.
- **Sender**: Service Owner or Cutover Manager.
- **Owner**: Change Management Lead.
- **Approver**: Cutover Manager.
- **Dependencies**: Known-issues list from post-go-live validation; hypercare rota confirmed.

## Hypercare close / return to BAU

- **Purpose**: Confirm hypercare has ended, where support now comes from, and close the change out.
- **Audience**: All affected users; Service Desk; executive stakeholders.
- **Channel**: Email + intranet article.
- **Sender**: Service Owner.
- **Owner**: Change Management Lead.
- **Approver**: Service Owner.
- **Dependencies**: Hypercare exit criteria met and signed off; BAU support handover complete.

## New-system variants

For a brand-new system the two base comms carry different weight than an upgrade's
reminders — there is no existing routine to interrupt, so the job is awareness and
adoption rather than disruption warning:

- **Pre go-live awareness (T-5)** — Purpose: introduce what the new system is, who
  it's for, what it replaces or enables, when it becomes available, and what (if
  anything) users need to do to get access. Sender: {sponsor}.
- **Go-live / now available (T+0)** — Purpose: confirm availability, how to access
  it, the first thing to do in it, and where to get help. Sender: {sponsor} or
  Service Owner.

## Decommission variants

- **T-14 / T-7** — what is being switched off, the date, and what replaces it.
- **T-1 final shutdown notice** — last chance to extract data or complete work.
- **Service retired** — confirm it's off, where the data went, and where to go now.
