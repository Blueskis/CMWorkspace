# Generating a baseline CIA from a prompt

`Generate a new baseline CIA` is the artifact's second mode. It exists for a different moment in
an engagement than the first mode (`Generate a CIA process`): before interviews, before Signavio
models, sometimes before the programme has even confirmed its scope in detail — a CM lead needs
something concrete to put in front of the client and say "does this look right?" This produces a
**first-pass draft for validation**, not a baseline in the evidence-linked sense the rest of this
skill uses that word for. Say that plainly whenever one of these leaves your hands.

## What a baseline batch gives you

A `client`, `scope`, an optional `goLive` date, a free-text `prompt`, and zero or more attached
`files[]` (`.docx .xlsx .pptx .pdf .txt .md .csv`, decoded from the base64 the artifact embedded).
Treat the prompt as the primary brief and the files as corroborating detail — run every file
through `scripts/ingest_sources.py` exactly as you would for mode 1's Excel channel, and read
each one in full before building the spine.

If the prompt is thin (a sentence or two, no stakeholder detail), don't invent scope to hit a row
count — build what the input actually supports and say in the handover that the input was thin.
A baseline built from nothing but its own invention is worse than a short one.

## Coverage: comprehensive, client prunes

Target **40–80 rows**. The client's job is to delete what doesn't apply and flag what's missing —
that only works if the first draft casts wide. Build the L1–L4 spine across every process area
the prompt and documents imply, not just the ones spelled out in detail; a transformation prompt
that says "S/4HANA and Ariba" implies procure-to-pay, source-to-contract and supplier management
even if only one of those gets a paragraph. Split to one row per process change × stakeholder
group exactly as `reference/extraction-guide.md` describes for mode 1 — the same discipline about
L4 being where a process splits into different things for different people applies here too.

Don't pad with rows that don't say anything the client couldn't infer from the module name alone.
Wide coverage means area count, not row count for its own sake — five weak rows restating "this
module changes for procurement" are worse than four that each add a real observation.

## Provenance while the Standard Change Library is empty

The library (`Standard Change Library` in `appFD6GsiE3Jh5rGQ`) exists but currently holds no
patterns, so a baseline built today draws entirely from the prompt and attached documents:

- `source_ref` cites those — `BRF-01` for the prompt itself, `DOC-01`/`DOC-02`… for each attached
  file, exactly as `ingest_sources.py` would assign them
- `confidence` is `Low` for anything the row infers rather than states, `Medium` only where the
  prompt or a document says it directly — nothing in a prompt-only baseline earns `High`; that
  requires the interview/document depth mode 1 works from
- `validation_status` stays `Draft`
- every Low-confidence row carries a real, specific open question in `notes` — not a placeholder.
  This is also what silences `generate_cia.py`'s own "Low confidence with no open question"
  warning, and more importantly it's the actual validation agenda you're handing the client
- set `meta.version` to `"v0.1 — Generated Baseline (for client validation; not evidence-based)"`
  so the Assessment Info sheet states plainly what this document is, the same way mode 1's rows
  get flagged for confidence rather than presented as settled

## Once the library is seeded

Filter `Standard Change Library` by `Process Area` against the spine you're building, the same
checklist discipline `reference/standard-change-library.md` already describes for mode 1. A
pattern-derived row gets `Source Type = Standard Change Pattern (Unvalidated)` and
`Source Ref = Pattern: SCL-nnn`, `confidence` capped at Low until the client confirms it. **A
library score never overrides something the prompt or an attached document actually states** —
same rule as mode 1, unchanged here.

## Building the workbook

Reuses the existing pipeline unmodified — this mode changes what feeds Step 3, not Steps 4–7:

1. Write `cia_input.json` (`reference/input-schema.md`) — `meta.client`/`meta.solution_scope` come
   straight from the batch's `client`/`scope` fields; `meta.go_live_date` from `goLive` if given
2. `python3 scripts/generate_cia.py cia_input.json --validate-only` until it reports zero hard
   errors
3. `python3 scripts/generate_cia.py cia_input.json -o "<Client> — Baseline CIA v0.1.xlsx"`

Expect a real warning list — High-rated rows with no `change_champion` or `comms_owner` is normal
on a first pass nobody has staffed yet. Per the existing rule in `SKILL.md`, these are left
standing and reported, not papered over: they're the client's agenda, not defects in the draft.

## Delivery

`.xlsx` cannot be offered as an in-page download — the `downloads` capability's allowlist has no
`xlsx` entry (base set `gif png jpg jpeg webp mp4 webm txt json md`; extended set adds
`docx pptx epub csv ttf html svg pdf`, still no xlsx), and the `assets` capability that would give
the page a hostable URL isn't available to this account. So:

1. **`SendUserFile`** — the actual workbook, into this chat. This is the deliverable.
2. Republish the artifact with the batch marked `processed`: `stats` (`{count, high, medium, low}`
   from the rating distribution), `workbookName`, and `csv` — the register as CSV, for a viewer
   who isn't in this chat to pull via the page's own "Download register" button (uses the
   `downloads` capability directly; degrades to a toast pointing back at the chat delivery if
   unavailable).
3. **Strip the batch's file blobs before republishing.** `files[].base64` has done its job once
   `ingest_sources.py` has read it; carrying it forward in `history` forever is how the artifact's
   16MB ceiling gets hit. Keep `files[].name` and `.size` for the history display, drop
   `.base64`. This is the same rule mode 1's Excel channel already follows for the same reason.

## Handover

Same shape as `SKILL.md` Step 8, adapted for a first pass rather than an evidence-linked
baseline: shape of the change (row count, rating distribution, which areas carry the weight), the
few things that matter most, training/comms load, and — the part that matters more here than
anywhere else in this skill — a clear, upfront statement that this is a draft built to start a
conversation, and the open questions in `notes` are literally the agenda for that conversation.
