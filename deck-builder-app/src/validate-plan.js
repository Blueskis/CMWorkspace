/**
 * Plan-time validation for the browser — the JS-in-artifact equivalent of
 * skills/deck-builder/scripts/plan_deck.py, minus the vision-notes confidence check
 * (this artifact has no vision pass; PDFs/images are parsed for text/embedded images
 * only, same as webapp/'s training pipeline).
 *
 * Four checks, same as the Python skill:
 *   - deck type: the plan's slide roles must include the deck type's required_roles,
 *     in order, as a subsequence.
 *   - provenance: every non-gap block needs sources[]; every gap block needs gap_note.
 *   - fit: lib/deck/fit-check.js's checkManifestFit, against the resolved layout geometry.
 *   - variety: lib/deck/fit-check.js's checkVariety, no >2 consecutive same-layout slides.
 */

import { targetPlaceholders } from "../../lib/deck/map-layouts.js";
import { checkManifestFit, checkVariety } from "../../lib/deck/fit-check.js";

export function checkDeckType(plan, deckType) {
  const errors = [];
  const rolesInPlan = (plan.modules ?? []).flatMap((m) => (m.slides ?? []).map((s) => s.role));
  const required = deckType.required_roles;
  let ptr = 0;
  for (const role of rolesInPlan) {
    if (ptr < required.length && role === required[ptr]) ptr++;
  }
  if (ptr < required.length) {
    errors.push(
      `"${deckType.label}" requires these roles, in order, and the plan is missing ` +
      `(from position ${ptr}): ${JSON.stringify(required.slice(ptr))} — plan has: ${JSON.stringify(rolesInPlan)}`
    );
  }
  return errors;
}

export function checkProvenance(plan) {
  const errors = [];
  for (const mod of plan.modules ?? []) {
    for (const slide of mod.slides ?? []) {
      (slide.blocks ?? []).forEach((block, i) => {
        const where = `${slide.slide_id} block ${i} (${block.slot})`;
        if (block.gap) {
          if (!block.gap_note) errors.push(`${where}: gap is true but gap_note is missing`);
        } else if (!block.sources || block.sources.length === 0) {
          errors.push(`${where}: no sources and gap is not true — no third state allowed`);
        }
      });
    }
  }
  return errors;
}

function geomOf(ph, fallback) {
  return ph?.geometry ? [ph.geometry.x_in, ph.geometry.y_in, ph.geometry.w_in, ph.geometry.h_in] : fallback;
}

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
        let ph = null, bbox = null;
        if (block.slot === "title") {
          ph = targets?.title;
          bbox = geomOf(ph, [0.6, 0.6, (profile.slide_size?.w_in ?? 10) - 1.2, 1.1]);
        } else if (block.slot === "body" || block.slot === "body2" || block.slot === "subtitle") {
          const idx = block.slot === "body2" ? 1 : 0;
          ph = targets?.bodies?.[idx] ?? targets?.bodies?.[0] ?? targets?.subTitle;
          bbox = geomOf(ph, [0.6, 1.6, (profile.slide_size?.w_in ?? 10) - 1.2, (profile.slide_size?.h_in ?? 5.6) - 2.4]);
        }
        if (!bbox) continue;
        fills.push({
          kind: "text",
          placeholder: ph?.type === "ctrTitle" || ph?.type === "title" ? "title" : (block.slot ?? "body"),
          bbox, content: block.content, gap: !!block.gap,
        });
      }
      steps.push({ position, slide_id: slide.slide_id, layout_part: layoutPart, fills });
    }
  }
  return steps;
}

export function checkFitAndVariety(plan, profile, assignment) {
  const steps = flattenForFitCheck(plan, profile, assignment);
  const fit = checkManifestFit(steps);
  const pictureCapableLayoutParts = (profile.layouts ?? [])
    .filter((l) => l.has_picture_placeholder).map((l) => l.part);
  const variety = checkVariety(steps, { pictureCapableLayoutParts });
  return {
    failures: [...fit.failures.map((f) => ({ type: "fit", ...f })), ...variety.failures.map((f) => ({ type: "variety", ...f }))],
    warnings: [...fit.warnings.map((w) => ({ type: "fit", ...w })), ...variety.warnings.map((w) => ({ type: "variety", ...w }))],
  };
}

/** Runs all four checks; returns { hardFail, failures, warnings } — same report shape
 * as plan_deck.py's plan_validation.json. */
export function validatePlan(plan, deckType, profile, assignment) {
  const deckTypeErrors = checkDeckType(plan, deckType);
  const provenanceErrors = checkProvenance(plan);
  const fitVariety = checkFitAndVariety(plan, profile, assignment);
  const failures = [
    ...deckTypeErrors.map((message) => ({ type: "deck-type", message })),
    ...provenanceErrors.map((message) => ({ type: "provenance", message })),
    ...fitVariety.failures,
  ];
  return { hardFail: failures.length > 0, failures, warnings: fitVariety.warnings };
}
