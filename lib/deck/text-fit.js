/**
 * Shared text-fit math: how many lines a string wraps to at a given font size in a given
 * box width, and the largest font size (from a caller-supplied list) whose resulting
 * height still fits a box.
 *
 * Extracted out of render-diagram.js so build-pptx.js's body-text sizing (composeSlide's
 * narrowed columns need this exactly as much as a diagram label does) doesn't reimplement
 * the same approximation with its own, inevitably-drifting constants. render-diagram.js
 * still owns its own FONT_SIZES range (8-14pt, diagram labels tolerate small text) and its
 * own overflow-vs-warn policy — only the arithmetic underneath both is shared here.
 */

export const PT_PER_INCH = 72;
export const CHAR_WIDTH_FACTOR = 0.52; // average glyph width as a fraction of font size
export const LINE_HEIGHT_FACTOR = 1.25;

/** How many wrapped lines `text` needs at `fontPt` inside a box `boxWIn` inches wide. */
export function linesNeeded(text, boxWIn, fontPt, charWidthFactor = CHAR_WIDTH_FACTOR) {
  const charsPerLine = Math.max(1, Math.floor((boxWIn * PT_PER_INCH) / (fontPt * charWidthFactor)));
  return Math.max(1, Math.ceil(String(text).length / charsPerLine));
}

/** Vertical space `lines` lines of `fontPt` text occupy, in inches. */
export function textHeightIn(lines, fontPt) {
  return (lines * fontPt * LINE_HEIGHT_FACTOR) / PT_PER_INCH;
}

/**
 * Try `sizes` (any order, normally descending) against `totalLinesAt(pt) -> lineCount`.
 * Returns the largest size whose text height fits `boxHIn`, or null if none do — caller
 * decides whether "none fit" throws (diagram label) or warns and ships at the smallest
 * size (body text). Kept generic so a single-string label and a multi-bullet body can
 * share it: `totalLinesAt` is the caller's own line-counting closure over its own text.
 */
export function fitFontSize(totalLinesAt, boxHIn, sizes) {
  for (const size of sizes) {
    if (textHeightIn(totalLinesAt(size), size) <= boxHIn) return size;
  }
  return null;
}
