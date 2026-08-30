/**
 * Build a representative deck against every template in the matrix and gate each output
 * on the pptx skill's own validate.py — the same structural gate the v0.2 deck passed.
 *
 *   node test/build-matrix.mjs
 *
 * The plan used here deliberately exercises every block kind and every layout role at
 * once (title, bullets, table, screenshot, all five diagram types, a [GAP] block and
 * speaker notes), so a template that can only host some of them shows up as warnings
 * rather than as a silent omission discovered later.
 */

import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { profileTemplate } from "../src/profile-template.js";
import { resolveLayoutRoles } from "../src/map-layouts.js";
import { buildPptx } from "../src/build-pptx.js";

const VALIDATE =
  "/root/.claude/skills/synced/9e312654-67aa-495a-bc6d-0685e7943d94_a893b1e2-c16b-4ff3-a80a-f61ace8bb8c0/pptx/scripts/office/validate.py";

const screenshot = readFileSync("test/fixtures/screenshot.png");

const plan = {
  modules: [
    {
      module_id: "cover", order: 1, slides: [
        { slide_id: "cover-1", role: "title-slide", blocks: [
          { slot: "title", kind: "text", content: "Supplier Block & Unblock" },
          { slot: "subtitle", kind: "text", content: "Generated from the FSD — first draft" },
        ] },
      ],
    },
    {
      module_id: "intro", order: 2, slides: [
        { slide_id: "intro-1", role: "section-header", blocks: [
          { slot: "title", kind: "text", content: "Why this is changing" },
        ] },
        { slide_id: "intro-2", role: "content",
          speaker_notes: "Open with the audit finding — it is real, and it is why this exists.",
          blocks: [
            { slot: "title", kind: "text", content: "What's Changing" },
            { slot: "body", kind: "bullets", content: [
              "One governed entry point replaces ad-hoc edits",
              "Every block needs a reason code and justification",
              "The requester can never approve their own request",
            ] },
          ] },
        { slide_id: "intro-3", role: "content", blocks: [
          { slot: "title", kind: "text", content: "Who Does What" },
          { slot: "body", kind: "table", content: {
            headers: ["Role", "Does", "Cannot Do"],
            rows: [
              ["Requester", "Submit requests", "Approve their own"],
              ["Category Manager", "Approve BQ*/BF*", "Approve BC* alone"],
              ["Compliance Officer", "Approve BC*", "—"],
            ],
          } },
        ] },
      ],
    },
    {
      module_id: "screens", order: 3, slides: [
        { slide_id: "shot-1", role: "picture", blocks: [
          { slot: "title", kind: "text", content: "Step 1 — Start From the Worklist" },
          { slot: "picture", kind: "image", content: { asset_id: "img1", caption: "Manage Supplier Block Requests" } },
        ] },
      ],
    },
    {
      module_id: "diagrams", order: 4, slides: [
        { slide_id: "d-process", role: "diagram", blocks: [
          { slot: "title", kind: "text", content: "Request Status Lifecycle" },
          { slot: "body", kind: "diagram", content: { diagram_type: "process", spec: { steps: ["DRAFT", "IN APPROVAL", "APPROVED", "ACTIVE"] } } },
        ] },
        { slide_id: "d-swim", role: "diagram", blocks: [
          { slot: "title", kind: "text", content: "End-to-End Process Flow" },
          { slot: "body", kind: "diagram", content: { diagram_type: "swimlane", spec: {
            roles: ["Requester", "System", "Approver", "S/4HANA Core"],
            steps: [
              { step: "Select supplier", role: "Requester" }, { step: "Enter reason", role: "Requester" },
              { step: "Validate", role: "System" }, { step: "Start workflow", role: "System" },
              { step: "Review & decide", role: "Approver" }, { step: "Set indicators", role: "S/4HANA Core" },
              { step: "Write audit log", role: "S/4HANA Core" }, { step: "Publish event", role: "S/4HANA Core" },
            ] } } },
        ] },
        { slide_id: "d-decision", role: "diagram", blocks: [
          { slot: "title", kind: "text", content: "Who Approves What" },
          { slot: "body", kind: "diagram", content: { diagram_type: "decision", spec: { rules: [
            { condition: "BC* — sanctions", outcome: "Compliance only. Central, no expiry" },
            { condition: "BQ* — quality", outcome: "Category Manager + Compliance" },
            { condition: "BF* — commercial", outcome: "Category Manager" },
          ] } } },
        ] },
        { slide_id: "d-hier", role: "diagram", blocks: [
          { slot: "title", kind: "text", content: "Approval Escalation" },
          { slot: "body", kind: "diagram", content: { diagram_type: "hierarchy", spec: { root: {
            name: "Director", children: [{ name: "Manager A", children: [{ name: "Team Lead" }] }, { name: "Manager B" }] } } } },
        ] },
        { slide_id: "d-time", role: "diagram", blocks: [
          { slot: "title", kind: "text", content: "Rollout Timeline" },
          { slot: "body", kind: "diagram", content: { diagram_type: "timeline", spec: { milestones: [
            { label: "Kickoff", date: "Jan 2026" }, { label: "UAT", date: "Feb 2026" }, { label: "Go-live", date: "Mar 2026" },
          ] } } },
        ] },
      ],
    },
    {
      module_id: "close", order: 5, slides: [
        { slide_id: "gap-1", role: "content", blocks: [
          { slot: "title", kind: "text", content: "Open Question" },
          { slot: "body", kind: "bullets", content: ["placeholder"], gap: true,
            gap_note: "The FSD does not state the escalation contact for a failed mass run." },
        ] },
        { slide_id: "two-1", role: "two-content", blocks: [
          { slot: "title", kind: "text", content: "Before and After" },
          { slot: "body", kind: "bullets", content: ["Ad-hoc email request", "No reason code"] },
          { slot: "body2", kind: "bullets", content: ["Governed request", "Reason code required"] },
        ] },
      ],
    },
  ],
};

const assets = new Map([["img1", { bytes: screenshot, ext: "png", alt: "Worklist screenshot" }]]);

const templates = [
  ...readdirSync("test/fixtures/templates").filter((f) => f.endsWith(".pptx"))
    .map((f) => ["test/fixtures/templates/" + f, f]),
  ["../training/supplier-block-unblock-20260829/template/placeholder.pptx", "placeholder.pptx"],
];

let failures = 0;
for (const [path, label] of templates) {
  const bytes = readFileSync(path);
  const profile = await profileTemplate(bytes);
  const { assignment, pictureFallback } = resolveLayoutRoles(profile);
  const { file, warnings, slideCount } = await buildPptx({
    templateBytes: bytes, profile, assignment, plan, assets,
  });
  const out = `test/out/built-${label}`;
  writeFileSync(out, file);

  let verdict;
  try {
    verdict = execFileSync("python3", [VALIDATE, out, "--original", path], { encoding: "utf8" }).trim().split("\n").pop();
  } catch (e) {
    verdict = "FAILED: " + (e.stdout || e.message).trim().split("\n").slice(-6).join(" | ");
    failures++;
  }
  console.log(`\n${label}  (${slideCount} slides${pictureFallback ? ", picture fallback" : ""})`);
  console.log(`  validate.py: ${verdict}`);
  warnings.slice(0, 4).forEach((w) => console.log(`  warn: ${w}`));
  if (warnings.length > 4) console.log(`  ... and ${warnings.length - 4} more warnings`);
}

console.log(failures ? `\n${failures} TEMPLATE(S) FAILED VALIDATION` : "\nAll templates produced valid decks.");
process.exit(failures ? 1 : 0);
