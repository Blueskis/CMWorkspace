/**
 * Mechanical QA over a generated deck plan.
 *
 * Browser port of qa_training.py. Same five checks, same distinction between hard
 * failures (objective coverage, source coverage, provenance) and soft ones reported but
 * not blocking (asset hygiene, question sanity) — see that script's own docstring for the
 * exact rules; this is a direct translation, not a redesign.
 */

export function audit(brief, plan, corpus, questions) {
  const objectives = Object.fromEntries((brief.learning_objectives ?? []).map((o) => [o.lo_id, o]));
  const outOfScope = new Set((brief.out_of_scope ?? []).map((e) => e.section_id));
  const sections = Object.fromEntries(corpus.sections.map((s) => [s.section_id, s]));
  const assetsById = Object.fromEntries(corpus.assets.map((a) => [a.asset_id, a]));
  const unusedDeclared = Object.fromEntries((plan.unused_assets ?? []).map((e) => [e.asset_id, e.reason]));

  const loToSlides = {};
  const sourcedSections = new Set();
  const placedAssets = new Set();
  const missingProvenance = [];
  const gapMissingNote = [];

  for (const mod of plan.modules ?? []) {
    for (const lo of mod.objective_ids ?? []) loToSlides[lo] = loToSlides[lo] ?? [];
    for (const slide of mod.slides ?? []) {
      const modLos = mod.objective_ids ?? [];
      for (let i = 0; i < (slide.blocks ?? []).length; i++) {
        const block = slide.blocks[i];
        const where = `${mod.module_id} / ${slide.slide_id} / block ${i}`;
        const isGap = !!block.gap;
        if (isGap) {
          if (!block.gap_note) gapMissingNote.push(where);
        } else if (!block.sources || block.sources.length === 0) {
          missingProvenance.push(where);
        } else {
          for (const lo of modLos) loToSlides[lo].push(slide.slide_id);
          for (const src of block.sources) sourcedSections.add(src);
        }
        if (block.kind === "image" && !isGap && block.content?.asset_id) {
          placedAssets.add(block.content.asset_id);
        }
      }
    }
  }

  const loNoSlide = Object.keys(objectives).filter((lo) => !(loToSlides[lo] ?? []).length);

  let loNoQuestion = [];
  const questionErrors = [];
  const questionsChecked = questions != null;
  if (questionsChecked) {
    const qByLo = {};
    for (const q of questions.questions ?? []) {
      qByLo[q.objective_id] = qByLo[q.objective_id] ?? [];
      qByLo[q.objective_id].push(q);
      const optionIds = new Set((q.options ?? []).map((o) => o.option_id));
      const badKeys = (q.key ?? []).filter((k) => !optionIds.has(k));
      if (badKeys.length) questionErrors.push(`${q.question_id}: key references unknown option(s) ${JSON.stringify(badKeys)}`);
      if (["mcq", "true-false"].includes(q.type) && (q.key ?? []).length !== 1) {
        questionErrors.push(`${q.question_id}: type '${q.type}' must have exactly one key`);
      }
      if (q.type === "multi" && (q.key ?? []).length < 1) {
        questionErrors.push(`${q.question_id}: type 'multi' needs at least one key`);
      }
      if (q.type === "mcq" && (q.options ?? []).length < 4) {
        questionErrors.push(`${q.question_id}: mcq has only ${(q.options ?? []).length} option(s) — needs >=4 (1 correct + >=3 distractors)`);
      }
      if (!(q.objective_id in objectives)) {
        questionErrors.push(`${q.question_id}: objective_id '${q.objective_id}' not in training_brief.json`);
      }
      for (const src of q.sources ?? []) {
        if (!(src in sections)) questionErrors.push(`${q.question_id}: source '${src}' not in source_map.json`);
      }
    }
    loNoQuestion = Object.keys(objectives).filter((lo) => !(qByLo[lo] ?? []).length);
  }

  const uncoveredProcedures = Object.values(sections)
    .filter((s) => s.classifier === "procedure" && !sourcedSections.has(s.section_id) && !outOfScope.has(s.section_id))
    .map((s) => s.section_id);

  const screenshotIds = new Set(corpus.assets.filter((a) => a.role === "screenshot").map((a) => a.asset_id));
  const unplacedScreenshots = [...screenshotIds].filter((id) => !placedAssets.has(id) && !(id in unusedDeclared));

  const lowResPlacedUnacked = [];
  for (const mod of plan.modules ?? []) {
    for (const slide of mod.slides ?? []) {
      for (const block of slide.blocks ?? []) {
        if (block.kind !== "image" || block.gap) continue;
        const asset = assetsById[block.content?.asset_id];
        if (asset && (asset.quality ?? []).includes("low_res") && !block.content?.ack_low_res) {
          lowResPlacedUnacked.push(`${slide.slide_id}: ${block.content.asset_id}`);
        }
      }
    }
  }

  return {
    objectives, loNoSlide, loNoQuestion, questionsChecked, questionErrors,
    missingProvenance, gapMissingNote, uncoveredProcedures, sections,
    unplacedScreenshots, unusedDeclared, lowResPlacedUnacked,
  };
}

