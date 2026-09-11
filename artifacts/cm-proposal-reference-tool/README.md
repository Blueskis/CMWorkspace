# CM Proposal Reference Tool

A published claude.ai Artifact for finding which past proposals are most relevant to a new
tender. Drop in the RFP (or paste it), and it reads out the requirements, pulls candidate
keywords, and ranks the firm's past bids — read live from Airtable — by how much of the
tender those keywords cover.

## Why it exists

Before drafting a bid, a practitioner needs to know which past proposals are worth opening
first. This tool automates that first pass: it never writes content, it only surfaces the
shortlist — open the ones whose name looks right, whatever they scored.

## Files

```
artifacts/cm-proposal-reference-tool/
└── index.html   # the artifact (single file, published to claude.ai)
```

## How it works

1. **Read the tender.** Drop or paste a `.txt` / `.md` / `.docx` / `.pptx` (all parsed in
   the browser — nothing leaves the page). Two built-in samples (a public-sector tender and
   a transport-sector ERP RFP) let you exercise the flow without a real client document.
2. **Keyword extraction.** The page pulls candidate keywords out of the tender text
   automatically; add or remove any before ranking.
3. **Similar past proposals.** Reads the firm's past-bid record live through the viewer's
   own Airtable connector (`mcp` capability) — the page never holds a token or a stale
   copy. Ranking rewards a keyword only a few past bids carry over one they all share, and
   nudges won bids up / lost bids down slightly, never enough to outweigh subject match.

## Capabilities and sharing

Declares the `mcp` capability (Airtable). Per this project's house rule (see `CLAUDE.md`),
**declaring `mcp` makes the artifact organization-internal — not link-shareable.** If a
link-shareable copy is ever needed (as with Change Impact Intake's testing copy), publish a
second copy with the Airtable panel and `mcp` capability removed, degrading to "no live
ranking" rather than a broken page.

## Known style deviation

This artifact predates `CLAUDE.md`'s artifact house style and does not yet match it: it
loads Google Fonts (Libre Franklin / Newsreader / IBM Plex Mono) rather than system fonts,
and uses its own token names (`--seal`, `--jade`, `--amber`, `--red`) rather than the
house palette (`--accent`, `--jade`, `--amber`, `--clay`). Re-sync it to the house style
the next time this artifact needs a substantive update, rather than as a standalone pass.

## Publishing or updating it

Single self-contained HTML file, no build step. Publish with the Artifact tool (capability
`mcp: {}` for the Airtable connector), or update an existing published copy by passing its
URL.
