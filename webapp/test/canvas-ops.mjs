/**
 * Unit tests for canvas-ops.js — the two pixel operations a vector shape cannot do:
 * redact (destroy pixels, not just cover them) and crop+upscale (a real magnified zoom
 * inset). Uses the `canvas` npm devDependency directly to build and read back a fixture,
 * exactly the path the Node test harness itself takes through canvas-ops.js's own
 * Node fallback (see its module docstring).
 *
 *   node test/canvas-ops.mjs
 */
import { createCanvas, loadImage } from "canvas";
import { redactImage, cropScale, mimeFor, CanvasOpsError } from "../src/canvas-ops.js";

let failures = 0;
function check(label, cond, detail = "") {
  if (cond) console.log(`  ok  ${label}`);
  else { failures++; console.log(`  FAIL ${label} ${detail}`); }
}

// 64x40 fixture: left half red, right half blue — enough to tell "inside the redact rect"
// from "outside it" by eye and by pixel value.
const W = 64, H = 40;
function buildFixture() {
  const c = createCanvas(W, H);
  const ctx = c.getContext("2d");
  ctx.fillStyle = "red"; ctx.fillRect(0, 0, W / 2, H);
  ctx.fillStyle = "blue"; ctx.fillRect(W / 2, 0, W / 2, H);
  return new Uint8Array(c.toBuffer("image/png"));
}

async function readPixel(pngBytes, x, y) {
  const img = await loadImage(Buffer.from(pngBytes));
  const c = createCanvas(img.width, img.height);
  const ctx = c.getContext("2d");
  ctx.drawImage(img, 0, 0);
  return Array.from(ctx.getImageData(x, y, 1, 1).data);
}

const fixture = buildFixture();

// ---------------------------------------------------------------------------
// mimeFor
// ---------------------------------------------------------------------------
check("mimeFor('png') -> image/png", mimeFor("png") === "image/png");
check("mimeFor('jpg') -> image/jpeg", mimeFor("jpg") === "image/jpeg");
check("mimeFor(undefined) defaults to image/png", mimeFor(undefined) === "image/png");

// ---------------------------------------------------------------------------
// redactImage — destroys pixels inside the rect, leaves everything outside untouched,
// never mutates the input
// ---------------------------------------------------------------------------
{
  const beforeLen = fixture.length;
  const redacted = await redactImage(fixture, "image/png", [0, 0, 0.5, 1]); // left half
  check("input bytes are not mutated", fixture.length === beforeLen);
  check("output is a different byte buffer than the input", redacted !== fixture);

  const insidePx = await readPixel(redacted, 10, 10); // inside the redacted left half
  const outsidePx = await readPixel(redacted, 50, 10); // outside — should still be blue

  check("pixel inside the redacted rect is dark (destroyed, not merely covered)",
    insidePx[0] < 30 && insidePx[1] < 30 && insidePx[2] < 30, JSON.stringify(insidePx));
  check("pixel outside the redacted rect is untouched (still blue)",
    outsidePx[2] > 200 && outsidePx[0] < 50, JSON.stringify(outsidePx));
}

// ---------------------------------------------------------------------------
// cropScale — crop dimensions are exact, nearest-neighbour upscale (no blending), source
// untouched
// ---------------------------------------------------------------------------
{
  const cropped = await cropScale(fixture, "image/png", [0.5, 0, 0.25, 0.3], 3);
  const img = await loadImage(Buffer.from(cropped));
  const expectedW = Math.round(0.25 * W) * 3;
  const expectedH = Math.round(0.3 * H) * 3;
  check("crop+scale output has exact expected dimensions",
    img.width === expectedW && img.height === expectedH,
    `got ${img.width}x${img.height}, expected ${expectedW}x${expectedH}`);

  const topLeft = await readPixel(cropped, 1, 1); // well inside the blue crop region
  check("cropped region samples the correct source colour (blue)",
    topLeft[2] > 200 && topLeft[0] < 50, JSON.stringify(topLeft));
}

// ---------------------------------------------------------------------------
// error paths
// ---------------------------------------------------------------------------
{
  let threw = false;
  try { await cropScale(fixture, "image/png", [0, 0, 0.5, 0.5], 0); }
  catch (e) { threw = e instanceof CanvasOpsError; }
  check("scale < 1 throws CanvasOpsError", threw);
}
{
  let threw = false;
  try { await redactImage(fixture, "image/png", [0.9, 0.9, 0.5, 0.5]); }
  catch (e) { threw = e instanceof CanvasOpsError; }
  check("a rect extending past the image edge throws CanvasOpsError", threw);
}

console.log(failures ? `\n${failures} FAILURE(S)` : "\nAll canvas-ops.js checks passed.");
process.exit(failures ? 1 : 0);
