import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { unzipAll } = require("../src/ooxml-zip.js");
const { profileTemplate } = require("../src/ooxml-read.js");
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");

async function loadProfile(filename) {
  const buf = await readFile(path.join(FIX, filename));
  const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  const { entries } = await unzipAll(ab);
  return profileTemplate(entries, filename);
}

// Test case 1: valid .potx, layouts with names/placeholders, theme, slide size.
test("case 1: profiles a valid .potx — layouts, theme, slide size", async () => {
  const profile = await loadProfile("sample-template.potx");
  assert.equal(profile.kind, "potx");
  assert.ok(profile.layoutCount >= 5, "expected at least 5 layouts");
  const names = profile.layouts.map(l => l.name);
  for (const expected of ["Title Slide", "Title and Content", "Two Content", "Section Header", "Blank"]) {
    assert.ok(names.includes(expected), `expected layout "${expected}" among ${names.join(", ")}`);
  }
  const titleSlide = profile.layouts.find(l => l.name === "Title Slide");
  assert.ok(titleSlide.placeholders.length > 0);
  assert.ok(titleSlide.placeholders.some(p => p.type === "ctrTitle" || p.type === "title"));

  assert.ok(profile.themeColors && Object.keys(profile.themeColors).length > 0);
  assert.ok(profile.themeFonts.major);
  assert.ok(profile.themeFonts.minor);

  assert.ok(profile.slideSize);
  assert.equal(profile.slideSize.wIn, 13.33);
  assert.equal(profile.slideSize.hIn, 7.5);
});

// Test case 2: .pptx with 2 example slides -> same profile + existingSlides: 2.
test("case 2: .pptx with example slides reports exampleSlideCount", async () => {
  const profile = await loadProfile("sample-template.pptx");
  assert.equal(profile.kind, "pptx");
  assert.equal(profile.exampleSlideCount, 2);
  assert.ok(profile.layoutCount >= 5);
});

// Test case 3: a .txt renamed .potx -> named error, no crash.
test("case 3: a non-ZIP file renamed .potx throws a named error", async () => {
  const buf = await readFile(path.join(FIX, "not-a-template.potx"));
  const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  await assert.rejects(() => unzipAll(ab), /does not look like/);
});

// Test case 4: template with zero layouts -> layoutCount 0, no crash.
test("case 4: template with zero layouts reports layoutCount 0", async () => {
  const profile = await loadProfile("empty-template.potx");
  assert.equal(profile.layoutCount, 0);
  assert.deepEqual(profile.layouts, []);
});

// Test case 5: notes master present/absent -> notesSupported true/false.
test("case 5: notesSupported reflects presence of a notes master", async () => {
  const withNotes = await loadProfile("sample-template.potx");
  assert.equal(withNotes.notesSupported, true);

  const withoutNotes = await loadProfile("empty-template.potx");
  assert.equal(withoutNotes.notesSupported, false);
});
