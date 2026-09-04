"use strict";

/* =================================================================
   Triage editing — the keyword classifier in triage()/scoreSection()
   is deliberately simple and will miss things. This module makes its
   verdicts correctable, whether the correction comes from a click on
   a clause row or from the assistant's proposed edit list. Both paths
   emit the same edit objects and go through the same validator, so a
   manual reclassify and an assistant-proposed one behave identically.

   Edit shapes:
     { op: "reclassify", sectionId, verdict }
     { op: "rename",      sectionId, heading }
     { op: "add",         heading, verdict?, excerpt? }
     { op: "remove",      sectionId }

   Every edit that actually changes something is stamped with an
   `edited` marker recording what it was before and who changed it —
   the whole tool's ethic is that machine output and human judgement
   stay visibly distinguishable, so an edited clause must never look
   identical to a freshly classified one.
   ================================================================= */

const VERDICTS = new Set(["cm-core", "cm-adjacent", "not-cm"]);

function findSection(sections, id) {
  return sections.find(s => s.id === id) || null;
}

/* Rejects only malformed edits — an unknown sectionId, an unknown op,
   an invalid verdict, an empty rename. "Remove a parsed (non-manual)
   clause" is NOT rejected here: that is a semantic transform (demote
   to not-cm) applyTriageEdits performs, not a validation failure. */
function validateEdits(triage, edits) {
  const sections = (triage && triage.sections) || [];
  const valid = [];
  const errors = [];

  for (const edit of edits || []) {
    if (!edit || typeof edit !== "object" || typeof edit.op !== "string") {
      errors.push({ edit, reason: "malformed edit" });
      continue;
    }

    if (edit.op === "add") {
      if (edit.verdict !== undefined && !VERDICTS.has(edit.verdict)) {
        errors.push({ edit, reason: `unknown verdict "${edit.verdict}"` });
        continue;
      }
      if (typeof edit.heading !== "string" || !edit.heading.trim()) {
        errors.push({ edit, reason: "a clause needs a heading" });
        continue;
      }
      valid.push(edit);
      continue;
    }

    if (typeof edit.sectionId !== "string" || !findSection(sections, edit.sectionId)) {
      errors.push({ edit, reason: `unknown section id "${edit.sectionId}"` });
      continue;
    }

    if (edit.op === "reclassify") {
      if (!VERDICTS.has(edit.verdict)) {
        errors.push({ edit, reason: `unknown verdict "${edit.verdict}"` });
        continue;
      }
      valid.push(edit);
    } else if (edit.op === "rename") {
      if (typeof edit.heading !== "string" || !edit.heading.trim()) {
        errors.push({ edit, reason: "a heading can't be renamed to nothing" });
        continue;
      }
      valid.push(edit);
    } else if (edit.op === "remove") {
      valid.push(edit);
    } else {
      errors.push({ edit, reason: `unknown op "${edit.op}"` });
    }
  }

  return { valid, errors };
}

function recountTriage(sections) {
  return sections.reduce(
    (acc, s) => (acc[s.verdict] = (acc[s.verdict] || 0) + 1, acc),
    { "cm-core": 0, "cm-adjacent": 0, "not-cm": 0 }
  );
}

let manualCounter = 0;
function nextManualId() {
  manualCounter += 1;
  return `manual-${Date.now().toString(36)}-${manualCounter}`;
}

/* Applies a batch of edits to a triage object, returning a NEW triage
   (the input is never mutated) plus the batch's validation errors.
   Invalid edits are dropped and reported; every valid edit in the
   batch still applies — one bad edit in a batch must never lose the
   rest, since the assistant may propose several at once. */
function applyTriageEdits(triage, edits, source = "user") {
  const { valid, errors } = validateEdits(triage, edits);
  const sections = (triage.sections || []).map(s => ({ ...s }));

  for (const edit of valid) {
    if (edit.op === "reclassify") {
      const sec = findSection(sections, edit.sectionId);
      if (sec.verdict === edit.verdict) continue;
      const from = sec.verdict;
      sec.verdict = edit.verdict;
      sec.edited = { field: "verdict", from, source };
    } else if (edit.op === "rename") {
      const sec = findSection(sections, edit.sectionId);
      const heading = edit.heading.trim();
      if (sec.heading === heading) continue;
      const from = sec.heading;
      sec.heading = heading;
      sec.edited = { field: "heading", from, source };
    } else if (edit.op === "add") {
      const excerpt = (edit.excerpt || "").trim();
      sections.push({
        id: nextManualId(),
        ref: "(added)",
        heading: edit.heading.trim(),
        body: excerpt,
        excerpt,
        offset: null,
        page: null,
        verdict: edit.verdict || "cm-core",
        score: 0,
        coverage: 0,
        strong: [],
        offTopic: 0,
        cues: [],
        manual: true,
        edited: { field: "added", from: null, source },
      });
    } else if (edit.op === "remove") {
      const idx = sections.findIndex(s => s.id === edit.sectionId);
      if (idx === -1) continue;
      if (sections[idx].manual) {
        sections.splice(idx, 1);
      } else {
        // A parsed clause carries evidence from the tender itself — deleting
        // it would throw that evidence away. Demote it instead: same effect
        // on the outline (it drops out of cm-core), but the clause and its
        // excerpt stay visible and reversible.
        const from = sections[idx].verdict;
        if (from !== "not-cm") {
          sections[idx] = {
            ...sections[idx],
            verdict: "not-cm",
            edited: { field: "verdict", from, source, note: "removal refused for a parsed clause; demoted instead" },
          };
        }
      }
    }
  }

  return {
    triage: { ...triage, sections, counts: recountTriage(sections) },
    errors,
  };
}

/* A compact, budget-bounded listing of every clause for the assistant
   prompt: id, ref, page, current verdict, heading, a short excerpt.
   Stops adding clauses once the budget is spent and says how many
   were left out, rather than silently truncating the list. */
function sectionDigest(triage, budgetBytes = 20000) {
  const encoder = new TextEncoder();
  const byteLen = s => encoder.encode(s).length;
  const sections = (triage && triage.sections) || [];

  const lines = [];
  let used = 0;
  let included = 0;
  for (const s of sections) {
    const excerpt = (s.excerpt || s.body || "").replace(/\s+/g, " ").trim().slice(0, 160);
    const line = `${s.id} | ${s.ref || "(no ref)"} | page ${s.page ?? "?"} | [${s.verdict}] `
      + `${s.heading || "(no heading)"} :: ${excerpt}`;
    const lineBytes = byteLen(line) + 1;
    if (used + lineBytes > budgetBytes && included > 0) break;
    lines.push(line);
    used += lineBytes;
    included += 1;
  }

  const omitted = sections.length - included;
  if (omitted > 0) {
    lines.push(`(${omitted} more clause(s) not listed here — ask about one by its heading if you need it)`);
  }
  return lines.join("\n");
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { VERDICTS, validateEdits, applyTriageEdits, recountTriage, sectionDigest };
}
