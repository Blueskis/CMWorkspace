# FSD Extraction Guide

What `map_source.py` and Stage 1 pull out of a functional specification document (or
FSD-like input), and what these documents habitually bury. Read this alongside
`map_source.py`'s own docstring, which covers the mechanics; this covers judgement.

## What `map_source.py` gives you automatically

A complete section outline (`source_map.json`), each section classified as `procedure |
reference | narrative | config | non-functional` by a cheap heuristic (numbered steps and
action verbs → procedure; field/attribute/mandatory language → reference; configuration
vocabulary → config; performance/security/SLA language → non-functional; everything else →
narrative). **This classifier errs toward calling a section `procedure` when ambiguous**,
because that's the classification Stage 5 enforces coverage on — a false positive costs a
review; a false negative costs a silently-uncovered task.

Always spot-check the classification before planning Stage 2 around it. It's cheap and
wrong classifications are common in FSDs that mix narrative and instruction in the same
paragraph.

## Where FSDs bury the things training actually needs

1. **Role/permission matrices, often in an appendix or a table far from the procedure
   they govern.** A step that reads "the approver reviews the request" is meaningless for
   training until you've found the table defining who counts as "the approver" at each
   threshold. Read appendices before finalizing `training_brief.json`'s `audiences[]`.

2. **Exception and error-state behaviour, usually in a separate subsection or scattered
   as footnotes to the happy-path procedure.** These are exactly what module 9
   ("Exceptions and common errors") needs and exactly what's easiest to miss on a single
   read-through.

3. **Field-level validation rules inside what looks like a pure reference table** — a
   "mandatory" column, a format constraint, a cross-field dependency ("Amount is required
   if Category = Capital"). These belong in the procedure they gate, not just the
   reference appendix; cite the reference section but teach the rule at the point of use.

4. **Screenshots without adjacent captions.** `extract_assets.py` looks at the paragraph
   *following* an image for a caption candidate, since that's where FSD authors typically
   put "Figure N: ..." — but confirm by eye; some documents caption above, and some don't
   caption at all, leaving only a `nearest_heading` to go on.

5. **Versioned or superseded content.** An FSD revised in place sometimes leaves an old
   screenshot or an old field name uncorrected in a table while the procedure text was
   updated. If a screenshot's visible field names don't match the surrounding prose,
   flag it rather than trusting either silently — this is the single most common
   after-the-fact correction the `training-qa-agent` skill's system-training lens exists
   to catch, but it's cheaper to catch here, before the deck is built.

6. **Conditional/branching logic written as prose ("if the amount exceeds $10,000...")
   rather than a table.** This is exactly what the `decision` diagram type in
   `reference/diagram-patterns.md` is for — pull every "if X then Y" sentence out during
   Stage 1/2 rather than leaving it as a wall of text a learner has to parse under time
   pressure.

## Confidence and gaps

Same discipline as `cm-proposal-generator`'s RFP extraction: never invent a procedure,
field, or rule the source documents don't state, and never soften a stated mandatory/
optional distinction. Where a learning objective's scope is genuinely ambiguous in the
source, record it as such rather than guessing — an LO with an unclear boundary is better
caught at Stage 1 than discovered as a wrong slide at Stage 5.

Where the FSD asks nothing (no `procedure` sections at all, or a role clearly used in the
system but never documented), that surfaces as a `[GAP]` downstream. Report it plainly
rather than filling it with plausible-sounding invented process — see SKILL.md's "the
source documents are the product" note.

## Multiple input documents

A run can take more than one document — an FSD plus an addendum, plus a glossary, plus a
UI style guide. `map_source.py` assigns each a distinct `document_id` and every section a
document-qualified `section_id` (`fsd#4.2.1`, `addendum#2.1`), so cross-references stay
unambiguous. When two documents disagree (an addendum changing a threshold the base FSD
still states), the later/more specific document wins for teaching purposes — but note the
discrepancy in `training_brief.json` rather than silently picking one, since it may be a
real error worth flagging back to the client.
