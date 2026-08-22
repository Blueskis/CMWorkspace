# Extraction guide — getting the key right

Diffing is matching, and matching is only as good as the item key. Everything else in this
skill degrades gracefully; a bad key does not. Key a training tracker on the row number
instead of the learner and inserting one row at the top reports the whole sheet as changed.

`extract.py` picks keys automatically. This is what it does, when it gets it wrong, and
what to do about it.

## What the extractor keys on

| Source | Item | Key |
|---|---|---|
| `.xlsx` sheet, `.csv` | one data row | first column whose header matches a key hint, else the first populated column |
| `.docx` heading | the heading and the prose under it | the heading text |
| `.docx` / `.pptx` table | one data row | as for a sheet |
| `.pptx` slide | title plus prose that isn't a metric or an object line | the slide title |
| `.pptx` bullet starting with an object ID | that object | the object ID |

Key hints, best first: RICEFW/RICEFWA/WRICEF · deliverable ID, activity ID, task ID, item
ID, ID, ref · employee, learner, participant, attendee, user · course, curriculum, module ·
activity, deliverable, task, milestone, workstream, name, title.

Duplicate keys get `#2`, `#3` suffixes in sheet order. That's a fallback, not a feature — a
sheet with duplicate keys will mis-match if the rows reorder. Say so rather than hiding it.

## Object bullets on a status deck

A bullet like `FI-R-014 Payment run report - In Build - amber` becomes an item in its own
right, keyed `object:fi-r-014`, with `Description`, `Status` and `RAG` fields. Trailing
segments (split on ` - `, ` – ` or ` | `) are read as RAG if they're a RAG word, as Status
if they contain a status word, and as a `Note` otherwise.

This is what lets a RICEFWA deck be tracked object by object even though the slides get
re-titled and re-ordered every week. It needs the ID at the **start** of the bullet, in a
form like `FI-R-014`, `LO-W-011`, `MM_I_003`. If the deck's convention differs, say so
before running — don't quietly accept slide-level text diffs and call it object tracking.

A short `Label: value` bullet (`Build complete: 24`) becomes a field on the slide item
rather than prose, so headline counts diff as numbers.

## Checking the key before you trust the diff

After extracting both periods, always run the sanity check in Stage 1 of SKILL.md: if the
diff reports a large number of additions and removals and few field changes, the key is
wrong. Common causes and fixes:

- **A tracker keyed on a name that changed spelling** ("A. Okafor" → "Amara Okafor"). The
  second-pass similarity matcher usually catches this and reports a rename. If it doesn't,
  fix it in the source or add the previous name.
- **A plan whose headings were reworded.** Same mechanism, `section:` keys. A heading
  rewrite that also rewrites the prose won't pair — report it as one section removed and
  one added, which is honest.
- **A sheet whose ID column was added this week.** Last week's snapshot keyed on activity
  name, this week's on activity ID; nothing matches. Re-extract last week's document with
  the same column present, or accept a one-off full-reset diff and say so in the update.

## Formats

Open XML only: `.xlsx`, `.xlsm`, `.docx`, `.pptx`, plus `.csv`. Legacy `.doc`, `.xls` and
`.ppt` must be resaved first. PDFs aren't supported — a status report that only exists as
a PDF can be read with the `pdf` skill, but it won't diff structurally, and a text-only
comparison is worth being explicit about rather than passing off as the same thing.

Charts, images, tracked changes, comments, speaker notes and cell formatting (including
colour-as-RAG) are **not** read. If a programme signals RAG by cell fill rather than a
word, this skill cannot see it — say so; don't guess from the numbers.
