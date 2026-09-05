/**
 * Unit tests for splitSharedRect — the pure rect math composeSlide uses to divide one
 * shared placeholder/fullBleed rect between 2+ blocks that collided under the old
 * per-block resolveSlot. No HTML/JSZip involved; build-matrix.mjs's overlap check is the
 * end-to-end guard, this is the arithmetic underneath it.
 *
 *   node test/compose-slide.mjs
 */
import {
  splitSharedRect, GUTTER_IN, MIN_COL_W_IN, MIN_SPLIT_W_IN, PORTRAIT_ASPECT, WIDE_ASPECT,
  MEDIA_COL_FRAC, PORTRAIT_MEDIA_COL_FRAC, STACK_TEXT_FRAC, CAPTION_STRIP_H_IN, BLOCK_GAP_IN,
} from "../src/build-pptx.js";

let failures = 0;
function check(label, cond, detail = "") {
  if (cond) {
    console.log(`  ok  ${label}`);
  } else {
    failures++;
    console.log(`  FAIL ${label} ${detail}`);
  }
}

const approx = (a, b, eps = 1e-6) => Math.abs(a - b) < eps;

/** Same overlap predicate check_overlap.py uses, reimplemented for plain [x,y,w,h] rects. */
function rectsOverlap([ax, ay, aw, ah], [bx, by, bw, bh], eps = 1e-6) {
  const ax2 = ax + aw, ay2 = ay + ah, bx2 = bx + bw, by2 = by + bh;
  return !(ax2 - eps <= bx || bx2 - eps <= ax || ay2 - eps <= by || by2 - eps <= ay);
}

function withinBounds([rx, ry, rw, rh], [x, y, w, h], eps = 1e-6) {
  return rx >= x - eps && ry >= y - eps && rx + rw <= x + w + eps && ry + rh <= y + h + eps;
}

function assertNoOverlapAndInBounds(label, rect, results) {
  const geoms = results.map((r) => r.geom);
  for (const g of geoms) {
    check(`${label}: within bounds ${JSON.stringify(g.map((n) => +n.toFixed(3)))}`, withinBounds(g, rect));
  }
  for (let i = 0; i < geoms.length; i++) {
    for (let j = i + 1; j < geoms.length; j++) {
      check(`${label}: item ${i}/${j} do not overlap`, !rectsOverlap(geoms[i], geoms[j]));
    }
  }
}

// --- two text blocks, no media -> 50/50 minus gutter, first item left ---
{
  const rect = [1, 1, 10, 5];
  const textA = { block: "A", isMedia: false, aspect: null };
  const textB = { block: "B", isMedia: false, aspect: null };
  const results = splitSharedRect(rect, [textA, textB]);
  const colW = (10 - GUTTER_IN) / 2;
  check("two-text: A gets left column", approx(results[0].geom[0], 1) && approx(results[0].geom[2], colW));
  check("two-text: B gets right column", approx(results[1].geom[0], 1 + colW + GUTTER_IN) && approx(results[1].geom[2], colW));
  check("two-text: both full height", approx(results[0].geom[3], 5) && approx(results[1].geom[3], 5));
  assertNoOverlapAndInBounds("two-text", rect, results);
}

// --- one text + one normal-aspect image -> MEDIA_COL_FRAC split, media right by default ---
{
  const rect = [0, 0, 10, 6];
  const text = { block: "text", isMedia: false, aspect: null };
  const image = { block: "image", isMedia: true, aspect: 1.5 }; // between PORTRAIT_ASPECT and WIDE_ASPECT
  const results = splitSharedRect(rect, [text, image]);
  const mediaW = 10 * MEDIA_COL_FRAC;
  const textW = 10 - GUTTER_IN - mediaW;
  const [textG, imageG] = results;
  check("normal-image: text on left", approx(textG.geom[0], 0) && approx(textG.geom[2], textW));
  check("normal-image: media on right by default", approx(imageG.geom[0], textW + GUTTER_IN) && approx(imageG.geom[2], mediaW));
  assertNoOverlapAndInBounds("normal-image (default right)", rect, results);
}

