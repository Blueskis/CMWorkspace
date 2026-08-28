# Reading a functional specification

What to pull out at Stage 1, and what specifications habitually bury.

`ingest_docs.py` does the mechanical part — chunks, tables, images, anchors. This file is
about the judgement: what those chunks mean, what to look for that the script cannot see,
and what to correct before Stage 2.

## The anchor is the contract

Every citation anywhere downstream is an anchor from the source index: `POFSD#5.1`,
`POFSD#4.2@p17`. Two consequences worth internalising:

- **Cite the clause, not the document.** `FSD#5.1` is checkable in seconds; "the FSD" is not.
  The whole provenance guarantee rests on a reviewer being able to open the spec at the right
  place.
- **A numbered clause makes a better anchor than a heading slug**, because numbered clauses
  survive rewording and re-issue. The ingester prefers the number when the heading carries
  one, which is why `4.2 Field rules` becomes `POFSD#4.2` rather than `POFSD#field-rules`.

## What to read out of the document

**The process, before the screens.** Usually an overview or lifecycle section near the front.
This is what `process-context` is built from, and it is the part most likely to be thin —
specifications are written for builders who already know the process.

**States and transitions.** A status list, a lifecycle table, or prose describing what moves
a record from one state to the next. Prime material for a `state-transition` diagram, and the
thing learners most often get wrong in the system.

**Screens and their fields.** Each screen the audience operates, its route through the menus,
and the field-level rules. Field rules almost always live in a table with a Mandatory column —
which is exactly why tables are kept as rows rather than flattened to prose.

**Business rules and validations.** Frequently scattered: some in the field table, some in a
"business rules" subsection, some as a sentence in the middle of a screen description.
Collect them all. Reproduce thresholds and messages verbatim.

**Exception paths.** Usually last in a chapter, often thin. These are what people hit under
pressure and they are consistently the least well trained.

**Downstream effects.** Postings, interfaces, overnight jobs. Makes learners careful.

**The release or build.** Sometimes only in the document properties or a revision table. Get
it — training that does not say which build it describes cannot be judged stale later.

## What specifications habitually bury

- **The rule that lives in one sentence in a screen description**, not in the rules section.
  "The system runs a budget check on submission, not on save" is a sentence in the middle of a
  paragraph about the Create screen, and it is the single most useful thing on the slide.
- **Negative permissions.** Specs say what a role can do. What it *cannot* do is implied, and
  it is the column learners actually need. Derive it, cite the permission text you derived it
  from, and flag it if the derivation is not certain.
- **The thing that changed.** Revision tables say "Approval thresholds updated for R3" without
  saying what they were before. If the audience is being retrained, that delta is the most
  valuable content in the document — and often the only place it exists.
- **Cross-references to documents you do not have.** "As described in the Security Design" is a
  hole, not a coverage. Record the topic and mark it a `[GAP]` rather than glossing over it.
- **"To be confirmed" and "TBC".** Search for them explicitly. A TBC in a spec becomes an
  invented rule in a deck if nobody notices.

## Correcting the ingest before Stage 2

Read the ingest summary and fix these before planning:

**Asset classification.** The script guesses from captions, alt text, dimensions and
repetition. It gets logos and screenshots right most of the time and is weakest on mid-sized
images with no caption, which come out `unknown`. Only `screenshot`, `diagram` and `chart` can
be placed on a slide or are subject to Stage 5's triage check, so an image misfiled as `icon`
disappears silently. Look at any `unknown` and reclassify.

**Topic scope.** Revision history, document control and sign-off tables are ruled out
automatically. Check nothing teachable was caught by that, and rule out anything else that is
document furniture — an appendix of database field names is not a topic.

**Heading structure.** If a specification uses manual numbering rather than heading styles,
the chunks will be coarse and the anchors will be slugs rather than clause numbers. Usable,
but say so: citations will be less precise, which matters at review time.

## Formats

| Format | Text | Tables | Images | Notes |
|---|---|---|---|---|
| `.docx` | yes | yes, as rows | yes, original bytes | The best case. Captions, alt text and heading context all survive. |
| `.xlsx` | sheet summary | yes, per sheet | yes | Each worksheet becomes one chunk carrying one table. |
| `.txt` / `.md` | yes, on headings | no | no | Fine for pasted extracts. |
| `.pdf` | via the `pdf` skill, as `.txt` | no | **no** | The index records `images_extracted: false`. Say at handover that its images were never looked at. |

A PDF-only specification is a real limitation, not a formality: the screenshots are the part
of an FSD this skill is most useful for, and in a PDF they are out of reach in v0.1. Ask for
the `.docx` if one exists — it usually does.
