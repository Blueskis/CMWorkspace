import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { unzipAll, zipPackage } = require("../src/ooxml-zip.js");
const { profileTemplate } = require("../src/ooxml-read.js");
const { buildPptx } = require("../src/build-pptx.js");
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIX = path.join(HERE, "fixtures");
const OUT = path.join(HERE, "..", "out");
const ROOT = path.join(HERE, "..");

async function templateBuffer(filename = "sample-template.potx") {
  const buf = await readFile(path.join(FIX, filename));
  return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
}

async function validateWithPython(buffer, outName) {
  await mkdir(OUT, { recursive: true });
  const outPath = path.join(OUT, outName);
  await writeFile(outPath, Buffer.from(buffer));
  const { stdout } = await execFileAsync("python3", [path.join(HERE, "validate_pptx.py"), outPath], { cwd: ROOT });
  return JSON.parse(stdout);
}

// Test case 6: unzip a template, rezip unchanged, python-pptx reports identical layout names.
test("case 6: unmodified round trip preserves every layout name", async () => {
  const ab = await templateBuffer();
  const { entries } = await unzipAll(ab);
  const before = profileTemplate(entries, "t");
  const rebuilt = await zipPackage([...entries.keys()].map(name => ({ name, data: entries.get(name) })));

  const { entries: reread } = await unzipAll(rebuilt.buffer.slice(rebuilt.byteOffset, rebuilt.byteOffset + rebuilt.byteLength));
  const after = profileTemplate(reread, "t");
  assert.deepEqual(after.layouts.map(l => l.name), before.layouts.map(l => l.name));
});

// Test case 7: one slide, Title Slide layout, exact title -> python-pptx confirms.
test("case 7: single slide on Title Slide layout carries the exact title", async () => {
  const ab = await templateBuffer();
  const result = await buildPptx(ab, [{
    layoutName: "Title Slide",
    shapes: [{ want: { type: "ctrTitle" }, paragraphs: [{ text: "Change Management Proposal" }] }],
  }]);
  assert.deepEqual(result.errors, []);
  assert.ok(result.buffer);

  const summary = await validateWithPython(result.buffer, "case7.pptx");
  assert.equal(summary.slide_count, 1);
  assert.equal(summary.slides[0].layout, "Title Slide");
  const runs = summary.slides[0].shapes[0].paragraphs.flatMap(p => p.runs);
  assert.equal(runs.join(""), "Change Management Proposal");
});