// --- media_position: "left" -> columns swap ---
{
  const rect = [0, 0, 10, 6];
  const text = { block: "text", isMedia: false, aspect: null };
  const image = { block: "image", isMedia: true, aspect: 1.5 };
  const results = splitSharedRect(rect, [text, image], { mediaPosition: "left" });
  const mediaW = 10 * MEDIA_COL_FRAC;
  const textW = 10 - GUTTER_IN - mediaW;
  const [textG, imageG] = results;
  check("media-left: media on the left", approx(imageG.geom[0], 0) && approx(imageG.geom[2], mediaW));
  check("media-left: text on the right", approx(textG.geom[0], mediaW + GUTTER_IN) && approx(textG.geom[2], textW));
  assertNoOverlapAndInBounds("media-left", rect, results);
}

// --- portrait image (aspect 0.7) -> PORTRAIT_MEDIA_COL_FRAC (narrower media column) ---
{
  const rect = [0, 0, 10, 6];
  const text = { block: "text", isMedia: false, aspect: null };
  const image = { block: "image", isMedia: true, aspect: 0.7 };
  const results = splitSharedRect(rect, [text, image]);
  const mediaW = 10 * PORTRAIT_MEDIA_COL_FRAC;
  check("portrait: narrower media column", approx(results[1].geom[2], mediaW));
  check("portrait: narrower than the default normal-aspect column", mediaW < 10 * MEDIA_COL_FRAC);
  assertNoOverlapAndInBounds("portrait", rect, results);
}

// --- wide image (aspect 3.0), no explicit position -> stacks, text on top ---
{
  const rect = [0, 0, 10, 6];
  const text = { block: "text", isMedia: false, aspect: null };
  const image = { block: "image", isMedia: true, aspect: 3.0 };
  const results = splitSharedRect(rect, [text, image]);
  const [textG, imageG] = results;
  check("wide-image: stacks (text full width)", approx(textG.geom[2], 10) && approx(imageG.geom[2], 10));
  check("wide-image: text on top", textG.geom[1] < imageG.geom[1]);
  check("wide-image: text gets STACK_TEXT_FRAC of height", approx(textG.geom[3], 6 * STACK_TEXT_FRAC));
  assertNoOverlapAndInBounds("wide-image (auto-stack)", rect, results);
}

// --- wide image with explicit media_position: "right" -> stays side-by-side, override wins ---
{
  const rect = [0, 0, 10, 6];
  const text = { block: "text", isMedia: false, aspect: null };
  const image = { block: "image", isMedia: true, aspect: 3.0 };
  const results = splitSharedRect(rect, [text, image], { mediaPosition: "right" });
  const [textG, imageG] = results;
  check("wide-image+explicit-right: side by side, not stacked", approx(textG.geom[3], 6) && approx(imageG.geom[3], 6));
  check("wide-image+explicit-right: media on the right", imageG.geom[0] > textG.geom[0]);
  assertNoOverlapAndInBounds("wide-image (explicit right override)", rect, results);
}

// --- narrow shared rect (w < MIN_SPLIT_W_IN) -> forces stack regardless of aspect ---
{
  const rect = [0, 0, MIN_SPLIT_W_IN - 0.5, 6];
  const text = { block: "text", isMedia: false, aspect: null };
  const image = { block: "image", isMedia: true, aspect: 1.5 }; // normal aspect, would otherwise go side-by-side
  const results = splitSharedRect(rect, [text, image]);
  const [textG, imageG] = results;
  check("narrow-rect: forces stack", approx(textG.geom[2], rect[2]) && approx(imageG.geom[2], rect[2]));
  assertNoOverlapAndInBounds("narrow-rect", rect, results);
}

