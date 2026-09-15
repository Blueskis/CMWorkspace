# How content reaches the assessment

The `Change Impact Intake` artifact has **two modes**, and mode 1 has **three channels**. Every
path — regardless of mode or channel — lands with Claude, who does the actual extraction and
scoring; nothing here is a shortcut around that. A mode/channel changes how content arrives,
never what happens to it once it does.

| Mode | Channels | Output |
|---|---|---|
| **Generate a CIA process** | Free text (chat or artifact tab) · Intake form · Excel upload | Rows written into the live `Change Impacts` register in Airtable |
| **Generate a new baseline CIA** | A transformation prompt, plus optional Word/Excel/PowerPoint/PDF/text documents | A downloadable baseline `.xlsx` workbook, delivered in chat |

Whoever holds the process knowledge for a change doesn't always have this chat open — a CM lead
does, but the client stakeholder they're pulling detail from usually doesn't, and the person
kicking off a whole-transformation baseline may want to do it in one sitting from a scope
document rather than a conversation. Both modes exist for that reason.

## Mode 1 — Generate a CIA process

One process change in, rows in the register out. Reuses Steps 3–5 of `SKILL.md` (Extract,
Score, Derive response), then Step 9 (push to Airtable) — unchanged regardless of which channel
supplied the content.

| Channel | Where | What it gives Claude |
|---|---|---|
| **Free text** | Pasted directly in this chat, or the artifact's Free text tab | A narrative brief, read and extracted like any other source |
| **Intake form** | The artifact's Form tab | Structured per-field input: L1–L4, as-is/to-be, a scoring steer, and a stakeholder group list, one card per process change |
| **Excel upload** | The artifact's Excel tab, or a chat attachment | A filled (or partially filled) copy of the client's own `CIA Template.xlsx`, extracted by `scripts/import_cia_excel.py` |

### The artifact's three channel tabs (mode 1 only)

Mode 1 carries all three as tabs over one submission mechanism, so a non-technical contributor
never needs to know which one is "supposed" to be used — they pick whichever is easiest for
what they have:

- **Form** — the original structured intake: repeatable process-change cards with nested
  stakeholder groups. Best when someone is composing the brief fresh, in the browser.
- **Free text** — one big textarea. Best for pasting an already-written note, an email, or
  meeting minutes, without reshaping it into fields first.
- **Excel upload** — a file picker for `.xlsx`. Best when a client or CM team member has
  already been filling in the template itself, possibly outside this engagement's chat
  entirely.

Submitting any tab appends a batch to the page's `history`, tagged `channel: "form" |
"freetext" | "excel"` (a mode-2 batch is tagged `mode: "baseline"` instead — see below), with
status `submitted`. **This session runs remotely and cannot hold a live watch on the
artifact**, and cannot register a wake subscription on it either — nothing wakes Claude
automatically when someone submits, in either mode, purely from the artifact side.

`reference/intake-worker.md` designs a fix — a claim/lease queue protocol and a 1-minute
polling loop, backed by an hourly Routine as a durability floor — but **as of the last update
to this file, that loop is not yet running.** Until it is, the manual trigger is still how
batches get processed: tell Claude a batch has landed; it re-reads the artifact, processes
whatever's waiting, and republishes with the batch marked `processed` — the resulting Airtable
rows listed inline for mode 1, or a rating-distribution summary and a CSV download for mode 2.
Check `reference/intake-worker.md`'s Status section before assuming otherwise.

## Mode 2 — Generate a new baseline CIA

One prompt (plus optional documents) in, a whole draft workbook out — for a client to prune and
discuss, not an evidence-linked baseline. Read `reference/baseline-generation.md` in full before
processing one of these; it covers coverage strategy, provenance while the Standard Change
Library is unseeded, and why `.xlsx` can't be offered as an in-page download (the `downloads`
capability's allowlist has no `xlsx` entry) — delivery is `SendUserFile` into chat, with a
best-effort CSV download button on the page for a viewer who isn't in the chat.

The mode switcher sits above the channel tabs, visually distinct from them — the two are
different levels of navigation, not siblings. Switching modes doesn't touch either mode's
draft; a half-filled baseline prompt survives switching to mode 1 and back.

### How the browser hands over an Excel file

The CSP an Artifact runs under blocks every external script host but Google Fonts, so there
is no way to load an in-browser `.xlsx` parser (that format is a zip container — DEFLATE plus
XML — not something worth hand-rolling for this). The page doesn't try: it reads the chosen
file as bytes via `FileReader`, base64-encodes them, and embeds that string in the same
`state-data` JSON the rest of the page's state already lives in. Claude decodes it back to a
real `.xlsx` file when it re-reads the artifact. A client-side 8MB cap keeps this sane — a
filled CIA template is normally well under 1MB.

**Processing any batch carrying a file blob — mode 1's Excel channel or mode 2's document
uploads — must strip the base64 from `history` before republishing.** The raw bytes have no
reason to stay in the page once extracted, and leaving them piles up: every unprocessed upload
sits in the document until it's handled, and the published page has a 16MB ceiling. Keep
`name` and `size` for the history display; drop `base64`. Mode 2 also caps this at the source:
8MB per file, 6MB total per pending batch, enforced client-side before it ever reaches the
published state.

## Processing an Excel batch (via the artifact or a direct chat upload)

```bash
python3 scripts/import_cia_excel.py "uploaded.xlsx" -o extracted.json
```

This is extraction only, same division of labour as `ingest_sources.py` for every other
format — it does not score anything the sheet left blank. It:

1. Confirms the sheet's columns match the client template's layout (position-based, tolerant
   of the As-is/To-be header cells' extra instructional text — see the script's own comment
   for why exact-string matching would false-positive there).
2. Detects whether the `--extended` governance columns are present.
3. Walks rows from row 3 until five consecutive blank rows, emitting one JSON dict per
   populated row using the same keys as `cia_input.json`'s `impacts[]`
   (`reference/input-schema.md`) — `null` for anything left blank, never guessed.
4. Reports on stderr how many rows already carry all three dimension scores.

Read the output like a stack of partially-completed sources: rows with all three scores and
solid as-is/to-be text may need only Step 5 (derive response) and a sanity check against
whatever supporting brief came with the file; rows missing scores need the full Step 4 pass,
exactly like a freshly extracted interview finding. Cite the file itself as the source
(`source_ref`), and keep `confidence` honest about what was actually stated versus inferred —
a filled-in score in someone else's spreadsheet is not automatically High confidence just
because it arrived as a number rather than a sentence.

## Free text (mode 1) — no new tooling

This is what's been happening in this conversation from the start: a process brief pasted or
typed directly into chat, read and extracted the same way `reference/extraction-guide.md`
describes for any other document. The artifact's Free text tab is the same channel, routed
through the artifact instead of chat, for a contributor who doesn't have this conversation
open. Treat a submitted free-text batch exactly like a chat-pasted brief — no separate
handling required.
