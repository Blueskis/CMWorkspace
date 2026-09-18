/**
 * Pixel operations for the two annotation types a vector shape genuinely cannot do:
 * `redact` (destroy pixels, not just cover them) and `zoom` (a real magnified crop).
 *
 * This is the browser twin of `png_ops.py`, but it does NOT reimplement a PNG codec —
 * the browser already has one, Canvas 2D, so this module is far smaller than its Python
 * sibling. It reuses the exact Canvas-shim pattern `parse-pdf.js`'s `imageToPng()`
 * established: `OffscreenCanvas` in a browser, a `<canvas>` element if `document` exists,
 * the `canvas` npm package (already a devDependency, already externalized in build.js so
 * it never reaches the shipped bundle) under the Node test harness.
 *
 * **The redaction guarantee is the one thing this module exists to protect.** A vector
 * `redact` shape (render-annotation.js) is cosmetic — it covers the region on screen but
 * the original pixels stay in `ppt/media/` inside the .pptx zip. `redactImage()` here
 * produces a NEW image whose pixels in that region are gone. The two must always be used
 * together: plan.js calls this the moment a `redact` annotation comes back from Claude,
 * registers the result as a new asset with `redacted_from` set, and repoints the block at
 * it — build-pptx.js and qa.js both refuse a `redact` annotation on any asset that isn't
 * flattened this way. See SKILL.md's note on this exact invariant on the Python side.
 *
 * Upscaling for `zoom` is nearest-neighbour (`imageSmoothingEnabled = false`), matching
 * png_ops.py's choice — smoothing would blur exactly the crisp UI-element border a zoom
 * inset exists to show.
 */

export const MIME_BY_FORMAT = {
  png: "image/png", jpeg: "image/jpeg", jpg: "image/jpeg",
  gif: "image/gif", bmp: "image/bmp", webp: "image/webp",
};

export function mimeFor(formatOrExt) {
  return MIME_BY_FORMAT[String(formatOrExt ?? "png").toLowerCase()] ?? "image/png";
}

export class CanvasOpsError extends Error {}

async function makeCanvas(width, height) {
  if (typeof OffscreenCanvas !== "undefined") return { canvas: new OffscreenCanvas(width, height), nodeCanvasMod: null };
  if (typeof document !== "undefined") {
    const c = document.createElement("canvas");
    c.width = width; c.height = height;
    return { canvas: c, nodeCanvasMod: null };
  }
  // Node test harness — see the module docstring.
  try {
    const nodeCanvasMod = await import("canvas");
    return { canvas: nodeCanvasMod.createCanvas(width, height), nodeCanvasMod };
  } catch {
    throw new CanvasOpsError(
      "no canvas implementation available (no OffscreenCanvas, no document, and the " +
        "'canvas' npm package is not installed) — pixel operations cannot run here"
    );
  }
}

/** Decodes `bytes` (a PNG/JPEG/etc.) into a drawable source with .width/.height, using
 * createImageBitmap in the browser or node-canvas's loadImage under Node. */
async function decodeImage(bytes, mime) {
  if (typeof createImageBitmap === "function") {
    const blob = new Blob([bytes], { type: mime });
    return { source: await createImageBitmap(blob), nodeCanvasMod: null };
  }
  try {
    const nodeCanvasMod = await import("canvas");
    const buf = bytes instanceof Uint8Array ? Buffer.from(bytes) : Buffer.from(bytes);
    const image = await nodeCanvasMod.loadImage(buf);
    return { source: image, nodeCanvasMod };
  } catch (e) {
    throw new CanvasOpsError(`could not decode image bytes: ${e.message}`);
  }
}

async function encodeCanvas(canvas, nodeCanvasMod) {
  if (nodeCanvasMod) return new Uint8Array(canvas.toBuffer("image/png"));
  const blob = canvas.convertToBlob
    ? await canvas.convertToBlob({ type: "image/png" })
    : await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  return new Uint8Array(await blob.arrayBuffer());
}

/** [u, v, du, dv] normalised 0-1, plus the image's pixel size -> integer pixel bounds. */
function rectToPx(rect, width, height, label = "rect") {
  const [u, v, du, dv] = rect;
  if (!(u >= 0 && u <= 1 && v >= 0 && v <= 1 && du > 0 && dv > 0 && u + du <= 1.0001 && v + dv <= 1.0001)) {
    throw new CanvasOpsError(`${label} [${rect.join(", ")}] is out of 0-1 bounds or extends past the image edge`);
  }
  const x0 = Math.max(0, Math.round(u * width));
  const y0 = Math.max(0, Math.round(v * height));
  const x1 = Math.min(width, Math.max(x0 + 1, Math.round((u + du) * width)));
  const y1 = Math.min(height, Math.max(y0 + 1, Math.round((v + dv) * height)));
  return [x0, y0, x1 - x0, y1 - y0];
}

/**
 * Destroys every pixel inside `rect` (normalised [u,v,du,dv]), returns a NEW PNG's bytes.
 * The input bytes are never modified — the caller registers this as a new asset.
 */
export async function redactImage(bytes, mime, rect) {
  const { source, nodeCanvasMod } = await decodeImage(bytes, mime);
  const width = source.width, height = source.height;
  const { canvas, nodeCanvasMod: canvasMod } = await makeCanvas(width, height);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(source, 0, 0, width, height);
  const [x, y, w, h] = rectToPx(rect, width, height, "redact rect");
  ctx.fillStyle = "#111111";
  ctx.fillRect(x, y, w, h);
  return encodeCanvas(canvas, canvasMod ?? nodeCanvasMod);
}

/**
 * Crops `rect` (normalised [u,v,du,dv]) and upscales it `scale`x, nearest-neighbour, for a
 * `zoom` annotation's magnified inset. Returns a NEW PNG's bytes.
 */
export async function cropScale(bytes, mime, rect, scale = 3) {
  if (!(Number.isInteger(scale) && scale >= 1)) {
    throw new CanvasOpsError(`scale must be a positive integer (got ${scale})`);
  }
  const { source, nodeCanvasMod } = await decodeImage(bytes, mime);
  const width = source.width, height = source.height;
  const [x, y, w, h] = rectToPx(rect, width, height, "zoom rect");
  const { canvas, nodeCanvasMod: canvasMod } = await makeCanvas(w * scale, h * scale);
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false; // nearest-neighbour — keeps UI text/borders crisp
  ctx.drawImage(source, x, y, w, h, 0, 0, w * scale, h * scale);
  return encodeCanvas(canvas, canvasMod ?? nodeCanvasMod);
}
