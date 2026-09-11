/**
 * A minimal DOM stub, just enough to exercise ui.js's render functions in Node and catch
 * ReferenceErrors/TypeErrors that the other test suites (which never touch ui.js) cannot.
 * Not a substitute for a real browser check — event wiring and CSS are unverified here.
 */
import assert from "node:assert/strict";

class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.attrs = {};
    this.children = [];
    this._text = "";
    this._listeners = {};
    this.className = "";
    this.disabled = false;
  }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(type, fn) { this._listeners[type] = fn; }
  appendChild(c) { this.children.push(c); return c; }
  replaceChildren(...nodes) { this.children = nodes.filter((n) => n != null); }
  querySelector(sel) {
    // only supports #id lookups, which is all ui.js uses
    if (sel.startsWith("#")) return findById(this, sel.slice(1));
    return null;
  }
  set textContent(v) { this._text = v; this.children = []; }
  get textContent() { return this._text; }
  click() { this._listeners.click?.({ target: this, preventDefault() {} }); }
}
function findById(node, id) {
  if (node.attrs?.id === id) return node;
  for (const c of node.children) {
    if (c instanceof FakeNode) {
      const hit = findById(c, id);
      if (hit) return hit;
    }
  }
  return null;
}

class FakeText {
  constructor(text) { this.text = text; }
}

const rootEl = new FakeNode("div");
rootEl.attrs.id = "app";

globalThis.document = {
  createElement: (tag) => new FakeNode(tag),
  createTextNode: (text) => new FakeText(text),
  getElementById: (id) => (id === "app" ? rootEl : null),
};
globalThis.window = { claude: undefined };
globalThis.URL = { createObjectURL: () => "blob:fake", revokeObjectURL: () => {} };
globalThis.Blob = class { constructor(parts, opts) { this.parts = parts; this.opts = opts; } };

const { initApp } = await import("../src/ui.js");

initApp();
assert.equal(rootEl.children.length, 1, "renderUpload should produce one panel");
const panel = rootEl.children[0];
assert.equal(panel.tag, "div");
assert.ok(panel.className.includes("panel"));

// Find the two file inputs and the "Parse documents" button, and drive step 1 -> step 2
// by simulating file selection the way ui.js's onchange handlers expect.
function findAll(node, pred, out = []) {
  if (node instanceof FakeNode) {
    if (pred(node)) out.push(node);
    node.children.forEach((c) => findAll(c, pred, out));
  }
  return out;
}
const inputs = findAll(panel, (n) => n.tag === "input");
assert.equal(inputs.length, 2, "expected a template input and a source-docs input");
const [templateInput, sourceInput] = inputs;
assert.equal(templateInput.attrs.accept, ".pptx,.potx");
assert.equal(sourceInput.attrs.accept, ".docx,.pptx,.pdf");

const fakeTemplateFile = { name: "client-template.pptx", arrayBuffer: async () => new ArrayBuffer(8) };
templateInput._listeners.change({ target: { files: [fakeTemplateFile] } });
sourceInput._listeners.change({ target: { files: [{ name: "fsd.docx" }] } });

const buttons = findAll(rootEl, (n) => n.tag === "button");
const goBtn = buttons.find((b) => b.disabled === false);
assert.ok(goBtn, "expected an enabled 'Parse documents' button after both files are chosen");

console.log("ui.js smoke test: upload step renders, inputs wire up, button enables. OK");
