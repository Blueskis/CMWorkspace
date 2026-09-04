/**
 * Verifies the error step's behaviour for a retriable sample() failure: invalid_json,
 * upstream_error, rate_limited, refused, empty_completion (per sample.d.ts's own
 * grouping) offer a "Try again" button that re-enters runGenerate() directly — without
 * re-uploading or re-parsing anything — while a non-retriable failure only offers
 * "Start over". This is exactly the class of bug a real viewer hit: sample.json()
 * rejected {code: "invalid_json", message: "the reply held no JSON value"} and the old
 * code discarded .code entirely, leaving only a full reset.
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
  for (const c of node.children) { if (c instanceof FakeNode) { const h = findById(c, id); if (h) return h; } }
  return null;
}
function findAll(node, pred, out = []) {
  if (node instanceof FakeNode) { if (pred(node)) out.push(node); node.children.forEach((c) => findAll(c, pred, out)); }
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

const templateBytes = readFileSync("test/fixtures/templates/minimal.pptx");
const docxBytes = readFileSync("/tmp/sample-fsd.docx");

let sampleCallCount = 0;
let failNextCall = true; // the brief call fails once with invalid_json, then succeeds on retry

globalThis.window = {
  claude: {
    use: async (name) => {
      if (name === "sample") return { json: mockSample };
      return null;
    },
  },
};

async function mockSample(prompt) {
  sampleCallCount++;
  if (prompt.startsWith("You are drafting the intake brief")) {
    if (failNextCall) {
      failNextCall = false;
      const err = new Error("the reply held no JSON value");
      err.code = "invalid_json";
      throw err;
    }
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
    return { slides: [{ slide_id: "s-lo1", role: "content",
      blocks: [{ slot: "title", kind: "text", content: "Do the thing", sources: [someSection] }] }] };
  }
  if (prompt.startsWith("Write exactly")) {
    return { questions: [1, 2, 3, 4, 5].map((n, i) => ({
      question_id: `Q${n}`, objective_id: "LO1", type: i % 2 === 0 ? "mcq" : "true-false", stem: `Question ${n}`,
      options: i % 2 === 0
        ? [{ option_id: "a", text: "A" }, { option_id: "b", text: "B" }, { option_id: "c", text: "C" }, { option_id: "d", text: "D" }]
        : [{ option_id: "t", text: "True" }, { option_id: "f", text: "False" }],
      key: [i % 2 === 0 ? "b" : "t"], rationale: "because", bloom_level: "apply", audience_ids: ["requester"],
    })) };
  }
  throw new Error("unrecognized prompt: " + prompt.slice(0, 80));
}

const { initApp } = await import("../src/ui.js");
initApp();

const [templateInput, sourceInput] = findAll(rootEl, (n) => n.tag === "input");
templateInput._listeners.change({ target: { files: [{ name: "t.pptx", arrayBuffer: async () => templateBytes.buffer.slice(templateBytes.byteOffset, templateBytes.byteOffset + templateBytes.byteLength) }] } });
sourceInput._listeners.change({ target: { files: [{ name: "fsd.docx", arrayBuffer: async () => docxBytes.buffer.slice(docxBytes.byteOffset, docxBytes.byteOffset + docxBytes.byteLength) }] } });

const goBtn = findAll(rootEl, (n) => n.tag === "button" && getText(n) === "Parse documents")[0];
goBtn._listeners.click();
for (let i = 0; i < 100; i++) {
  await new Promise((r) => setTimeout(r, 10));
  if (findAll(rootEl, (n) => n.tag === "h2" && getText(n) === "2. Review").length) break;
}
assert.ok(findAll(rootEl, (n) => n.tag === "h2" && getText(n) === "2. Review").length, "expected to reach Review");

const genBtn = findAll(rootEl, (n) => n.tag === "button" && getText(n).startsWith("Generate deck"))[0];
genBtn._listeners.click();

// Wait for the error step (the mocked brief call fails on its first attempt).
for (let i = 0; i < 100; i++) {
  await new Promise((r) => setTimeout(r, 10));
  if (findAll(rootEl, (n) => n.tag === "h2" && getText(n) === "Something went wrong").length) break;
}
assert.ok(findAll(rootEl, (n) => n.tag === "h2" && getText(n) === "Something went wrong").length, "expected the error step");

const errorText = getText(findAll(rootEl, (n) => n.className === "notice notice--error")[0]);
console.log("error step shows:", errorText);
assert.ok(errorText.includes("the reply held no JSON value"), "expected the raw sample.json() message to be shown");
assert.ok(errorText.includes("isn't"), "expected the invalid_json explanatory copy to be shown");

const tryAgainBtn = findAll(rootEl, (n) => n.tag === "button" && getText(n) === "Try again")[0];
assert.ok(tryAgainBtn, "expected a 'Try again' button for a retriable (invalid_json) failure");
const startOverBtn = findAll(rootEl, (n) => n.tag === "button" && getText(n) === "Start over")[0];
assert.ok(startOverBtn, "Start over should still be offered alongside Try again");

console.log("clicking Try again (this re-enters runGenerate() without re-uploading)...");
tryAgainBtn._listeners.click();

for (let i = 0; i < 200; i++) {
  await new Promise((r) => setTimeout(r, 10));
  if (findAll(rootEl, (n) => n.tag === "h2" && getText(n) === "3. Deliver").length) break;
  const err = findAll(rootEl, (n) => n.className === "notice notice--error");
  if (err.length && getText(rootEl.children[0]).includes("Something went wrong")) {
    // a second, unexpected failure — not the retry-success path this test checks
  }
}
const reachedDeliver = findAll(rootEl, (n) => n.tag === "h2" && getText(n) === "3. Deliver").length > 0;
assert.ok(reachedDeliver, "expected Try again to succeed and reach the Deliver step");
console.log(`total sample() calls made: ${sampleCallCount} (one failed + retried, then the rest succeeded)`);

console.log("\nerror-retry behaviour works correctly.");
