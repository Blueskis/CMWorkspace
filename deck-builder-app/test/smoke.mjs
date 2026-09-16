/**
 * Smoke test for deck-builder-app's own modules — pure functions only (deck-plan.js's
 * prompt builders, validate-plan.js, and a ui.js import check that the bundle graph
 * resolves). sample()/sample.json() cannot run in Node, so plan generation itself is
 * exercised with a mocked sampleJson, same pattern as webapp/test/plan.mjs.
 *
 *   node test/smoke.mjs
 */
import assert from "node:assert/strict";
import { briefPrompt, planPrompt, generateDeckPlan } from "../src/deck-plan.js";
import { checkDeckType, checkProvenance, validatePlan } from "../src/validate-plan.js";
import { DECK_TYPES, DECK_TYPE_ORDER } from "../../lib/deck/deck-types.js";
import deckRegistryJson from "../../lib/schemas/deck_registry.json" with { type: "json" };

let failures = 0;
function check(label, cond, detail = "") {
  if (cond) console.log(`  ok  ${label}`);
  else { failures++; console.log(`  FAIL ${label} ${detail}`); }
}

// --- deck-types.js parity with the JSON source (case: registry drift guard) ---
check("deck-types.js matches lib/schemas/deck_registry.json byte-for-byte (as data)",
  JSON.stringify(DECK_TYPES) === JSON.stringify(deckRegistryJson.deck_types));
check("DECK_TYPE_ORDER covers all 11 registry entries", DECK_TYPE_ORDER.length === 11);

// --- prompt builders stay within sample's input budget ---
const corpus = {
  documents: [{ document_id: "doc1" }],
  sections: Array.from({ length: 40 }, (_, i) => ({
    section_id: `doc1#${i}`, document_id: "doc1", section_path: `doc1 / Section ${i}`,
    text: "Lorem ipsum ".repeat(50),
  })),
};
const deckType = DECK_TYPES["status-update"];
const bp = briefPrompt(corpus, deckType, null);
check("briefPrompt stays under 64 KiB", new TextEncoder().encode(bp).length < 64 * 1024, `${bp.length} chars`);
check("briefPrompt names the deck type", bp.includes(deckType.label));

const brief = { key_messages: [{ message_id: "m1", statement: "Programme is on track.", sources: ["doc1#0"] }] };
const pp = planPrompt(brief, deckType, corpus, null);
check("planPrompt stays under 64 KiB", new TextEncoder().encode(pp).length < 64 * 1024);
check("planPrompt lists the required role sequence", pp.includes(JSON.stringify(deckType.required_roles)));

// --- generateDeckPlan against a mocked sampleJson (case: deck-type-aware generation shape) ---
const mockPlan = {
  modules: [{ module_id: "m1", slides: [
    { slide_id: "s1", role: "title-slide", title: "Programme Update", blocks: [{ slot: "title", kind: "text", content: "Programme Update", sources: ["m1"] }] },
    { slide_id: "s2", role: "metric-row", title: "Status", blocks: [{ slot: "title", kind: "text", content: "Status", sources: ["m1"] }, { slot: "body", kind: "text", content: "80% complete", sources: ["doc1#0"] }] },
    { slide_id: "s3", role: "content", title: "Detail", blocks: [{ slot: "title", kind: "text", content: "Detail", sources: ["m1"] }] },
    { slide_id: "s4", role: "content", title: "More detail", blocks: [{ slot: "title", kind: "text", content: "More", sources: ["m1"] }] },
    { slide_id: "s5", role: "closing", title: "Thank you", blocks: [{ slot: "title", kind: "text", content: "Thank you", sources: ["m1"] }] },
  ] }],
};
let call = 0;
const mockSampleJson = async () => {
  call++;
  return call === 1 ? JSON.stringify(brief) : JSON.stringify(mockPlan);
};
const generated = await generateDeckPlan(corpus, deckType, { sampleJson: mockSampleJson });
check("generateDeckPlan returns brief + plan", !!generated.brief && !!generated.plan);
check("generateDeckPlan calls sampleJson exactly twice (brief, plan)", call === 2);

// --- validate-plan.js: deck-type role sequence check (case: deck registry validation) ---
const roleErrors = checkDeckType(mockPlan, deckType);
check("valid role sequence passes checkDeckType", roleErrors.length === 0, JSON.stringify(roleErrors));

const badPlan = { modules: [{ module_id: "m1", slides: [{ slide_id: "s1", role: "content", blocks: [] }] }] };
const badErrors = checkDeckType(badPlan, deckType);
check("missing required roles fails checkDeckType", badErrors.length === 1);

// --- provenance check (case: no third state) ---
const noProvPlan = { modules: [{ module_id: "m1", slides: [{ slide_id: "s1", role: "content", blocks: [{ slot: "body", kind: "text", content: "x" }] }] }] };
check("block with neither sources nor gap fails checkProvenance", checkProvenance(noProvPlan).length === 1);
const gapPlan = { modules: [{ module_id: "m1", slides: [{ slide_id: "s1", role: "content", blocks: [{ slot: "body", kind: "text", content: "x", gap: true, gap_note: "no source" }] }] }] };
check("gap:true with gap_note passes checkProvenance", checkProvenance(gapPlan).length === 0);

// --- unknown deck type is a data-level error, never silently accepted ---
check("DECK_TYPES has no 'webinar' entry (case: unknown deck type must be rejected upstream)", !("webinar" in DECK_TYPES));

if (failures) {
  console.log(`\n${failures} check(s) FAILED.`);
  process.exit(1);
}
console.log("\nAll deck-builder-app smoke checks passed.");
