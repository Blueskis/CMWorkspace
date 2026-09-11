// Extracts the pure "export-core" script block from index.html and tests it
// with node's built-in test runner. No build step, no dependencies.
//
// Run: node --test artifacts/brand-template-creator/tests/test_export.mjs

import { test } from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const indexPath = path.join(__dirname, "..", "index.html");
const html = fs.readFileSync(indexPath, "utf8");

const START = "// ---8<--- export-core start";
const END = "// ---8<--- export-core end";
const startIdx = html.indexOf(START);
const endIdx = html.indexOf(END);
if (startIdx === -1 || endIdx === -1 || endIdx < startIdx) {
  throw new Error("Could not find export-core markers in index.html");
}
const code = html.slice(startIdx, endIdx);

const sandbox = { module: { exports: {} }, console };
vm.createContext(sandbox);
vm.runInContext(code, sandbox, { filename: "export-core.js" });
const Core = sandbox.module.exports;

for (const name of [
  "normalizeHex",
  "contrastRatio",
  "escapeMdCell",
  "slugifyFilename",
  "clampFormality",
  "validateProfile",
  "buildExportObject",
  "buildExportMarkdown",
  "importProfileFromRaw",
  "mergeGeneratedIntoProfile",
  "decideLogoResize",
  "createEmptyProfile",
  "USAGE_INSTRUCTION",
]) {
  test(`export-core exposes ${name}`, () => {
    assert.notEqual(Core[name], undefined, `${name} missing from BrandCore export`);
  });
}

function completeProfile() {
  const p = Core.createEmptyProfile();
  p.meta.name = "Acme Statutory Board";
  p.meta.org = "Acme";
  p.meta.owner = "J. Tan";
  p.style.theme = "Corporate Institutional";
  p.style.descriptors = ["formal", "confident", "clean"];
  p.style.imagery = "Real staff photography, no stock smiles";
  p.style.layoutFeel = "grid-aligned, generous whitespace";
  p.colors.primary = { hex: "#0b3d91", note: "headers, primary CTAs" };
  p.colors.secondary = { hex: "#1f6f54", note: "secondary accents" };
  p.colors.accent = { hex: "#e0a526", note: "highlights, callouts" };
  p.colors.ink = { hex: "#1a1a1a", note: "body text" };
  p.colors.muted = { hex: "#6b6b6b", note: "captions" };
  p.colors.surface = { hex: "#ffffff", note: "cards" };
  p.colors.background = { hex: "#f4f4f2", note: "page background" };
  p.typography.headingFont = "Fraunces";
  p.typography.headingFallback = "Georgia, serif";
  p.typography.bodyFont = "IBM Plex Sans";
  p.typography.bodyFallback = "Arial, sans-serif";
  p.typography.headingWeight = 600;
  p.typography.bodyWeight = 400;
  p.typography.scaleRatio = 1.25;
  p.logo.dataUri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
  p.logo.variant = "full colour on light";
  p.logo.minWidthPx = 80;
  p.logo.clearSpace = "equal to logotype cap height";
  p.voice.formality = 4;
  p.voice.person = "we";
  p.voice.sentenceLength = "medium";
  p.voice.toneDescriptors = ["measured", "reassuring"];
  p.voice.preferredVocabulary = ["citizens", "service"];
  p.voice.bannedVocabulary = ["disrupt", "synergy"];
  p.voice.rewriteExample = { before: "We're disrupting government.", after: "We are improving public service delivery." };
  p.messaging.tagline = "Service, simplified.";
  p.messaging.oneLiner = "We help statutory boards modernise how citizens are served.";
  p.messaging.boilerplate = "Acme Statutory Board oversees...";
  p.messaging.proofPoints = ["20 agencies onboarded", "98% citizen satisfaction", "ISO 27001 certified"];
  p.messaging.terminology = [{ term: "GLC", definition: "Government-linked company" }];
  return p;
}

// 1. Complete profile -> JSON has every top-level key, version, non-empty usage
test("case 1: complete profile exports every top-level key with usage and version", () => {
  const p = completeProfile();
  const obj = Core.buildExportObject(p);
  for (const key of ["usage", "meta", "style", "colors", "typography", "logo", "voice", "messaging"]) {
    assert.ok(key in obj, `missing key ${key}`);
  }
  assert.equal(typeof obj.usage, "string");
  assert.ok(obj.usage.length > 0);
  assert.equal(typeof obj.meta.version, "number");
  assert.ok(obj.meta.version >= 1);
});