// Test case 8: bullets at levels 0,1,1 -> correct paragraph levels, no explicit font/colour.
test("case 8: bulleted body preserves levels and adds no explicit formatting", async () => {
  const ab = await templateBuffer();
  const result = await buildPptx(ab, [{
    layoutName: "Title and Content",
    shapes: [{
      want: { type: "body" },
      paragraphs: [
        { text: "Top-level point", level: 0 },
        { text: "Supporting detail", level: 1 },
        { text: "Another supporting detail", level: 1 },
      ],
    }],
  }]);
  assert.deepEqual(result.errors, []);

  const summary = await validateWithPython(result.buffer, "case8.pptx");
  const bodyShape = summary.slides[0].shapes.find(s => s.paragraphs && s.paragraphs.length === 3);
  assert.ok(bodyShape, "expected a shape with 3 paragraphs");
  assert.deepEqual(bodyShape.paragraphs.map(p => p.level), [0, 1, 1]);

  // No explicit font/colour: confirm the raw slide XML carries no <a:latin>,
  // <a:solidFill>, or <a:rPr> with size/colour attributes on any run.
  const buf = Buffer.from(result.buffer);
  const { entries } = await unzipAll(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
  const slideXml = new TextDecoder().decode(entries.get("ppt/slides/slide1.xml"));
  assert.ok(!slideXml.includes("<a:latin"), "slide XML must not set an explicit font");
  assert.ok(!slideXml.includes("solidFill"), "slide XML must not set an explicit colour");
  assert.ok(!slideXml.includes("<a:rPr"), "slide XML must not set explicit run properties");
});

// Test case 9: special characters survive byte-exact after round trip.
test("case 9: entities, em-dash, and non-Latin text survive exactly", async () => {
  const tricky = 'Fish & Chips <tag> "quoted" — 培训计划';
  const ab = await templateBuffer();
  const result = await buildPptx(ab, [{
    layoutName: "Title Slide",
    shapes: [{ want: { type: "ctrTitle" }, paragraphs: [{ text: tricky }] }],
  }]);
  assert.deepEqual(result.errors, []);

  const summary = await validateWithPython(result.buffer, "case9.pptx");
  const runs = summary.slides[0].shapes[0].paragraphs.flatMap(p => p.runs);
  assert.equal(runs.join(""), tricky);
});

// Test case 10: template already holding example slides -> output has only the new ones.
test("case 10: existing example slides are replaced, not appended to", async () => {
  const ab = await templateBuffer("sample-template.pptx"); // ships with 2 example slides
  const result = await buildPptx(ab, [{
    layoutName: "Title Slide",
    shapes: [{ want: { type: "ctrTitle" }, paragraphs: [{ text: "Only slide" }] }],
  }]);
  assert.deepEqual(result.errors, []);

  const summary = await validateWithPython(result.buffer, "case10.pptx");
  assert.equal(summary.slide_count, 1);

  const buf = Buffer.from(result.buffer);
  const { entries, names } = await unzipAll(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
  const slideParts = names.filter(n => /^ppt\/slides\/slide\d+\.xml$/.test(n));
  assert.deepEqual(slideParts, ["ppt/slides/slide1.xml"]);

  // No orphaned content-type overrides or presentation rels pointing at a
  // slide part that no longer exists.
  const contentTypes = new TextDecoder().decode(entries.get("[Content_Types].xml"));
  const overriddenSlideParts = [...contentTypes.matchAll(/PartName="(\/ppt\/slides\/slide\d+\.xml)"/g)].map(m => m[1]);
  assert.deepEqual(overriddenSlideParts, ["/ppt/slides/slide1.xml"]);

  const presRels = new TextDecoder().decode(entries.get("ppt/_rels/presentation.xml.rels"));
  const slideRelTargets = [...presRels.matchAll(/Target="(slides\/slide\d+\.xml)"/g)].map(m => m[1]);
  assert.deepEqual(slideRelTargets, ["slides/slide1.xml"]);
});

// Test case 11: a 14-slide deck -> unique sldId values >= 256, all 14 slides present.
test("case 11: a 14-slide deck gets unique sldId values and all slides present", async () => {
  const ab = await templateBuffer();
  const shapes = [{ want: { type: "ctrTitle" }, paragraphs: [{ text: "Slide" }] }];
  const slideRequests = Array.from({ length: 14 }, (_, i) => ({
    layoutName: "Title Slide",
    shapes: [{ want: { type: "ctrTitle" }, paragraphs: [{ text: `Slide ${i + 1}` }] }],
  }));
  const result = await buildPptx(ab, slideRequests);
  assert.deepEqual(result.errors, []);

  const summary = await validateWithPython(result.buffer, "case11.pptx");
  assert.equal(summary.slide_count, 14);

  const buf = Buffer.from(result.buffer);
  const { entries } = await unzipAll(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
  const presentation = new TextDecoder().decode(entries.get("ppt/presentation.xml"));
  const ids = [...presentation.matchAll(/<p:sldId id="(\d+)"/g)].map(m => Number(m[1]));
  assert.equal(ids.length, 14);
  assert.equal(new Set(ids).size, 14, "sldId values must be unique");
  assert.ok(ids.every(id => id >= 256), "sldId values must be >= 256");
});

// Test case 12: slide targets a placeholder the layout lacks -> refused, no file.
test("case 12: an unresolvable placeholder refuses the build with a named error", async () => {
  const ab = await templateBuffer();
  const result = await buildPptx(ab, [{
    layoutName: "Title Slide",
    shapes: [{ want: { type: "body", idx: "99" }, paragraphs: [{ text: "orphan" }] }],
  }]);
  assert.equal(result.buffer, null);
  assert.ok(result.errors.length > 0);
  assert.match(result.errors[0].message, /no placeholder/);
});

// Test case 13: speaker notes with no notes master -> dropped, warned, file still valid.
test("case 13: notes are dropped with a warning when the template has no notes master", async () => {
  const ab = await templateBuffer("empty-template.potx"); // stripped of layouts too
  // empty-template has no layouts, so build against sample-template but
  // strip only the notes master to isolate the behaviour under test.
  const { entries } = await unzipAll(await templateBuffer());
  for (const name of [...entries.keys()]) {
    if (/notesMaster/.test(name)) entries.delete(name);
  }
  const contentTypes = new TextDecoder().decode(entries.get("[Content_Types].xml"))
    .replace(/<Override PartName="\/ppt\/notesMasters\/notesMaster\d+\.xml"[^>]*?\/>/g, "");
  entries.set("[Content_Types].xml", new TextEncoder().encode(contentTypes));
  const presRels = new TextDecoder().decode(entries.get("ppt/_rels/presentation.xml.rels"))
    .replace(/<Relationship [^>]*notesMaster[^>]*\/>/g, "");
  entries.set("ppt/_rels/presentation.xml.rels", new TextEncoder().encode(presRels));

  const noNotesMasterBuffer = await zipPackage([...entries.keys()].map(name => ({ name, data: entries.get(name) })));
  const result = await buildPptx(
    noNotesMasterBuffer.buffer.slice(noNotesMasterBuffer.byteOffset, noNotesMasterBuffer.byteOffset + noNotesMasterBuffer.byteLength),
    [{
      layoutName: "Title Slide",
      shapes: [{ want: { type: "ctrTitle" }, paragraphs: [{ text: "Title" }] }],
      notes: "This should be dropped.",
    }]
  );
  assert.deepEqual(result.errors, []);
  assert.ok(result.warnings.some(w => /notes master/.test(w)));
  assert.ok(result.buffer);

  const summary = await validateWithPython(result.buffer, "case13.pptx");
  assert.equal(summary.slide_count, 1);
});
