/**
 * Drives ui.js's full state machine (upload -> parse -> review -> generate -> deliver)
 * against real modules and a real fixture docx + template, with only sample/downloads
 * mocked (those two are the only things that cannot run outside a published artifact).
 * This is the integration check ui.js never had: does the object shape runParse hands to
 * generatePlan/buildPptx/audit actually match what those modules expect end to end.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

class FakeNode {
  constructor(tag) {
    this.tag = tag; this.attrs = {}; this.children = []; this._text = "";
    this._listeners = {}; this.className = ""; this.disabled = false;
  }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(type, fn) { this._listeners[type] = fn; }
  appendChild(c) { this.children.push(c); return c; }
  replaceChildren(...nodes) { this.children = nodes.filter((n) => n != null); }
  querySelector(sel) { return sel.startsWith("#") ? findById(this, sel.slice(1)) : null; }
  set textContent(v) { this._text = v; this.children = []; }
  get textContent() { return this._text; }
}
function findById(node, id) {
  if (node.attrs?.id === id) return node;
  for (const c of node.children) {
    if (c instanceof FakeNode) { const hit = findById(c, id); if (hit) return hit; }
  }
  return null;
}
function findAll(node, pred, out = []) {
  if (node instanceof FakeNode) {
    if (pred(node)) out.push(node);
    node.children.forEach((c) => findAll(c, pred, out));
  }
  return out;
}
function getText(node) {
  if (!(node instanceof FakeNode)) return node?.text ?? "";
  if (node._text) return node._text;
  return node.children.map(getText).join("");
}

const rootEl = new FakeNode("div");
rootEl.attrs.id = "app";
globalThis.document = {
  createElement: (tag) => new FakeNode(tag),
  createTextNode: (text) => ({ text }),
  getElementById: (id) => (id === "app" ? rootEl : null),
  querySelector: (sel) => (sel.startsWith("#") ? findById(rootEl, sel.slice(1)) : null),
};
globalThis.URL = { createObjectURL: () => "blob:fake", revokeObjectURL: () => {} };
globalThis.Blob = class { constructor(parts, opts) { this.parts = parts; this.opts = opts; } };

const templateBytes = readFileSync("test/fixtures/templates/minimal.pptx");
const docxBytes = readFileSync("/tmp/sample-fsd.docx");

let savedFile = null;
globalThis.window = {
  claude: {
    use: async (name) => {
      if (name === "sample") return { json: mockSample };
      if (name === "downloads") return { save: async (f) => { savedFile = f; } };
      return null;
    },
  },
};

async function mockSample(prompt) {
  const bytes = new TextEncoder().encode(prompt).length;
  assert.ok(bytes <= 65536, `prompt exceeds sample's cap: ${bytes} bytes`);
  if (prompt.startsWith("You are drafting the intake brief")) {
    const m = /"section_id":\s*"([^"]+)"/.exec(prompt);
    const someSection = m ? m[1] : "sample-fsd#s1";
    return {
      system: "Test System", process_scope: "test",
      audiences: [{ audience_id: "requester", role_name: "Requester", tasks: ["do things"] }],
      learning_objectives: [
        { lo_id: "LO1", text: "Do the thing", bloom_level: "apply", audience_ids: ["requester"], sources: [someSection] },
      ],
      out_of_scope: [],
    };
  }
  if (prompt.startsWith("You are planning the module")) {
    return { modules: [
      { module_id: "cover", title: "Cover", order: 1, objective_ids: [], slides: [{ slide_id: "cover-1", role: "title-slide", title: "Cover" }] },
      { module_id: "mod-lo1", title: "Do the thing", order: 2, objective_ids: ["LO1"], slides: [{ slide_id: "s-lo1", role: "content", title: "Do the thing" }] },
    ] };
  }
  if (prompt.startsWith("Write the slide content")) {
    const m = /"section_id":\s*"([^"]+)"/.exec(prompt);
    const someSection = m ? m[1] : "sample-fsd#s1";
    return { slides: [{ slide_id: "s-lo1", role: "content", speaker_notes: "note",
      blocks: [{ slot: "title", kind: "text", content: "Do the thing", sources: [someSection] },
               { slot: "body", kind: "text", content: "Step one.\nStep two.", sources: [someSection] }] }] };
  }
  if (prompt.startsWith("Write exactly")) {
    return { questions: [1, 2, 3, 4, 5].map((n, i) => ({
      question_id: `Q${n}`, objective_id: "LO1",
      type: i % 2 === 0 ? "mcq" : "true-false", stem: `Question ${n}`,
      options: i % 2 === 0
        ? [{ option_id: "a", text: "A" }, { option_id: "b", text: "B" }, { option_id: "c", text: "C" }, { option_id: "d", text: "D" }]
        : [{ option_id: "t", text: "True" }, { option_id: "f", text: "False" }],
      key: [i % 2 === 0 ? "b" : "t"], rationale: "because", bloom_level: "apply",
      audience_ids: ["requester"],
    })) };
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}

const { initApp } = await import("../src/ui.js");
initApp();

// step 1: upload
let inputs = findAll(rootEl, (n) => n.tag === "input");
const [templateInput, sourceInput] = inputs;
templateInput._listeners.change({ target: { files: [{ name: "client-template.pptx", arrayBuffer: async () => templateBytes.buffer.slice(templateBytes.byteOffset, templateBytes.byteOffset + templateBytes.byteLength) }] } });
sourceInput._listeners.change({ target: { files: [{ name: "fsd.docx", arrayBuffer: async () => docxBytes.buffer.slice(docxBytes.byteOffset, docxBytes.byteOffset + docxBytes.byteLength) }] } });

let buttons = findAll(rootEl, (n) => n.tag === "button");
let goBtn = buttons.find((b) => getText(b) === "Parse documents");
assert.ok(goBtn && !goBtn.disabled, "expected enabled Parse documents button");
await goBtn._listeners.click();
// runParse is async; the onclick handler is `() => runParse(root)` — awaiting the click
// handler's return value only works if it's a promise, so poll briefly instead.
for (let i = 0; i < 50 && !findAll(rootEl, (n) => n.tag === "h2" && getText(n) === "2. Review").length && !findAll(rootEl, (n) => n.className === "notice notice--error").length; i++) {
  await new Promise((r) => setTimeout(r, 10));
}

let h2s = findAll(rootEl, (n) => n.tag === "h2");
console.log("after parse, headings:", h2s.map(getText));
const errorNotice = findAll(rootEl, (n) => n.className === "notice notice--error");
if (errorNotice.length) {
  console.log("ERROR STATE:", getText(errorNotice[0]));
  process.exit(1);
}
assert.ok(h2s.some((h) => getText(h) === "2. Review"), "expected to reach the Review step");

// step 2: review -> generate
buttons = findAll(rootEl, (n) => n.tag === "button");
const genBtn = buttons.find((b) => getText(b).startsWith("Generate deck"));
assert.ok(genBtn, "expected the Generate deck button");
genBtn._listeners.click();
for (let i = 0; i < 200; i++) {
  await new Promise((r) => setTimeout(r, 10));
  h2s = findAll(rootEl, (n) => n.tag === "h2");
  if (h2s.some((h) => getText(h) === "3. Deliver")) break;
  const err = findAll(rootEl, (n) => n.className === "notice notice--error");
  if (err.length) {
    console.log("ERROR STATE:", JSON.stringify(err[0].children));
    process.exit(1);
  }
}
h2s = findAll(rootEl, (n) => n.tag === "h2");
assert.ok(h2s.some((h) => getText(h) === "3. Deliver"), "expected to reach the Deliver step within timeout");

const statusPills = findAll(rootEl, (n) => n.className?.startsWith("status-pill"));
console.log("QA status pill:", statusPills[0]?.className, statusPills[0]?._text);

const dlBtn = findAll(rootEl, (n) => n.attrs.id === "dl-btn")[0];
assert.ok(dlBtn, "expected a download button");
await dlBtn._listeners.click();
assert.ok(savedFile, "expected downloads.save to have been called");
console.log("saved filename:", savedFile.filename, "bytes:", savedFile.data?.parts?.[0]?.length ?? savedFile.data?.byteLength);

console.log("\nui.js end-to-end smoke test passed.");

// Also verify the built file is structurally valid, not just non-throwing.
import { writeFileSync } from "node:fs";
const outBuf = savedFile.data.parts ? Buffer.concat(savedFile.data.parts.map((p) => Buffer.from(p))) : Buffer.from(savedFile.data);
writeFileSync("/tmp/e2e-out.pptx", outBuf);
console.log("wrote /tmp/e2e-out.pptx (" + outBuf.length + " bytes) for structural validation");