// 2. Profile with no logo -> logo.dataUri null; MD reads "No logo supplied"; no broken image markup
test("case 2: profile with no logo exports null dataUri and a text placeholder in markdown", () => {
  const p = completeProfile();
  p.logo.dataUri = null;
  const obj = Core.buildExportObject(p);
  assert.equal(obj.logo.dataUri, null);
  const md = Core.buildExportMarkdown(p);
  assert.match(md, /No logo supplied/);
  assert.doesNotMatch(md, /!\[[^\]]*\]\(\s*\)/); // no empty-src image markup
  assert.doesNotMatch(md, /<img[^>]*src=["']["']/);
});

// 3. Hex normalisation
test("case 3: hex normalisation handles #ABC, abc, #AABBCC", () => {
  assert.equal(Core.normalizeHex("#ABC"), "#aabbcc");
  assert.equal(Core.normalizeHex("abc"), "#aabbcc");
  assert.equal(Core.normalizeHex("#AABBCC"), "#aabbcc");
});

// 4. Contrast ratio
test("case 4: contrast ratio black-on-white and #777-on-white", () => {
  const bw = Core.contrastRatio("#000000", "#ffffff");
  assert.equal(Math.round(bw * 10) / 10, 21.0);
  const grey = Core.contrastRatio("#777777", "#ffffff");
  assert.equal(Math.round(grey * 100) / 100, 4.48);
});

// 5. Brand name with | and # is escaped in markdown
test("case 5: brand name with | and # does not break the markdown table", () => {
  const p = completeProfile();
  p.meta.name = "Ba | Ka #1 Holdings";
  const md = Core.buildExportMarkdown(p);
  // every table row must have a stable column count; a raw unescaped `|`
  // in a cell would add an extra column to that row
  const tableLines = md.split("\n").filter((l) => l.trim().startsWith("|"));
  const counts = tableLines.map((l) => l.split("|").length);
  assert.ok(counts.length > 0, "expected at least one table row");
  assert.equal(new Set(counts.filter((c, i) => tableLinesAreDataRows(tableLines, i))).size <= 2, true);
  assert.match(md, /Ba \\\| Ka #1 Holdings/);
});
function tableLinesAreDataRows(lines, i) {
  return !/^\s*\|[-\s|:]+\|\s*$/.test(lines[i]);
}

// 6. Filename slug
test("case 6: filename slug strips punctuation and collapses spaces", () => {
  const slug = Core.slugifyFilename("Ministry of Trade & Industry (MTI)");
  assert.equal(slug, "ministry-of-trade-industry-mti-brand.json");
});

// 7. Empty brand name blocks export
test("case 7: empty brand name fails validation naming meta.name", () => {
  const p = completeProfile();
  p.meta.name = "   ";
  const result = Core.validateProfile(p);
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.field === "meta.name"));
});

// 8. Export then re-import round trip
test("case 8: export JSON then re-import round trips with no field lost", () => {
  const p = completeProfile();
  const exported = Core.buildExportObject(p);
  const reimported = Core.importProfileFromRaw(exported);
  const reExported = Core.buildExportObject(reimported);
  assert.deepEqual(reExported, exported);
});

// 9. Malformed / partial model output leaves existing values untouched
test("case 9: malformed sample output leaves profile untouched and surfaces an error", () => {
  const p = completeProfile();
  const beforeJson = JSON.stringify(p);
  const r1 = Core.mergeGeneratedIntoProfile(p, "not json at all {{{", false);
  // objects come from a separate vm realm than this test file, so compare
  // via JSON rather than assert.deepEqual (which treats cross-realm plain
  // objects as not reference-equal even when structurally identical)
  assert.equal(JSON.stringify(r1.profile), beforeJson);
  assert.ok(r1.error);

  const r2 = Core.mergeGeneratedIntoProfile(p, null, false);
  assert.equal(JSON.stringify(r2.profile), beforeJson);
  assert.ok(r2.error);

  // partial object: only fills what is given, and only into empty fields
  const empty = Core.createEmptyProfile();
  const r3 = Core.mergeGeneratedIntoProfile(empty, { colors: { primary: { hex: "#123456" } } }, false);
  assert.equal(r3.profile.colors.primary.hex, "#123456");
  assert.equal(r3.error, null);
});

// 10. Logo resize decision
test("case 10: 3000x2000 logo downscales to 512px longest edge, aspect preserved", () => {
  const size = Core.decideLogoResize(3000, 2000);
  assert.equal(Math.max(size.width, size.height), 512);
  const originalRatio = 3000 / 2000;
  const newRatio = size.width / size.height;
  assert.ok(Math.abs(originalRatio - newRatio) < 0.01);
});

// 11. Import preserves unknown extra keys
test("case 11: import preserves unknown top-level keys under x_extra", () => {
  const p = completeProfile();
  const exported = Core.buildExportObject(p);
  exported.someFutureField = "keep me";
  exported.anotherOne = { nested: true };
  const reimported = Core.importProfileFromRaw(exported);
  assert.equal(reimported.x_extra.someFutureField, "keep me");
  assert.deepEqual(reimported.x_extra.anotherOne, { nested: true });
});

// 12. Voice formality clamped to 1-5
test("case 12: voice formality 0 or 6 clamp to 1-5", () => {
  assert.equal(Core.clampFormality(0), 1);
  assert.equal(Core.clampFormality(6), 5);
  assert.equal(Core.clampFormality(3), 3);
  assert.equal(Core.clampFormality(-10), 1);
  assert.equal(Core.clampFormality(100), 5);
});
