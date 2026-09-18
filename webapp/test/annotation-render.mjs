/**
 * Unit tests for render-annotation.js — mirrors DiagramRenderTests on the Python side:
 * well-formed/hex-free/no-latin XML, the fitted-rect coordinate transform, the callout's
 * editable text run, out-of-bounds/unknown-type errors, the {1..N} step-binding validator,
 * and a full picture+overlay round-trip through buildPptx with correct z-order.
 *
 *   node test/annotation-render.mjs
 */
import { DOMParser } from "@xmldom/xmldom";
import { readFileSync } from "node:fs";
import { renderAnnotation, validateAnnotations, AnnotationSpecError, DiagramOverflowError } from "../src/render-annotation.js";
import { fitExtent, imagePixelSize } from "../src/build-pptx.js";
import { profileTemplate } from "../src/profile-template.js";
import { resolveLayoutRoles } from "../src/map-layouts.js";
import { buildPptx } from "../src/build-pptx.js";
import { getJSZip } from "../src/env.js";

let failures = 0;
function check(label, cond, detail = "") {
  if (cond) console.log(`  ok  ${label}`);
  else { failures++; console.log(`  FAIL ${label} ${detail}`); }
}

const ALL_FIVE = [
  { type: "highlight", rect: [0.41, 0.22, 0.28, 0.06], step: 1, label: "Approve button" },
  { type: "callout", point: [0.55, 0.25], step: 1 },
  { type: "arrow", from: [0.70, 0.40], to: [0.56, 0.26], step: 2 },
  { type: "redact", rect: [0.05, 0.05, 0.22, 0.04], reason: "vendor name" },
  { type: "zoom", rect: [0.40, 0.20, 0.10, 0.08], scale: 3, place: "right", step: 3 },
];
const BBOX = [0.6, 1.8, 8.5, 4.5];
const FITTED = fitExtent(BBOX, { width: 400, height: 300 });

