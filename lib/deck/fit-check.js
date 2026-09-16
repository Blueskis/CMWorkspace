/**
 * Plan-time fit and variety gates — the mechanical checks behind "almost as good as a
 * human built it, minus review": the three defects that give a deck away as AI-made are
 * a repeated layout, text overflowing its box, and content ignoring the template's own
 * picture slots. All three are checkable before a single slide is assembled, so they are
 * hard failures here rather than something visual QA discovers after the fact.
 *
 * Reuses text-fit.js's line-wrap arithmetic (the same estimate build-pptx.js's
 * composeSlide uses to size body text) so a "fits" verdict here means the same thing it
 * means at build time — no second, drifting definition of fit.
 */

import { linesNeeded, textHeightIn, fitFontSize } from "./text-fit.js";

// Never shrink body text below this to make something fit — a plan that only fits at an
// illegible size is a content problem (cut copy, split the slide), not a sizing one.
export const MIN_BODY_PT = 12;
export const BODY_SIZES = [16, 15, 14, 13, MIN_BODY_PT];
export const TITLE_MIN_PT = 24;
export const MAX_CONSECUTIVE_SAME_LAYOUT = 2;

/**
 * Check one text block against its resolved placeholder box.
 * Returns { ok, fontPt, lines, overflowIn } — ok=false is a hard failure; a title that
 * wraps to 2 lines but still fits vertically is reported via `wrapped: true`, not failed.
 */
export function checkTextFit(text, boxWIn, boxHIn, { sizes = BODY_SIZES, isTitle = false } = {}) {
  const totalLinesAt = (pt) => linesNeeded(String(text), boxWIn, pt);
  const fontPt = fitFontSize(totalLinesAt, boxHIn, sizes);
  if (fontPt == null) {
    const smallest = sizes[sizes.length - 1];
    const lines = totalLinesAt(smallest);
    const neededIn = textHeightIn(lines, smallest);
    return { ok: false, fontPt: smallest, lines, overflowIn: +(neededIn - boxHIn).toFixed(2), wrapped: lines > 1 };
  }
  const lines = totalLinesAt(fontPt);
  return { ok: true, fontPt, lines, overflowIn: 0, wrapped: isTitle && lines > 1 };
}

/**
 * Check every text block in a sequenced build manifest (the same `steps[].fills[]` shape
 * build_training_deck.py / build-pptx.js's composeSlide consume) against its bbox.
 * Returns { failures: [...], warnings: [...] } — never mutates the manifest; a caller
 * decides whether to shrink, split, or shorten.
 */
export function checkManifestFit(steps) {
  const failures = [];
  const warnings = [];
  for (const step of steps) {
    for (const fill of step.fills ?? []) {
      if (fill.kind !== "text" || !fill.bbox || fill.gap) continue;
      const [, , w, h] = fill.bbox;
      const isTitle = fill.placeholder === "title" || fill.placeholder === "ctrTitle";
      const text = typeof fill.content === "string" ? fill.content : (fill.content?.bullets ?? []).join(" ");
      if (!text) continue;
      const result = checkTextFit(text, w, h, { sizes: isTitle ? [40, 36, 32, TITLE_MIN_PT] : BODY_SIZES, isTitle });
      if (!result.ok) {
        failures.push({
          slide_id: step.slide_id, placeholder: fill.placeholder,
          message: `text overflows its placeholder by ${result.overflowIn}in even at ${result.fontPt}pt — cut the copy or split the slide, never ship it cut off`,
        });
      } else if (result.wrapped) {
        warnings.push({ slide_id: step.slide_id, placeholder: fill.placeholder, message: "title wraps to two lines — consider shortening" });
      }
    }
  }
  return { failures, warnings };
}

/**
 * Variety gate: no more than MAX_CONSECUTIVE_SAME_LAYOUT slides in a row on one layout,
 * and (warning only) any picture-capable layout the template offers that the plan never
 * uses at all — the two most common tells of an unreviewed AI deck.
 */
export function checkVariety(steps, { pictureCapableLayoutParts = [] } = {}) {
  const failures = [];
  const warnings = [];
  let run = { part: null, start: 0, count: 0 };
  const flush = (endIdx) => {
    if (run.part && run.count > MAX_CONSECUTIVE_SAME_LAYOUT) {
      failures.push({
        message: `${run.count} consecutive slides (positions ${run.start}-${endIdx}) use the same layout '${run.part}' — vary layouts; never more than ${MAX_CONSECUTIVE_SAME_LAYOUT} in a row`,
      });
    }
  };
  steps.forEach((step, i) => {
    const part = step.layout_part;
    if (part === run.part) {
      run.count += 1;
    } else {
      flush(steps[i - 1]?.position ?? i);
      run = { part, start: step.position ?? i + 1, count: 1 };
    }
  });
  flush(steps[steps.length - 1]?.position ?? steps.length);

  if (pictureCapableLayoutParts.length) {
    const used = new Set(steps.map((s) => s.layout_part));
    const unused = pictureCapableLayoutParts.filter((p) => !used.has(p));
    if (unused.length && pictureCapableLayoutParts.some((p) => used.has(p)) === false) {
      warnings.push({ message: `the template offers a picture-capable layout this plan never uses: ${unused.join(", ")}` });
    }
  }
  return { failures, warnings };
}
