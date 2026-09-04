# Test list: route_channels.py and qa_comms.py

Plain-language input/expected-output pairs, written before implementation per TDD.

## route_channels.py — validates comms_plan.json against channel_registry.json, emits build manifest

1. **Happy path.** A plan whose every channel_run references a channel_id present in the
   registry, at status "live" or "planned" → manifest lists one build step per channel_run,
   grouped by producer (docx / pptx / canva-doc / canva-poster / narration-spec). Exit 0.
2. **Unknown channel_id.** A channel_run references "sms" (not in the registry) → error
   naming the run_id and the unknown channel_id, listing valid ids. Exit 1. No manifest written.
3. **Registry version mismatch.** Plan's `registry_version` field doesn't match the
   registry's actual `version` → refuses to build, error names both versions. Exit 1.
   (Plan's plain-English requirement: "route_channels.py refuses to build against a
   mismatched registry version.")
4. **Planned channel routed correctly.** A channel_run for `short_form_video` or
   `explainer_video` → manifest step says "narration-spec", not "build file", and the
   manifest note states no rendered video exists yet. Exit 0 (not an error — planned is a
   valid status, not a defect).
5. **Banner routed with the copy-to-paste caveat.** A channel_run for `banner` → manifest
   step is producer "canva-poster" and carries a `note` field restating that verbatim is
   ignored and QA'd copy must be pasted by hand (pulled from channel_registry.json's own
   constraints.note, not re-authored ad hoc).
6. **Newsletter routed with verbatim.** A channel_run for `newsletter` → manifest step is
   producer "canva-doc" with `verbatim: true` set in the step's params.
7. **Empty comms_plan (no channel_runs).** → manifest is `{"steps": []}`, no crash, exit 0
   with a warning printed to stderr that nothing will be built.
8. **Missing required schema field on a channel_run** (e.g. no `blocks` key at all) →
   reported as a structural error naming the run_id, distinct from an unknown-channel
   error. Exit 1.

## qa_comms.py — five checks, writes qa_report.md, exits non-zero on hard failure

9. **Full coverage, full provenance, consistent dates → PASS.** A brief with 2 audiences,
   6 mandatory messages each, a plan whose channel_runs cover every M x A pair with every
   block sourced, and every date/figure across channels matching → report says "PASS", exit 0.
10. **Uncovered mandatory M x A pair.** Audience A2 has mandatory message M3 assigned, but
    no channel_run for A2 carries M3 in its `message_ids` → reported under "Message x
    audience coverage" naming M3/A2. Exit 1 (hard failure, mirrors qa_deck.py's uncovered
    mandatory requirement).
11. **Non-mandatory message not covered.** M7 has `mandatory: false` and is uncovered →
    NOT a failure, listed informationally only (mirrors "desirable" requirement in
    qa_deck.py). Exit 0 if this is the only issue.
12. **Block missing both sources and gap.** A block has `sources: []` and no `gap` key →
    hard failure, same wording pattern as qa_deck.py's "content blocks with neither
    sources nor a [GAP] marker". Exit 1.
13. **Block correctly marked gap: true with gap_note.** → NOT a provenance failure. Appears
    in the "Open gaps" section as an action item, same as qa_deck.py's gap list. Exit 0 if
    the only thing present.
14. **gap: true but missing gap_note.** → schema violation, hard failure distinct from
    the missing-provenance case ("gap declared without a gap_note").
15. **Mandatory-field presence per draft — a message extracted at Stage 1 never made it
    into any block.** M4 (kind: "help", mandatory: true) exists in change_brief.json but
    no channel_run's `message_ids` contains M4 anywhere → reported as "message extracted
    but never drafted into any channel", distinct wording from the coverage-matrix
    failure (#10), since this is "brief said it, nothing built it" vs "matrix said reach
    it, nothing reached it". Exit 1.
16. **Channel constraint compliance — email subject over 50 chars.** A `subject` block's
    content string is 62 characters → reported under "Channel constraint compliance"
    naming the run_id, the limit (50), and the actual length (62). Exit 1.
17. **Channel constraint compliance — briefing_deck over 12 slides.** Count of blocks with
    `kind: "heading"` (one per slide) exceeds 12 → same pattern, reported, exit 1.
18. **Channel constraint compliance — within limits.** All constraints respected → no
    entries in that section, contributes to exit 0.
19. **Cross-channel consistency — SAME date, different formats, must be treated as
    equal.** Email says "14 September 2026", banner says "14/09/2026" → the check
    normalizes and does NOT flag this as a conflict.
20. **Cross-channel consistency — genuinely different dates for the same T id.** Email's
    block cites T1 ("14 September") but a briefing_deck block also citing T1 in its
    content states "15 September" → flagged as a hard failure naming both channel_runs,
    the two values, and T1. Exit 1. (This is the check the plan calls out as "no existing
    script does this" — must actually fire on a deliberately broken fixture.)
21. **Cross-channel consistency — SAME figure, different formatting, must be treated as
    equal.** "2,400" in one block vs "2400" in another, both sourced to the same message
    → NOT flagged.
22. **Cross-channel consistency — genuinely different figures.** "2,400" in the email vs
    "2,000" in the article, same message id as source → flagged as a hard failure naming
    both run_ids and both values. Exit 1.
23. **Cross-channel consistency — unconfirmed date reaching a channel unmarked.** T2 has
    `confirmed: false` in change_brief.json; a banner block states T2's date as if
    settled, with no qualifying language ("provisional", "subject to change", a "?") →
    flagged separately from #20 as "unconfirmed date presented as settled", naming the
    channel_run and T id. This is the specific failure mode channel_registry.json's
    `article.must_never_carry` calls out. Exit 1.
24. **Report structure.** Regardless of pass/fail, qa_report.md always contains the five
    named sections in order (Message x audience coverage / Provenance / Mandatory-field
    presence / Channel constraint compliance / Cross-channel consistency), a Status line
    (PASS or FAIL), and a Handover section with the "first draft for practitioner review"
    language, matching qa_deck.py's closing convention.
25. **CLI contract.** `qa_comms.py change_brief.json comms_plan.json -o qa_report.md`
    writes the file and prints a one-line summary to stdout (coverage count, gap count,
    consistency-conflict count), matching qa_deck.py's `print()` pattern at the end of
    `main()`.
