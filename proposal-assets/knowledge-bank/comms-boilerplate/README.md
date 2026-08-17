# Comms Boilerplate

Standing blocks reused close to verbatim across comms. Read by `cm-comms-generator` at
Stage 2.

## What belongs here

- Help and support routes, in the shapes they take for different clients
- Accessibility statements and alternative-format offers
- The data-protection line for comms that collect or process personal data
- Standard sign-off constructions
- "What's not changing" scaffolds — the recurring reassurance categories worth checking
  against every change

## Why this folder earns its place

These are the blocks most likely to be dropped under time pressure and most expensive to drop.
A comm with an action and no help route generates a wave of tickets to whoever signed it. A
comm with no alternative-format offer excludes people. Having them here means the draft carries
them by default and `qa_comms.py` can check they survived.

## Keep them adaptable, not final

A boilerplate block still needs the change's own specifics — a service desk address, an
actual deadline. Write the entry so the substitution points are obvious, and expect the draft
to adapt it. Adaptation is expected; fabrication is not.

Tag with `boilerplate` plus the block type (`help-route`, `accessibility`, `signoff`,
`data-protection`, `not-changing`).
