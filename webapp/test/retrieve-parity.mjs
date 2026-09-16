/**
 * Parity check between lib/deck_index.py and lib/deck/retrieve.js — deck-builder test
 * case #21. Same fixture, same queries, both implementations must return the same
 * ranked chunk_id order. This is what lets the repo's no-embeddings BM25 choice stand:
 * two independent implementations agreeing on ranking is the actual evidence the
 * scoring is deterministic and language-independent, not a claim taken on faith.
 *
 *   node test/retrieve-parity.mjs
 */
import { execFileSync } from "node:child_process";
import { writeFileSync, mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { buildIndex, queryIndex } from "../../lib/deck/retrieve.js";

const sourceMap = {
  run_id: "parity-test",
  sections: [
    { section_id: "doc#1", document_id: "doc", section_path: "doc / Approvals", classifier: "procedure",
      text: "The approval threshold for a purchase order is set by finance policy. Colleagues must route requests through the manager for sign-off." },
    { section_id: "doc#2", document_id: "doc", section_path: "doc / Staffing", classifier: "narrative",
      text: "Staff headcount for the programme is reviewed quarterly by the sponsor and finance business partner." },
    { section_id: "doc#3", document_id: "doc", section_path: "doc / Risks", classifier: "reference",
      text: "Key risks include vendor delay, data migration errors, and change fatigue among frontline staff." },
  ],
};
const visionNotes = { notes: [
  { note_id: "v1", source_ref: "diagram.pdf", page: 1, kind: "diagram",
    transcription: "Approval workflow: requester submits, manager approves, finance releases funds.", confidence: "medium" },
] };

const dir = mkdtempSync(join(tmpdir(), "retrieve-parity-"));
const smPath = join(dir, "source_map.json");
const vnPath = join(dir, "vision_notes.json");
writeFileSync(smPath, JSON.stringify(sourceMap));
writeFileSync(vnPath, JSON.stringify(visionNotes));

const pyIndexPath = join(dir, "chunk_index.json");
execFileSync("python3", [join(process.cwd(), "..", "lib", "deck_index.py"), "index", smPath, vnPath, "-o", pyIndexPath]);
const pyIndex = JSON.parse(readFileSync(pyIndexPath, "utf8"));
const jsIndex = buildIndex(sourceMap, visionNotes);

let failures = 0;
function check(label, cond, detail = "") {
  if (cond) console.log(`  ok  ${label}`);
  else { failures++; console.log(`  FAIL ${label} ${detail}`); }
}

check("chunk_count matches", pyIndex.chunk_count === jsIndex.chunk_count, `py=${pyIndex.chunk_count} js=${jsIndex.chunk_count}`);

const queries = [
  { query: "approval threshold" },
  { query: "workflow approves" }, // should surface the vision chunk
  { query: "headcount" },
  { query: "staff members", brandProfile: { messaging: { terminology: [{ term: "colleagues", definition: "staff members" }] } } },
];

for (const q of queries) {
  const pyOut = execFileSync("python3", [
    join(process.cwd(), "..", "lib", "deck_index.py"), "query", pyIndexPath,
    "--query", q.query, "--top", "10", "--json",
    ...(q.brandProfile ? (() => {
      const bp = join(dir, "brand.json");
      writeFileSync(bp, JSON.stringify(q.brandProfile));
      return ["--brand", bp];
    })() : []),
  ], { encoding: "utf8" });
  const pyResults = JSON.parse(pyOut).map((c) => c.chunk_id);
  const jsResults = queryIndex(jsIndex, { query: q.query, top: 10, brandProfile: q.brandProfile }).map((c) => c.chunk_id);
  check(`"${q.query}" ranking matches`, JSON.stringify(pyResults) === JSON.stringify(jsResults),
    `py=${JSON.stringify(pyResults)} js=${JSON.stringify(jsResults)}`);
}

rmSync(dir, { recursive: true, force: true });

if (failures) {
  console.log(`\n${failures} parity check(s) FAILED.`);
  process.exit(1);
}
console.log("\nAll deck_index.py / retrieve.js parity checks passed.");
