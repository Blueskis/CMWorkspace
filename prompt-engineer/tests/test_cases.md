# Prompt Engineer — test cases

Plain-language input/expected pairs for the deterministic logic block (classifier,
question bank, prompt assembly). `run_tests.mjs` asserts each of these against the
`// ===== LOGIC START =====` / `// ===== LOGIC END =====` block in
`prompt-engineer.html`. DOM wiring and the `sample` calls are not covered here — they
are verified by hand in the published artifact.

The logic block exposes one global object, `PE`, with:

- `PE.ARCHETYPES` — the eight archetypes, `{id, label}`.
- `PE.classify(brief)` — returns `{archetype}` or `{error}`.
- `PE.getQuestions(archetypeId)` — returns the ordered question list for that archetype.
- `PE.assemble({archetypeId, brief, answers, aiAnswers})` — returns the assembled prompt
  string.

## Classification

1. `PE.classify("Write a comms email to staff about a system go-live")` →
   `{archetype: "write"}`.
2. `PE.classify("Pull the key risks out of this 40-page report")` →
   `{archetype: "summarize"}`.
3. `PE.classify("Should we run the pilot in one department or three?")` →
   `{archetype: "analyze"}`.
4. `PE.classify("Fix this Python script that keeps timing out")` →
   `{archetype: "code"}`.
5. `PE.classify("Explain what an API is to a non-technical audience")` →
   `{archetype: "teach"}`.
6. `PE.classify("asdfgh")` → `{archetype: "write"}` (fallback; no keyword match; must not
   throw).
7. `PE.classify("")` (and whitespace-only, e.g. `"   "`) → `{error: "empty"}`, an object
   carrying an `error` field and no `archetype` field, not a real archetype id.

## Question selection

8. For every id in `PE.ARCHETYPES`, `PE.getQuestions(id).length` is between 6 and 9
   inclusive, and the question ids within that list are all unique.
9. `PE.getQuestions("code")` and `PE.getQuestions("write")` contain at least one
   question id that is not present in the other's list (the archetype-specific
   questions differ).
10. Every question object returned by `PE.getQuestions(id)`, for every archetype, has a
    non-empty string `default` field (the default assumption shown to the viewer).

## Prompt assembly

Reinterpretation note: the plan says a block with no content is "omitted entirely
rather than left as an empty heading." This implementation resolves that rule as two
groups of blocks:

- **Always-shown blocks** (Role, Context, Output format, Constraints, Success
  criteria): every core question feeding them has a meaningful default assumption, so
  when skipped, the block is still shown with that default text substituted in. These
  blocks are never blank and never omitted.
- **Conditional blocks** (Inputs, Method): these only carry real content when the
  viewer (or Claude's tailored questions) actually supplies something — "no input" or
  "no special method" is not useful to print — so when every question feeding them is
  skipped, the whole block (heading included) is left out of the assembled prompt.

11. Answer every question for a given archetype (no skips) → the assembled prompt
    contains all eight block headings (`Role`, `Task`, `Context`, `Inputs`, `Method`,
    `Output format`, `Constraints`, `Success criteria`), each followed by non-empty
    text, in that fixed order.
12. Skip every optional question (submit only the brief) → `PE.assemble` still returns
    a non-empty, well-formed prompt: the always-shown blocks appear with their default
    text substituted in, and no block heading is followed by empty content.
13. Skip every question that feeds the Inputs block and every question that feeds the
    Method block (for an archetype whose Method question is skipped), leaving other
    questions answered → the assembled prompt has no `Inputs` heading and no `Method`
    heading at all (not a heading with blank or default filler beneath it).
14. An answer containing markdown syntax and backticks (e.g. `` "Use **bold** and `code`
    spans, and a\nnewline" ``) appears in the assembled prompt byte-for-byte, not
    escaped, re-encoded, or corrupted by any Markdown-to-HTML step.
15. A brief built from a 5000-character repeating sentence, assembled with
    `PE.assemble`, appears in the Task block in full and unmodified — the implementation
    performs no truncation at any length, so nothing is ever cut mid-sentence.
16. Calling `PE.assemble` twice with byte-identical arguments (deep-equal objects, no
    shared mutable references) returns byte-identical strings both times.
17. `PE.assemble` called with `aiAnswers` omitted (`undefined`, standing in for
    `sample` being unavailable) still returns a complete, non-empty prompt built only
    from the static answers.
18. `PE.assemble` called with `aiAnswers: {context: ["a tailored context line"],
    constraints: ["a tailored constraint line"]}` produces a prompt where the static
    Context and Constraints content is still present *and* both tailored lines appear
    inside their respective blocks — the tailored lines only ever append, they never
    replace or remove the static content.
