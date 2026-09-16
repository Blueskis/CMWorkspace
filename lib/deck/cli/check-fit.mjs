#!/usr/bin/env node
/**
 * Plan-time fit and variety gates, as a CLI — so plan_deck.py (Python) can call the same
 * text-fit.js arithmetic composeSlide uses at build time, rather than a second Python
 * reimplementation of line-wrap math that could silently drift from what actually ships.
 * Same subprocess pattern build_docx.py already uses for the docx-js build.
 *
 *     node lib/deck/cli/check-fit.mjs --plan deck_plan.json --profile template_profile.json --assignment assignment.json
 *
 * Prints one JSON object: { failures: [...], warnings: [...] } from fit-check.js's
 * checkManifestFit + checkVariety, after flattening deck_plan.json's
 * modules[].slides[].blocks[] into the {slide_id, layout_part, fills:[{kind, placeholder,
 * bbox, content, gap}]} shape those functions expect. Exits 1 iff there are any failures.
 */
import { readFileSync } from "node:fs";
import { targetPlaceholders } from "../map-layouts.js";
import { checkManifestFit, checkVariety } from "../fit-check.js";

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) { out[argv[i].slice(2)] = argv[i + 1]; i++; }
  }
  return out;
}

function geomOf(ph, fallback) {
  return ph?.geometry ? [ph.geometry.x_in, ph.geometry.y_in, ph.geometry.w_in, ph.geometry.h_in] : fallback;
}

/** Flatten a deck_plan.json (native buildPptx shape) into fit-check's manifest shape. */
function flattenForFitCheck(plan, profile, assignment) {
  const steps = [];
  let position = 0;
  for (const mod of plan.modules ?? []) {
    for (const slide of mod.slides ?? []) {
      position++;
      const roleAssignment = assignment[slide.role] ?? assignment.content;
      const layoutPart = roleAssignment?.part ?? null;
      const targets = layoutPart ? targetPlaceholders(profile, layoutPart) : null;
      const fills = [];
      for (const block of slide.blocks ?? []) {
        if (block.kind !== "text" || block.gap) continue;
        let ph = null;
        let bbox = null;
        if (block.slot === "title") { ph = targets?.title; bbox = geomOf(ph, [0.6, 0.6, (profile.slide_size?.w_in ?? 10) - 1.2, 1.1]); }
        else if (block.slot === "body" || block.slot === "body2" || block.slot === "subtitle") {
          const idx = block.slot === "body2" ? 1 : 0;
          ph = targets?.bodies?.[idx] ?? targets?.bodies?.[0] ?? targets?.subTitle;
          bbox = geomOf(ph, [0.6, 1.6, (profile.slide_size?.w_in ?? 10) - 1.2, (profile.slide_size?.h_in ?? 5.6) - 2.4]);
        }
        if (!bbox) continue;
        fills.push({
          kind: "text",
          placeholder: ph?.type === "ctrTitle" || ph?.type === "title" ? "title" : (block.slot ?? "body"),
          bbox,
          content: block.content,
          gap: !!block.gap,
        });
      }
      steps.push({ position, slide_id: slide.slide_id, layout_part: layoutPart, fills });
    }
  }
  return steps;
}

const args = parseArgs(process.argv.slice(2));
const plan = JSON.parse(readFileSync(args.plan, "utf8"));
const profile = JSON.parse(readFileSync(args.profile, "utf8"));
const assignment = JSON.parse(readFileSync(args.assignment, "utf8"));

const steps = flattenForFitCheck(plan, profile, assignment);
const fit = checkManifestFit(steps);
const pictureCapableLayoutParts = (profile.layouts ?? [])
  .filter((l) => l.has_picture_placeholder)
  .map((l) => l.part);
const variety = checkVariety(steps, { pictureCapableLayoutParts });

const report = {
  failures: [...fit.failures.map((f) => ({ type: "fit", ...f })), ...variety.failures.map((f) => ({ type: "variety", ...f }))],
  warnings: [...fit.warnings.map((w) => ({ type: "fit", ...w })), ...variety.warnings.map((w) => ({ type: "variety", ...w }))],
};
console.log(JSON.stringify(report, null, 2));
process.exit(report.failures.length ? 1 : 0);