export function hardFail(result) {
  return !!(
    result.loNoSlide.length ||
    result.missingProvenance.length ||
    result.gapMissingNote.length ||
    result.uncoveredProcedures.length ||
    (result.questionsChecked && result.loNoQuestion.length)
  );
}

/** Render the same report shape qa_training.py writes, for the in-page QA panel. */
export function renderReport(result, planRunId) {
  const lines = [];
  const push = (...s) => lines.push(...s);

  push(`# Training QA Report — ${planRunId ?? "unnamed run"}`, "");
  push(`**Status:** ${hardFail(result) ? "FAIL — must fix before handover" : "PASS (mechanical checks)"}`, "");

  push("## 1. Objective coverage", "");
  const objCount = Object.keys(result.objectives).length;
  push(`${objCount - result.loNoSlide.length} of ${objCount} objective(s) reach a content slide.`);
  if (result.loNoSlide.length) {
    push("", "### Objectives with no content slide");
    result.loNoSlide.forEach((lo) => push(`- \`${lo}\` — ${result.objectives[lo].text}`));
  }
  if (!result.questionsChecked) {
    push("", "> Question bank not supplied — the question half of this check and check 5 were skipped.");
  } else {
    push("", `${objCount - result.loNoQuestion.length} of ${objCount} objective(s) reach a knowledge-check question.`);
    if (result.loNoQuestion.length) {
      push("", "### Objectives with no question");
      result.loNoQuestion.forEach((lo) => push(`- \`${lo}\` — ${result.objectives[lo].text}`));
    }
  }

  push("", "## 2. Source coverage", "");
  if (result.uncoveredProcedures.length) {
    push("### FAIL — 'procedure' sections neither taught nor declared out of scope", "");
    result.uncoveredProcedures.forEach((id) => push(`- \`${id}\` — ${result.sections[id].section_path}`));
  } else {
    push("Every 'procedure' section is either taught or listed in `out_of_scope`.");
  }

  push("", "## 3. Provenance", "");
  if (result.missingProvenance.length) {
    push("### FAIL — blocks with neither sources nor gap: true", "");
    result.missingProvenance.forEach((w) => push(`- ${w}`));
  } else {
    push("Every content block carries sources or `gap: true`.");
  }
  if (result.gapMissingNote.length) {
    push("", "### FAIL — gap: true blocks missing gap_note", "");
    result.gapMissingNote.forEach((w) => push(`- ${w}`));
  }

  push("", "## 4. Asset hygiene", "");
  if (result.unplacedScreenshots.length) {
    push("### Screenshot assets not placed and not declared in `unused_assets`", "");
    result.unplacedScreenshots.forEach((id) => push(`- \`${id}\``));
  } else {
    push("Every screenshot-role asset is placed or explicitly declared unused.");
  }
  if (result.lowResPlacedUnacked.length) {
    push("", "### Low-res assets placed without acknowledgement", "");
    result.lowResPlacedUnacked.forEach((w) => push(`- ${w}`));
  }
  const unusedEntries = Object.entries(result.unusedDeclared);
  if (unusedEntries.length) {
    push("", "### Declared unused", "");
    unusedEntries.forEach(([id, reason]) => push(`- \`${id}\` — ${reason}`));
  }

  if (result.questionsChecked) {
    push("", "## 5. Question sanity", "");
    if (result.questionErrors.length) {
      result.questionErrors.forEach((e) => push(`- ${e}`));
    } else {
      push("No structural defects found in the question bank.");
    }
  }

  push("", "## Handover", "");
  push("This is a **first draft for practitioner review**, not finished training material.");
  return lines.join("\n");
}
