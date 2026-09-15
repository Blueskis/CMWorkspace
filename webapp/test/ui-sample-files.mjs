/**
 * Verifies the "use sample files" quick-start actually works against the real embedded
 * data (not a small fixture): clicking it should populate state with correctly-decoded
 * File objects and successfully carry the page through parsing to the Review step.
 */
import assert from "node:assert/strict";

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
globalThis.window = { claude: undefined };

const { initApp } = await import("../src/ui.js");
const { SAMPLE_TEMPLATE, SAMPLE_FSD } = await import("../src/sample-data.js");

initApp();

const useSamplesBtn = findAll(rootEl, (n) => n.tag === "button" && getText(n) === "Use the sample files")[0];
assert.ok(useSamplesBtn, "expected a 'Use the sample files' button on the upload step");
useSamplesBtn._listeners.click();

const status = findAll(rootEl, (n) => n.className === "upload-status")[0];
console.log("status after clicking:", getText(status));
assert.ok(getText(status).includes(SAMPLE_TEMPLATE.filename), "status should show the sample template's filename");
assert.ok(getText(status).includes(SAMPLE_FSD.filename), "status should show the sample FSD's filename");

const goBtn = findAll(rootEl, (n) => n.tag === "button" && getText(n) === "Parse documents")[0];
assert.ok(!goBtn.disabled, "Parse documents should be enabled once samples are loaded");

console.log("clicking Parse documents against the real embedded sample files (this decodes ~11MB and runs the real parser + profiler)...");
goBtn._listeners.click();

for (let i = 0; i < 300; i++) {
  await new Promise((r) => setTimeout(r, 20));
  const h2s = findAll(rootEl, (n) => n.tag === "h2");
  if (h2s.some((h) => getText(h) === "2. Review")) break;
  const err = findAll(rootEl, (n) => n.className === "notice notice--error");
  if (err.length) {
    console.log("ERROR STATE:", getText(err[0]));
    process.exit(1);
  }
}
const h2s = findAll(rootEl, (n) => n.tag === "h2");
assert.ok(h2s.some((h) => getText(h) === "2. Review"), "expected to reach the Review step on the real sample files");

const stats = findAll(rootEl, (n) => n.className === "stat");
console.log("review stats:", stats.map(getText));

console.log("\nsample-files quick-start works end to end against the real embedded content.");
