#!/usr/bin/env node
/**
 * Profile a .potx/.pptx template via profile-template.js — the canonical profile for
 * everything in lib/deck/ (assemble.mjs, check-fit.mjs, map-layouts.js), used because it
 * carries two fields lib/profile_template.py's Python profiler does not: `slide_size`
 * (needed for every geometry fallback and fit check) and `example_slides` (needed to
 * strip the template's own demo slides at build time). The two profilers are NOT
 * interchangeable — this is a known, deliberate divergence, not an oversight: the three
 * other skills that read lib/profile_template.py's output (cm-proposal-generator,
 * cm-comms-generator, training-material-generator's build_training_deck.py) don't need
 * either field, and unifying the two schemas was out of scope for this build. Anything in
 * skills/deck-builder/ that needs a template profile calls THIS, not the Python one.
 *
 *     node lib/deck/cli/profile.mjs template.potx -o template_profile.json
 */
import { readFileSync, writeFileSync } from "node:fs";
import { profileTemplate } from "../profile-template.js";

const input = process.argv[2];
const outIdx = process.argv.indexOf("-o");
const outPath = outIdx >= 0 ? process.argv[outIdx + 1] : null;
if (!input) {
  console.error("usage: profile.mjs template.potx -o template_profile.json");
  process.exit(1);
}
const bytes = readFileSync(input);
const ab = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
const profile = await profileTemplate(ab);
const text = JSON.stringify(profile, null, 2);
if (outPath) { writeFileSync(outPath, text); console.log(`-> ${outPath}`); }
else console.log(text);
