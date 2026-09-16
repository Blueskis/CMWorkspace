# Visual QA

`qa_deck.py` automates everything that can be checked mechanically — plan validation,
the pptx skill's `office/validate.py --original`, and a `markitdown` sweep for leftover
placeholder text. It does not, and cannot, replace looking at the rendered slides.

```bash
soffice --headless --convert-to pdf decks/<run>/deck.pptx
node lib/deck/cli/rasterise.mjs decks/<run>/deck.pdf -o decks/<run>/slides/
```

Then look at every slide image (a subagent works well for this — after staring at the
plan JSON you tend to see what you expect rather than what rendered). Check, in order:

1. **Text overflow or cut-off at a box or slide boundary** — the most common defect and
   always user-visible, even though `plan_deck.py`'s fit gate should have caught it before
   assembly. Check anyway: the gate checks the box geometry, not what the template's own
   theme font actually renders at (LibreOffice substitutes fonts it lacks).
2. Overlapping elements, low-contrast text, insufficient margins, uneven gaps — the same
   checklist the `pptx` skill's own visual QA section uses.
3. **Layout variety** — confirm by eye that the plan-time variety gate's verdict matches
   what you see; a false negative there (missed repetition) is the failure mode most worth
   a second look.
4. Template decoration mispositioned after content changed the wrap of a title or body.

Fix, re-render only the changed slides, stop. This deck is a first draft for practitioner
review — say so on handover, never present it as client-ready.
