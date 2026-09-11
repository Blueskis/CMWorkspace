# Prompt Engineer

A single-file HTML Artifact. The viewer describes what they want an AI to do, answers a
short set of optional clarifying questions, and gets back one ready-to-paste prompt with
a copy button. It is generic: nothing in it is specific to change management or any
other discipline.

## What it does

Three screens on one page:

1. **Brief.** One textarea: what do you want the AI to do? A deterministic keyword
   classifier reads it and picks one of eight task archetypes (Write/Draft,
   Summarize/Extract, Analyse/Decide, Research, Rewrite/Edit, Code/Build, Brainstorm,
   Teach/Explain), shown as a chip the viewer can override from a dropdown.
2. **Clarify.** Six core questions plus three archetype-specific ones, all optional,
   each showing the default assumption used if skipped. If the `sample` capability is
   available and the viewer asks for it, two tailored follow-up questions from Claude
   appear beneath the static ones.
3. **Prompt.** The assembled prompt in a monospace block with a copy button, an
   optional "Polish with Claude" pass, and a back button that returns to Clarify with
   every answer intact.

**Hybrid engine.** The deterministic form (classification, question bank, prompt
assembly) always works with no network calls. When the `sample` capability resolves and
the viewer explicitly asks, the page also calls Claude for tailored questions and an
optional final polish. If `sample` is unavailable or the viewer declines, a quiet
banner says tailored questions are off; nothing else changes and the tool still
produces a complete prompt.

**No persistence.** Nothing is saved, shared, or sent anywhere except the two explicit,
opt-in Claude calls described above. Refreshing the page starts over.

## Files

```
prompt-engineer/
├── prompt-engineer.html      # the artifact: logic block, styling, DOM wiring
├── tests/
│   ├── test_cases.md         # plain-language input/expected pairs (18 cases from the plan)
│   └── run_tests.mjs         # Node stdlib test runner
└── README.md                 # this file
```

## Running the tests

The pure logic (classifier, question selection, prompt assembly) lives in one
`<script>` block in `prompt-engineer.html`, bracketed by
`// ===== LOGIC START =====` / `// ===== LOGIC END =====` markers, and exposes its
functions on one global object, `PE`. `run_tests.mjs` reads the HTML file, slices out
that block, evaluates it with `node:vm`, and asserts against it. No dependencies, no
build step:

```bash
node prompt-engineer/tests/run_tests.mjs
```

A green run prints `19 passed, 0 failed`. DOM wiring and the `sample` calls sit in a
separate, un-tested `<script>` block and are verified by hand in the published
artifact (see Verification below).

## Republishing

This file is meant to be published as a Claude Artifact with the `sample` capability
declared (`capabilities: { sample: {} }`). To republish after an edit, use the
Artifact tool against the same artifact URL so the link stays stable; do not create a
new artifact for a routine update.

## Manual verification checklist

Because the DOM and `sample` layers are not unit tested, check these by hand in the
published artifact after any change:

- Run one real brief end to end and confirm the copy button puts the right text on the
  clipboard.
- Decline the Claude consent prompt on a fresh load (or use a view where `sample` is
  unavailable). Confirm the quiet banner appears and a complete prompt still generates.
- Check the page at roughly 400px width: no horizontal scroll.
- Check both light and dark theme.
- Paste a generated prompt into Claude and confirm the response matches the requested
  format.
