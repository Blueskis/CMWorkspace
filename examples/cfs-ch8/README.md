# Sample Input — CFS Part 2, Chapter 8 (Change Management and Training)

The standing sample input for `cm-proposal-generator`. Unlike `examples/acme-erp/`, which
is synthetic and was written alongside the scripts, this is a **real tender requirements
chapter** — so it exercises the pipeline against document structure nobody designed for it.

## Anonymisation

Verified before use, not assumed:

- **No tenderer is identified.** Every party appears as a generic role — *the Authority*,
  *the Contractor*, *the Tenderer*, *Licensees*. 13 occurrences of "Tenderer", 56 of
  "Contractor", 55 of "Authority", all generic.
- **No company names, emails, URLs or phone numbers.** Every multi-word proper noun in the
  document is a domain term (*Change Management Plan*, *Business Rule Training*, and so on).
- **The Authority is unnamed too**, so the client side is anonymous as well as the supplier
  side.
- **PDF metadata was stripped.** The original carried Microsoft Information Protection
  labels including a `SiteId` tenant GUID, which identifies the issuing organisation's
  Microsoft 365 tenant. Text extraction cannot see this — it lives in the PDF's metadata
  dictionary. The copy here has it removed; only a title and subject remain.

The only residual locator is Singapore, named in clause 5.1.11 as where onsite training
must be conducted.

## What makes it a good test

**It is one chapter of a multi-part tender.** It carries 63 requirements but no evaluation
criteria, no weights, no submission deadline, no response format and no page limit — those
live in parts not supplied. Stage 2 sizes sections by evaluation weight, so it cannot run
properly on this alone. That is a realistic condition, not a defect in the sample: bid
teams routinely receive chapters piecemeal.

**It cross-references documents we do not have** — Part 2 Chapter 4 Clause 6 for role
descriptions, Part 3 Annex I and Annex VII for pricing formats. Three requirements cannot
be answered without them.

**Its requirements are dense and nested.** Clause 3.1.2 alone lists fourteen sub-deliverables
(a)–(n), and 3.1.2(a) has six components of its own. This tests the extraction rule about
not merging requirements to tidy the list.

**Requirement types are mixed**, and v0.2 records the difference. Some are content for the
proposal (*the Tenderer shall provide a Transition Management plan*), some are delivery
obligations for after award (*the Contractor shall collect evaluation forms within seven
days*), and some are commercial constraints (*at no additional cost to the Authority*).
v0.1's schema could not tell them apart, which meant treating a delivery obligation as
something a slide "covers".

The `kind` on each requirement here follows the chapter's own pronouns — *the Tenderer* is
the bidder writing the response, *the Contractor* the party after award — with anything
carrying "at no additional cost" marked commercial:

| kind | Count |
|---|---|
| `proposal-content` | 30 |
| `delivery-obligation` | 29 |
| `commercial-constraint` | 4 |

No requirement here is a `submission-rule`, which is itself informative: the rules about
the response document live in the instructions-to-tenderers part, which we were not given.

## Files

| File | What it is |
|---|---|
| `inputs/…Change-Mgt-and-Training.pdf` | The source chapter, metadata stripped |
| `inputs/…Change-Mgt-and-Training.txt` | Extracted text, page-marked |
| `rfp_triage.json` | Stage 1 output — 52 sections scored for CM relevance |
| `rfp_brief.json` | Stage 2 output — 63 requirements, 6 open questions |

## Reproduce Stages 1–2

```bash
# Extract the text (the pdf skill, or pypdf directly)
python3 -c "
import pypdf
r = pypdf.PdfReader('examples/cfs-ch8/inputs/CFS-Part2-Ch8-Change-Mgt-and-Training.pdf')
print('\n'.join(p.extract_text() for p in r.pages))"

# Stage 1 — triage
python skills/cm-proposal-generator/scripts/triage_rfp.py \
    examples/cfs-ch8/inputs/CFS-Part2-Ch8-Change-Mgt-and-Training.txt \
    -o examples/cfs-ch8/rfp_triage.json
```

Then extract per `skills/cm-proposal-generator/reference/rfp-extraction.md`.

**Triage on a CM-only chapter is a degenerate case** — every section scores CM-relevant,
because every section is. That is the correct answer and a useful control: the interesting
run is a full multi-part tender, where the set-aside list is most of the document. What it
does earn its keep for here is ranking: clause 3.1.2 comes out far ahead of everything
else, which is exactly the fourteen-sub-clause deliverable Stage 3 should size the deck
around.

## Known blocker for Stages 3–6

Section sizing depends on evaluation weights this chapter does not contain. Either supply
the instructions-to-tenderers part, or size from `named_deliverables` and the triage
ranking and record the assumption. Do not invent weights.
