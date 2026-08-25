# Three ways content reaches the assessment

Whoever holds the process knowledge for a change doesn't always have this chat open —
a CM lead does, but the client stakeholder they're pulling detail from usually doesn't. So
there are three channels in, and all three land in the same place: Steps 3–5 of `SKILL.md`
(Extract, Score, Derive response), then Step 9 (push to Airtable). None of them skip that
processing — a channel changes how content arrives, never what happens to it once it does.

| Channel | Where | What it gives Claude |
|---|---|---|
| **Free text** | Pasted directly in this chat | Exactly what's happened throughout this engagement so far — a narrative brief, read and extracted like any other source |
| **Intake form** | The `Change Impact Intake` artifact, Form tab | Structured per-field input: L1–L4, as-is/to-be, a scoring steer, and a stakeholder group list, one card per process change |
| **Excel upload** | The same artifact's Excel tab, or a chat attachment | A filled (or partially filled) copy of the client's own `CIA Template.xlsx`, extracted by `scripts/import_cia_excel.py` |

## The artifact's three tabs

The published `Change Impact Intake` page carries all three as tabs over one submission
mechanism, so a non-technical contributor never needs to know which one is "supposed" to be
used — they pick whichever is easiest for what they have:

- **Form** — the original structured intake: repeatable process-change cards with nested
  stakeholder groups. Best when someone is composing the brief fresh, in the browser.
- **Free text** — one big textarea. Best for pasting an already-written note, an email, or
  meeting minutes, without reshaping it into fields first.
- **Excel upload** — a file picker for `.xlsx`. Best when a client or CM team member has
  already been filling in the template itself, possibly outside this engagement's chat
  entirely.

Submitting any tab appends a batch to the page's `history`, tagged `channel: "form" |
"freetext" | "excel"`, with status `submitted`. **This session runs remotely and cannot hold
a live watch on the artifact** — nothing wakes Claude automatically when someone submits.
Tell Claude a batch has landed; it re-reads the artifact, processes whatever's waiting, and
republishes with the batch marked `processed` and the resulting Airtable rows listed inline.

### How the browser hands over an Excel file

The CSP an Artifact runs under blocks every external script host but Google Fonts, so there
is no way to load an in-browser `.xlsx` parser (that format is a zip container — DEFLATE plus
XML — not something worth hand-rolling for this). The page doesn't try: it reads the chosen
file as bytes via `FileReader`, base64-encodes them, and embeds that string in the same
`state-data` JSON the rest of the page's state already lives in. Claude decodes it back to a
real `.xlsx` file when it re-reads the artifact. A client-side 8MB cap keeps this sane — a
filled CIA template is normally well under 1MB.

**Processing an Excel batch must strip the base64 blob from `history` before republishing.**
The raw bytes have no reason to stay in the page once extracted, and leaving them piles up:
every unprocessed upload sits in the document until it's handled, and the published page has
a 16MB ceiling. Keep `file.name` and `file.size` for the history display; drop `file.base64`.

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

## Free text — no new tooling

This is what's been happening in this conversation from the start: a process brief pasted or
typed directly into chat, read and extracted the same way `reference/extraction-guide.md`
describes for any other document. The artifact's Free text tab is the same channel, routed
through the artifact instead of chat, for a contributor who doesn't have this conversation
open. Treat a submitted free-text batch exactly like a chat-pasted brief — no separate
handling required.
