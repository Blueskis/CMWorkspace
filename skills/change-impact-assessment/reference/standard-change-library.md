# Standard Change Library

A table of change patterns compiled from past assessments, kept in the same Airtable base as
the live register (`Standard Change Library`, alongside `Sources` and `Change Impacts`). The
point is to stop every CIA starting from a blank page — a CM lead who has run ten SAP/Ariba
rollouts already knows procurement approvers usually take the hardest hit on contract workflow
changes. That knowledge currently lives in someone's head. This table is where it lives instead.

**What it is not: a source of ratings.** Every row in the actual `Change Impacts` register
must still trace to this engagement's own evidence — an interview, a brief, a document. The
library exists to prompt the checklist, not to supply the answer.

## Schema

| Field | Type | Purpose |
|---|---|---|
| `Pattern ID` | Primary, text | e.g. `SCL-001` |
| `Process Area` | Text | Free-text taxonomy tag (`Procurement > Contract Management`, `Supplier Master Data`, ...). Deliberately not tied to any one client's L1–L4 codes, since those vary by client. |
| `Change Description` | Long text | What the standard change is, independent of any one client's wording |
| `Change Type` | Select: Brownfield / Greenfield / Hybrid | See "Brownfield vs. greenfield" below |
| `Typical Stakeholder Group` | Text | Who this usually lands on |
| `Typical People Impact` / `Typical Process Impact` / `Typical Technology Impact` | Long text | Narrative pattern, not a client-specific description |
| `Typical People (0-3)` / `Typical Process (0-3)` / `Typical Technology (0-3)` | Number | **Indicative, not a rating.** A prior to test, never copied into a live row uncorroborated. |
| `Typical Overall Impact` | Formula | Same unweighted average as the live register, for browsing/sorting the library |
| `Typical Resistance` | Select: Low / Medium / High | |
| `Typical Training Method` | Select | Same option set as `Change Impacts`, for consistency |
| `Typical Response Notes` | Long text | What training/comms approach tended to work |
| `Source Project(s)` | Long text | Anonymised — programme type, industry, rough year. **Never a client name.** |
| `Applied To Change Impacts` | Link → `Change Impacts` | Every live row drafted from this pattern, however it was scored |
| `Times Reused` | Count (of the link above) | How often the pattern has actually informed a row |
| `Status` | Select: Draft / Active / Retired | New entries start Draft until a second engagement confirms the pattern holds |
| `Notes` | Long text | |

## How to use it during Step 3 (Extract) or Step 4 (Score)

1. **Filter the library by Process Area** against the L1–L4 spine you're building for this
   engagement.
2. **Treat matches as a checklist, not a draft.** For each candidate pattern: does this
   engagement's evidence say anything about that stakeholder group and that kind of impact? If
   yes, score from the evidence as normal and note the pattern only informally. If the evidence
   is silent, either go find it (ask the client, check another document) or draft the row from
   the pattern explicitly flagged as such — never silently.
3. **A pattern-sourced row is provenance-distinct from an evidence-sourced one.** Set
   `Source Type` on the `Change Impacts` record to `Standard Change Pattern (Unvalidated)` and
   `Source Ref` to the pattern ID (`Pattern: SCL-014`), not a document reference. Cap
   `Confidence` at Low. Once a stakeholder confirms it in validation, flip `Source Type` to
   `Standard Change Pattern (Validated)` and let `Confidence` and `Validation Status` follow
   the normal rules.
4. **Link the row back to the pattern** via `Applied To Change Impacts` on the pattern's
   record, so `Times Reused` stays accurate and the pattern's own track record is visible.
5. **Never let a library score override an evidence score.** If the client's own document says
   People = 1 and the pattern typically runs People = 2, the document wins. Note the divergence
   in `Notes / Open Questions` — a pattern that consistently doesn't match this client's reality
   is itself a finding worth surfacing.

This is the same discipline `cm-proposal-generator` applies to its knowledge bank: every
content block traces to a source or carries an explicit gap marker. Here, "gap marker" is the
`Source Type = Standard Change Pattern (Unvalidated)` flag — a row that exists because a
pattern suggested it, clearly marked as not yet confirmed by this engagement.

## Brownfield vs. greenfield

This is a scoring lens, not a separate tool or a separate table. The same 0–3 rubric applies
either way — what differs is what you're watching for:

- **Greenfield** (no prior process — see the CMT contract-request assessment): there is no
  habit to break, but a new *mandatory* role can still score high on People. Don't default to
  low impact just because nothing existed before; the adoption burden is real even without a
  loss to grieve.
- **Brownfield** (see the Supplier Information Update assessment): impact often reads as *loss*
  or *risk transfer* rather than pure learning curve — a control moving to a group that never
  held it, in that example. Watch for accountability without the matching authority.

Tag `Change Type` on library patterns so the library itself can be filtered by this lens, but do
not fork the generator or the base over it.

## Seeding the library

Don't attempt a big-bang import of every historical CIA. The normalisation cost is real — past
engagements used different taxonomies and scoring scales, and raw historical rows carry
client-specific headcounts and sometimes named individuals that must be stripped before a
pattern is reusable across clients. Seed it narrow:

1. Start with whatever 3–5 past assessments are easiest to pull, plus any patterns that repeat
   inside the current base's own `Change Impacts` records.
2. Anonymise on the way in — `Source Project(s)` describes the kind of programme, never the
   client.
3. Leave `Status = Draft` until the pattern has actually informed and been validated in a
   second, different engagement. A pattern seen once is an anecdote; twice is a pattern.
4. Grow it at the end of each engagement, not as a separate project — after Step 8 (Hand over),
   ask whether any High or Medium rows in the register just-completed look like they'll recur,
   and add them.
