# Bid Intake Desk

A browser front end for one question: **have we bid something like this before, and how
did it go?**

```
01 Read the tender          triage — which parts are CM's to answer
02 Similar past proposals   past bids from Airtable, ranked by similarity
```

This used to also assemble a plan and build a slide deck (Stages 03 and 04). Those were
cut so the tool could focus on being a reference desk rather than a deck-builder — see
git history if that work needs picking back up. What remains is deliberately small: read
a tender, see which past bids resemble it most, and open the ones worth a look.

## What it does

Upload a tender (or paste its text, or use a sample). Stage 01 triages it exactly as
`triage_rfp.py` would — the same lexicon, the same scoring — and shows which sections are
core to change management, which are related, and which are someone else's to answer.

Stage 02 reads `CM Knowledge Bank → Proposals and Tenders` live from Airtable, through
the viewer's own connector, and ranks every row against the tender's keywords: **+3** a
shared tag, **+2** a bid that was won, **−2** a bid that was lost, **−2** more if it was
submitted over two years ago. The keywords themselves are auto-picked from whichever tags
past bids actually carry and the tender happens to mention — add or remove any of them by
hand, and a re-rank never overwrites a deliberate edit that way.

For each past bid, two ways to open it, matching how the user actually wants to look at
it:
- **Open in Airtable →** — the record itself, with every field.
- **Open RFP / Deck directly** — the attached file, one click, no detour through Airtable's
  own UI.

Nothing is auto-selected and there is nothing to hand off — this is a reference tool, not
a pipeline stage. Deciding which past bid to actually reuse from is a judgement call for
the person reading it.

## Why past bids stay live in Airtable rather than baked in

Neither the page nor its build step can read an attachment out of Airtable — the files
live on a host the artifact's CSP blocks, and a build-time bake would go stale the moment
a new bid is submitted. Reading live through the viewer's own connector means the page
never holds a token and never shows a bid that was added five minutes ago as missing.

If the connector isn't available in a given view, Stage 02 says so plainly and Stage 01
still works — triage never depended on Airtable to begin with.

## Build

```bash
python tools/bid-intake-desk/build.py
```

Inlines the two sample tenders — a strict CSP blocks every external host, so anything the
page needs at load has to be in the page. The Airtable register is read live and needs no
baking.

`index.src.html` is the source; `index.html` is the built artifact. Never edit
`index.html` — the next build overwrites it.