// --- text column would fall below MIN_COL_W_IN -> clamps text to the floor, media absorbs ---
{
  // Pick a width just above MIN_SPLIT_W_IN so side-by-side is attempted, but small enough
  // that MEDIA_COL_FRAC's default split would leave textW < MIN_COL_W_IN (see
  // MIN_SPLIT_W_IN's own doc comment in build-pptx.js for why the two constants are tuned
  // to make this reachable rather than dead code).
  const rect = [0, 0, MIN_SPLIT_W_IN + 0.05, 6];
  const text = { block: "text", isMedia: false, aspect: null };
  const image = { block: "image", isMedia: true, aspect: 1.5 };
  const results = splitSharedRect(rect, [text, image]);
  const [textG, imageG] = results;
  check("clamp: text column floored at MIN_COL_W_IN", approx(textG.geom[2], MIN_COL_W_IN));
  check("clamp: media absorbs the shortfall", approx(imageG.geom[2], rect[2] - GUTTER_IN - MIN_COL_W_IN));
  assertNoOverlapAndInBounds("clamp", rect, results);
}

// --- diagram media block (isMedia true, aspect null) -> default MEDIA_COL_FRAC split ---
{
  const rect = [0, 0, 10, 6];
  const text = { block: "text", isMedia: false, aspect: null };
  const diagram = { block: "diagram", isMedia: true, aspect: null };
  const results = splitSharedRect(rect, [text, diagram]);
  const mediaW = 10 * MEDIA_COL_FRAC;
  check("diagram (no aspect): default media fraction", approx(results[1].geom[2], mediaW));
  assertNoOverlapAndInBounds("diagram-no-aspect", rect, results);
}

// --- caption carve-out (exercised through composeSlide, not splitSharedRect directly) ---
// splitSharedRect itself knows nothing about captions — the carve happens in composeSlide
// after splitSharedRect returns the media rect. Import composeSlide for this one case.
{
  const { composeSlide } = await import("../src/build-pptx.js");
  const bodyPh = { type: "body", idx: "2", geometry: { x_in: 0.6, y_in: 1.6, w_in: 10, h_in: 5 } };
  const targets = { title: null, pic: null, bodies: [bodyPh], subTitle: null };
  const slideSize = { w_in: 13.33, h_in: 7.5 };
  const blocks = [
    { slot: "body", kind: "bullets", content: ["a", "b"] },
    { slot: "picture", kind: "image", content: { asset_id: "img1" } },
    { slot: "caption", kind: "text", content: "Figure 1" },
  ];
  const assets = new Map([["img1", { bytes: null }]]); // no bytes -> aspect stays null (normal split)
  const resolved = composeSlide(blocks, targets, slideSize, { assets });
  const mediaGeom = resolved.get(blocks[1]).geom;
  const captionGeom = resolved.get(blocks[2]).geom;
  const innerGap = 0.05;
  check(
    "caption: media rect shrunk by CAPTION_STRIP_H_IN + gap",
    approx(mediaGeom[3] + CAPTION_STRIP_H_IN + innerGap, bodyPh.geometry.h_in) ||
      // media rect height is relative to whatever column height splitSharedRect gave it —
      // for a side-by-side split that's the FULL bucket height, so this equality should hold.
      false,
    `mediaH=${mediaGeom[3]}`
  );
  check(
    "caption: sits directly below the (shrunk) media rect, same x/width",
    approx(captionGeom[0], mediaGeom[0]) &&
      approx(captionGeom[2], mediaGeom[2]) &&
      approx(captionGeom[1], mediaGeom[1] + mediaGeom[3] + innerGap) &&
      approx(captionGeom[3], CAPTION_STRIP_H_IN)
  );
  assertNoOverlapAndInBounds("caption-carve", bodyPh.geometry ? [0.6, 1.6, 10, 5] : null, [
    { geom: resolved.get(blocks[0]).geom },
    { geom: mediaGeom },
    { geom: captionGeom },
  ]);
}

console.log(failures ? `\n${failures} FAILURE(S)` : "\nAll splitSharedRect/composeSlide rect-math checks passed.");
process.exit(failures ? 1 : 0);
