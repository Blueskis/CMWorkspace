# Test cases — deck-builder

Plain-language input/expected-output pairs, confirm before implementation.
Each case names which layer it exercises: [brand] [layout] [fit] [variety] [vision]
[retrieval] [deck-type] [assemble] [negative].

## Brand intake

1. [brand] Given a client `.potx` with a defined theme (accent1..6 set, major/minor
   fonts named), running brand extraction produces a profile with `source:
   "extracted-from-template"`, non-empty `colors.*`, and `typography.headingFont` /
   `bodyFont` matching the theme's major/minor fonts.
2. [brand] Given a Brand Vault export JSON, converting it produces a profile passing
   the canonical schema, with `voice`, `messaging.terminology`, and `logo.dataUri`
   carried over unchanged.
3. [brand] Given a profile JSON with `approval` empty or missing, any script that
   reads it exits non-zero and says "no approver — stop", rather than proceeding
   with defaults.
4. [brand] Given a profile whose `palette.primary`/`ink` pair fails the contrast
   floor CLAUDE.md-equivalent check for the deck producer, the run reports the
   specific pair and ratio, and does not silently pick different colours.
5. [brand] Given a profile keyed in by hand via a form (no file), the same schema
   validates it identically to a file-derived one — no separate code path.

## Layout mapping

6. [layout] For each of the six fixtures in
   `webapp/test/fixtures/templates/` (minimal, no-picture, odd-idx, two-masters,
   with-examples, real-training-template), every role in the widened `ROLES` list
   that the template can support resolves to a real layout; roles it cannot
   support are reported as unsupported, not silently dropped or guessed.
7. [layout] `no-picture` never assigns the `picture` role; a plan that puts an
   image block in it fails at plan time with a named reason.
8. [layout] `two-masters` picks placeholders from one master consistently across
   all resolved roles in a single run — never mixes masters mid-deck.
9. [layout] `odd-idx` (non-sequential placeholder idx values) still resolves every
   role — proves lookup is by idx/type/name value, not position.
10. [layout] The mapping produced for any fixture is inspectable JSON a caller can
    override per-role before build; overriding one role leaves the rest of the
    proposed mapping untouched.

## Fit

11. [fit] A bullet list that would overflow its resolved placeholder at the
    smallest acceptable body size is a hard plan-time failure naming the slide
    and the overflow amount — never auto-shrunk below the floor to make it fit.
12. [fit] A title that wraps to two lines is reported as a warning (not a
    failure) so a human can shorten it.
13. [fit] The same text against the same box size produces the same fit
    verdict whether checked from the JS path or the Python path (parity).

## Variety

14. [variety] A plan with three consecutive slides on the same layout fails
    plan-time validation naming the offending slide range.
15. [variety] A plan alternating two layouts across ten slides passes.
16. [variety] On a template offering a picture-capable layout, a plan that never
    uses it produces a warning (not a failure) naming the unused layout.

## Vision

17. [vision] A PDF page containing only a BPMN-style process diagram (no
    extractable body text) produces one `vision_notes.json` entry with
    `kind: "diagram"`, a non-empty `transcription`, and `source_ref` pointing at
    that page.
18. [vision] A slide block whose `sources` contains that note's `note_id` passes
    the provenance gate exactly as a text-chunk citation would.
19. [vision] A vision note with `confidence: "low"` cannot be the *only* source
    for a claim marked non-`gap` — the plan-time gate flags it for a supporting
    text source or an explicit `gap`.
20. [vision] Rasterising a 3-page PDF via the pdf.js-based rasteriser produces
    exactly 3 PNGs, matching page order, with no `pdftoppm`/poppler dependency
    invoked.

## Retrieval

21. [retrieval] Given a shared fixture chunk index, a query run through the JS
    BM25 implementation and the Python implementation returns the same
    ranked `chunk_id` order (parity test).
22. [retrieval] A query using a synonym present only in the brand profile's
    `messaging.terminology` map (not in the source text) retrieves the chunk
    that uses the client's own term, via query expansion.
23. [retrieval] `--section` scoping excludes chunks from sibling sections even
    when they'd otherwise outscore the in-scope ones.
24. [retrieval] A vision-derived chunk (`origin: "vision"`) is retrievable by a
    query matching its transcription text, and is distinguishable in results
    from a `origin: "prose"` chunk.
25. [retrieval] Expansion only adds candidates to the result set; it never
    causes a chunk matching the literal query to drop out of the top-k (RRF
    fusion check).

## Deck types

26. [deck-type] Each entry in the deck-type registry validates: its required
    role sequence is non-empty and every role it lists exists in the shared
    `ROLES` vocabulary.
27. [deck-type] A plan for `status-update` missing a required role (e.g. no
    `metric-row`) fails plan validation naming the missing role.
28. [deck-type] Requesting an unknown deck type (e.g. `"webinar"`) is rejected
    with a list of valid types — never silently defaulted to a close match.

## Assembly

29. [assemble] Building a manifest with one image block produces a `.pptx` where
    the media part, the relationship, and the `<p:pic>` all exist — verified by
    unzipping the output, never partially written.
30. [assemble] A diagram block's injected shape ids are all greater than the
    target slide's pre-existing maximum shape id.
31. [assemble] The template's own example/placeholder slides are absent from the
    built output; only slides generated from the plan remain.
32. [assemble] Every content slide in the manifest that carries `speaker_notes`
    has them present in the built deck's notes part, readable via the same
    zip-and-parse check.
33. [assemble] The built `.pptx` opens with zero errors under the pptx skill's
    `validate.py --original <template>`.

## Negative / guardrail

34. [negative] Running intake with no template supplied stops with an explicit
    "no approved template — cannot proceed" message; it does not fall back to
    building an unapproved lookalike.
35. [negative] A plan block with neither a non-empty `sources[]` nor `gap: true`
    fails validation — "no third state" — naming the offending block.
36. [negative] `markitdown <built deck> | grep -iE "\bx{3,}\b|lorem|\[insert|TODO"`
    returns no matches on a deck built from a template containing placeholder
    text like "XXXX" or "[Insert client name]" — proving the fill actually
    replaced it rather than leaving it untouched.
37. [negative] A `redact` annotation pointed at an asset lacking
    `redacted_from` in `asset_index.json` is a hard plan-time error, not a
    warning (the annotation is a vector shape; the un-flattened original pixels
    would still ship).