// ---------------------------------------------------------------------------
// 1. All five types render well-formed, hex-free, no-latin XML
// ---------------------------------------------------------------------------
{
  const { ooxml, svg, idsUsed } = renderAnnotation(ALL_FIVE, FITTED, { idStart: 200 });
  const wrapped = `<root xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">${ooxml}</root>`;
  let parseOk = true;
  new DOMParser({ onError: () => { parseOk = false; } }).parseFromString(wrapped, "text/xml");
  check("all five types parse as well-formed XML", parseOk);
  check("no hex colours (srgbClr or #RRGGBB)", !/srgbClr|#[0-9a-fA-F]{6}/.test(ooxml));
  check("no explicit typeface (a:latin)", !ooxml.includes("a:latin"));
  check("exactly one <p:grpSp>", (ooxml.match(/<p:grpSp>/g) || []).length === 1);
  check("svg preview present", svg.includes("<svg"));
  // group(1) + highlight(1) + callout(1) + arrow(1) + redact(1) + zoom(2) = 7
  check("idsUsed accounts for group + all shapes (7)", idsUsed === 7, `got ${idsUsed}`);
}

// ---------------------------------------------------------------------------
// 2. Fitted-rect coordinate transform — reuses inject_slide_xml.py's own fit_extent twin
// ---------------------------------------------------------------------------
{
  const wideImageInTallBox = fitExtent([0, 0, 4, 6], { width: 1600, height: 900 }); // 16:9 into portrait box
  check("wide image in tall box: fitted width == box width (pillarboxed on Y)",
    Math.abs(wideImageInTallBox[3] - (4 * 900 / 1600)) < 1e-9);
  const tallImageInWideBox = fitExtent([0, 0, 9, 3], { width: 600, height: 1200 }); // portrait into wide box
  check("tall image in wide box: fitted height == box height (letterboxed on X)",
    Math.abs(tallImageInWideBox[2] - (3 * 600 / 1200)) < 1e-9);

  const { ooxml } = renderAnnotation([{ type: "callout", point: [0.5, 0.5], step: 1 }], FITTED, { idStart: 200 });
  const [fx, fy, fw, fh] = FITTED;
  const cx = fx + 0.5 * fw, cy = fy + 0.5 * fh;
  const offMatch = ooxml.match(/<a:off x="(\d+)" y="(\d+)"\/>/);
  const extMatch = ooxml.match(/<a:ext cx="(\d+)" cy="(\d+)"\/>/);
  const shapeCx = (parseInt(offMatch[1], 10) + parseInt(extMatch[1], 10) / 2) / 914400;
  const shapeCy = (parseInt(offMatch[2], 10) + parseInt(extMatch[2], 10) / 2) / 914400;
  check("a centre-of-image callout lands at the fitted rect's centre, not the bbox's",
    Math.abs(shapeCx - cx) < 0.01 && Math.abs(shapeCy - cy) < 0.01,
    `shape centre (${shapeCx.toFixed(3)},${shapeCy.toFixed(3)}) vs fitted centre (${cx.toFixed(3)},${cy.toFixed(3)})`);
}

// ---------------------------------------------------------------------------
// 3. Callout number is a real, editable text run — never a rasterized digit
// ---------------------------------------------------------------------------
{
  const { ooxml } = renderAnnotation([{ type: "callout", point: [0.5, 0.5], step: 7 }], FITTED, { idStart: 200 });
  check("callout digit is a genuine <a:t> text run", ooxml.includes("<a:t>7</a:t>"));
}

// ---------------------------------------------------------------------------
// 4-6. Error paths
// ---------------------------------------------------------------------------
{
  let threw = false;
  try { renderAnnotation([{ type: "callout", point: [1.5, 0.2], step: 1 }], FITTED, { idStart: 200 }); }
  catch (e) { threw = e instanceof AnnotationSpecError; }
  check("out-of-bounds point throws AnnotationSpecError", threw);
}
{
  let threw = false;
  try { renderAnnotation([{ type: "highlight", rect: [0.9, 0.9, 0.5, 0.5], step: 1 }], FITTED, { idStart: 200 }); }
  catch (e) { threw = e instanceof AnnotationSpecError; }
  check("rect extending past image edge throws AnnotationSpecError", threw);
}
{
  let threw = false;
  try { renderAnnotation([{ type: "bogus", point: [0.1, 0.1] }], FITTED, { idStart: 200 }); }
  catch (e) { threw = e instanceof AnnotationSpecError; }
  check("unknown annotation type throws AnnotationSpecError", threw);
}

// ---------------------------------------------------------------------------
// 7. validateAnnotations — the {1..N} step-binding rule and the pixel-coordinate guard
// ---------------------------------------------------------------------------
{
  const clean = validateAnnotations(
    [{ type: "callout", point: [0.1, 0.1], step: 1 }, { type: "callout", point: [0.2, 0.2], step: 2 }, { type: "callout", point: [0.3, 0.3], step: 3 }],
    3,
  );
  check("steps [1,2,3] against 3 bullets: no errors", clean.errors.length === 0, JSON.stringify(clean.errors));

  const gap = validateAnnotations(
    [{ type: "callout", point: [0.1, 0.1], step: 1 }, { type: "callout", point: [0.3, 0.3], step: 3 }],
    3,
  );
  check("steps [1,3] against 3 bullets: binding error", gap.errors.length === 1);

  const outOfRange = validateAnnotations(
    [{ type: "callout", point: [0.1, 0.1], step: 1 }, { type: "callout", point: [0.2, 0.2], step: 2 }, { type: "callout", point: [0.3, 0.3], step: 4 }],
    3,
  );
  check("steps [1,2,4] against 3 bullets: binding error", outOfRange.errors.length === 1);

  const pixelSlip = validateAnnotations([{ type: "callout", point: [45, 0.1], step: 1 }], 1);
  check("a coordinate value of 120 is flagged as a pixel-coordinate slip",
    pixelSlip.errors.some((e) => e.includes("pixel coordinate")));
}

// ---------------------------------------------------------------------------
// 8. Full round-trip through buildPptx: picture placed before the annotation overlay
//    (z-order), all shape ids unique
// ---------------------------------------------------------------------------
{
  const screenshot = readFileSync("test/fixtures/screenshot.png");
  const plan = {
    modules: [{ module_id: "m1", order: 1, slides: [
      { slide_id: "cover-1", role: "title-slide", blocks: [{ slot: "title", kind: "text", content: "Test Deck" }] },
      { slide_id: "s1", role: "content", blocks: [
        { slot: "title", kind: "text", content: "Approve the PO" },
        { slot: "body", kind: "bullets", content: ["Open the worklist", "Click Approve", "Confirm"] },
        { slot: "picture", kind: "image", content: {
          asset_id: "img1", caption: "Worklist screen",
          annotations: [
            { type: "highlight", rect: [0.1, 0.1, 0.3, 0.1], step: 1 },
            { type: "callout", point: [0.5, 0.2], step: 2 },
            { type: "arrow", from: [0.7, 0.5], to: [0.6, 0.3], step: 3 },
          ],
        } },
      ] },
    ] }],
  };
  const assets = new Map([["img1", { bytes: screenshot, ext: "png", alt: "Worklist screenshot" }]]);
  const templateBytes = readFileSync("test/fixtures/templates/minimal.pptx");
  const profile = await profileTemplate(templateBytes);
  const { assignment } = resolveLayoutRoles(profile);
  const { file, warnings } = await buildPptx({ templateBytes, profile, assignment, plan, assets });
  check("build produced no warnings", warnings.length === 0, JSON.stringify(warnings));

  const JSZip = await getJSZip();
  const zip = await JSZip.loadAsync(file);
  const slideFiles = Object.keys(zip.files).filter((f) => /ppt\/slides\/slide\d+\.xml$/.test(f)).sort();
  let sawAnnotated = false;
  for (const sf of slideFiles) {
    const xml = await zip.files[sf].async("string");
    if (!xml.includes("<p:pic>")) continue;
    sawAnnotated = true;
    const picIdx = xml.indexOf("<p:pic>");
    const grpIdx = xml.indexOf("<p:grpSp>");
    check(`${sf}: picture precedes annotation overlay (z-order)`, picIdx !== -1 && grpIdx !== -1 && picIdx < grpIdx);
    const ids = [...xml.matchAll(/<p:cNvPr id="(\d+)"/g)].map((m) => m[1]);
    check(`${sf}: all shape ids unique`, new Set(ids).size === ids.length, JSON.stringify(ids));
    check(`${sf}: callout digit present as real text`, /<a:t>\d<\/a:t>/.test(xml));
  }
  check("at least one slide with a picture was found", sawAnnotated);
}

// ---------------------------------------------------------------------------
// 9. buildPptx refuses a "redact" annotation whose asset has no redacted_from — the
//    vector shape alone is cosmetic; shipping it as if it were a real redaction is a
//    data-disclosure defect, not a warning to shrug off. Uses the exact asset-value shape
//    ui.js's own assetsByRole Map construction produces (no asset_id key on the value —
//    that's the Map's key), since a prior version of this refusal's message referenced
//    a field that doesn't exist there and would have silently printed "undefined".
// ---------------------------------------------------------------------------
{
  const screenshot = readFileSync("test/fixtures/screenshot.png");
  const plan = {
    modules: [{ module_id: "m1", order: 1, slides: [
      { slide_id: "cover-1", role: "title-slide", blocks: [{ slot: "title", kind: "text", content: "T" }] },
      { slide_id: "s1", role: "content", blocks: [
        { slot: "title", kind: "text", content: "Approve" },
        { slot: "body", kind: "bullets", content: ["Step 1"] },
        { slot: "picture", kind: "image", content: {
          asset_id: "img1", annotations: [{ type: "redact", rect: [0.1, 0.1, 0.1, 0.1], reason: "vendor" }],
        } },
      ] },
    ] }],
  };
  const assets = new Map([["img1", { bytes: screenshot, ext: "png", alt: "w", redacted_from: null }]]);
  const templateBytes = readFileSync("test/fixtures/templates/minimal.pptx");
  const profile = await profileTemplate(templateBytes);
  const { assignment } = resolveLayoutRoles(profile);
  const { warnings } = await buildPptx({ templateBytes, profile, assignment, plan, assets });
  check("un-flattened redact: build refuses the block with a warning", warnings.length === 1, JSON.stringify(warnings));
  check("un-flattened redact: warning names the actual asset_id, not 'undefined'",
    warnings[0]?.includes('"img1"') && !warnings[0]?.includes("undefined"), warnings[0]);
}

console.log(failures ? `\n${failures} FAILURE(S)` : "\nAll render-annotation.js checks passed.");
process.exit(failures ? 1 : 0);
