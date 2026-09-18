#!/usr/bin/env node
"use strict";

// Tests for artifacts/cia-intake.template.html — the in-page scoring + Airtable push pipeline
// and the queue-status UI. See skills/change-impact-assessment/reference/intake-worker.md.
//
// No dependencies, no network. Runs the page's real <script id="app-script"> body, de-wrapped
// so its top-level declarations become inspectable properties of a fresh vm context per
// "load", against a hand-rolled DOM stub. A fake `window.claude.use` hands back controllable
// artifact / mcp / sample namespaces, and a fake `artifact.publish` captures the published
// HTML so a test can "reload" the page against it exactly as the platform would.
//
// Run: node artifacts/tests/cia-intake.test.js

var fs = require("fs");
var path = require("path");
var vm = require("vm");

var HTML_PATH = path.join(__dirname, "..", "cia-intake.template.html");

// --- Minimal DOM ------------------------------------------------------------------------

function Element(doc, tagName) {
  this.ownerDocument = doc;
  this.tagName = String(tagName || "div").toLowerCase();
  this.attrs = Object.create(null);
  this.children = [];
  this.parentNode = null;
  this.style = {};
  this.value = "";
  this.checked = false;
  this.disabled = false;
  this.hidden = false;
  this.open = false;
  this._listeners = Object.create(null);
  this._text = null;
}
Element.prototype.getAttribute = function (name) {
  return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
};
Element.prototype.setAttribute = function (name, value) {
  value = String(value);
  this.attrs[name] = value;
  if (name === "id") { this.ownerDocument._registerId(this); }
};
Element.prototype.removeAttribute = function (name) { delete this.attrs[name]; };
Object.defineProperty(Element.prototype, "id", {
  get: function () { return this.attrs.id || ""; },
  set: function (v) { this.setAttribute("id", v); }
});
Object.defineProperty(Element.prototype, "className", {
  get: function () { return this.attrs["class"] || ""; },
  set: function (v) { this.attrs["class"] = String(v); }
});
Object.defineProperty(Element.prototype, "dataset", {
  get: function () {
    var out = {};
    var self = this;
    Object.keys(this.attrs).forEach(function (k) {
      if (k.indexOf("data-") === 0) {
        var camel = k.slice(5).replace(/-([a-z])/g, function (_, c) { return c.toUpperCase(); });
        out[camel] = self.attrs[k];
      }
    });
    return out;
  }
});
Object.defineProperty(Element.prototype, "textContent", {
  get: function () {
    if (this._text !== null) { return this._text; }
    return this.children.map(function (c) { return c.textContent; }).join("");
  },
  set: function (v) {
    this._text = null;
    this.children = [];
    var t = new Element(this.ownerDocument, "#text");
    t._text = String(v);
    t.parentNode = this;
    this.children.push(t);
  }
});
function serialize(el) {
  if (el.tagName === "#text") { return el._text || ""; }
  var attrs = Object.keys(el.attrs).map(function (k) { return " " + k + "=\"" + el.attrs[k] + "\""; }).join("");
  var inner = el.children.map(serialize).join("");
  return "<" + el.tagName + attrs + ">" + inner + "</" + el.tagName + ">";
}
Object.defineProperty(Element.prototype, "innerHTML", {
  get: function () { return this.children.map(serialize).join(""); },
  set: function (html) {
    this._html = String(html);
    this.children = [];
    var kids = parseHTML(this.ownerDocument, String(html));
    var self = this;
    kids.forEach(function (k) { self.appendChild(k); });
  }
});
Element.prototype.appendChild = function (child) { child.parentNode = this; this.children.push(child); return child; };
Element.prototype.addEventListener = function (type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); };
Element.prototype._dispatch = function (type, evt) {
  evt.target = evt.target || this;
  (this._listeners[type] || []).slice().forEach(function (fn) { fn(evt); });
};
Element.prototype._classes = function () { return (this.attrs["class"] || "").split(/\s+/).filter(Boolean); };
Object.defineProperty(Element.prototype, "classList", {
  get: function () {
    var el = this;
    return {
      add: function (c) { var l = el._classes(); if (l.indexOf(c) === -1) { l.push(c); el.attrs["class"] = l.join(" "); } },
      remove: function (c) { el.attrs["class"] = el._classes().filter(function (x) { return x !== c; }).join(" "); },
      contains: function (c) { return el._classes().indexOf(c) !== -1; }
    };
  }
});
function selectorMatches(el, sel) {
  var m = /^([a-zA-Z0-9-]*)((?:#[a-zA-Z0-9_-]+|\.[a-zA-Z0-9_-]+|\[[a-zA-Z0-9_:-]+(?:="[^"]*")?\])*)$/.exec(sel.trim());
  if (!m) { throw new Error("test DOM stub: unsupported selector " + sel); }
  if (m[1] && el.tagName !== m[1].toLowerCase()) { return false; }
  var rest = m[2] || "";
  var frag = /#[a-zA-Z0-9_-]+|\.[a-zA-Z0-9_-]+|\[[a-zA-Z0-9_:-]+(?:="[^"]*")?\]/g, f;
  while ((f = frag.exec(rest))) {
    var tok = f[0];
    if (tok[0] === "#") { if (el.id !== tok.slice(1)) { return false; } }
    else if (tok[0] === ".") { if (!el.classList.contains(tok.slice(1))) { return false; } }
    else {
      var am = /^\[([a-zA-Z0-9_:-]+)(?:="([^"]*)")?\]$/.exec(tok);
      var val = el.getAttribute(am[1]);
      if (val === null) { return false; }
      if (am[2] !== undefined && val !== am[2]) { return false; }
    }
  }
  return true;
}
function walk(el, fn) {
  el.children.forEach(function (c) { if (c.tagName !== "#text") { fn(c); walk(c, fn); } });
}
Element.prototype.querySelector = function (sel) {
  var found = null;
  walk(this, function (el) { if (!found && selectorMatches(el, sel)) { found = el; } });
  return found;
};
Element.prototype.querySelectorAll = function (sel) {
  var out = [];
  walk(this, function (el) { if (selectorMatches(el, sel)) { out.push(el); } });
  return out;
};
Element.prototype.closest = function (sel) {
  var el = this;
  while (el && el.tagName !== "#text") {
    if (selectorMatches(el, sel)) { return el; }
    el = el.parentNode;
  }
  return null;
};

var VOID_TAGS = { input: 1, br: 1, img: 1, hr: 1, meta: 1 };
function parseHTML(doc, html) {
  var root = new Element(doc, "#root");
  var stack = [root];
  var re = /<\/?([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[a-zA-Z_:][a-zA-Z0-9_:.-]*(?:\s*=\s*"[^"]*")?)*)\s*\/?>|([^<]+)/g;
  var m;
  while ((m = re.exec(html))) {
    if (m[3] !== undefined) {
      var t = new Element(doc, "#text");
      t._text = m[3];
      stack[stack.length - 1].appendChild(t);
      continue;
    }
    var isClose = m[0][1] === "/";
    var tag = m[1].toLowerCase();
    if (isClose) {
      for (var i = stack.length - 1; i > 0; i--) { if (stack[i].tagName === tag) { stack.length = i; break; } }
      continue;
    }
    var el = new Element(doc, tag);
    var attrRe = /([a-zA-Z_:][a-zA-Z0-9_:.-]*)(?:\s*=\s*"([^"]*)")?/g, am;
    while ((am = attrRe.exec(m[2] || ""))) { el.setAttribute(am[1], am[2] === undefined ? "" : am[2]); }
    if (tag === "input" && Object.prototype.hasOwnProperty.call(el.attrs, "value")) { el.value = el.attrs.value; }
    stack[stack.length - 1].appendChild(el);
    var selfClose = m[0].slice(-2) === "/>";
    if (!VOID_TAGS[tag] && !selfClose) { stack.push(el); }
  }
  return root.children;
}

function Document() {
  this._ids = Object.create(null);
  this.body = new Element(this, "body");
  this.documentElement = new Element(this, "html");
  this.documentElement.appendChild(this.body);
}
Document.prototype._registerId = function (el) { this._ids[el.attrs.id] = el; };
Document.prototype.getElementById = function (id) { return this._ids[id] || null; };
Document.prototype.createElement = function (tag) { return new Element(this, tag); };
Document.prototype.querySelector = function (sel) { return this.body.querySelector(sel); };
Document.prototype.querySelectorAll = function (sel) { return this.body.querySelectorAll(sel); };

// --- Loading the real script -------------------------------------------------------------

var rawHtml = fs.readFileSync(HTML_PATH, "utf8");

function extractScript(html, id) {
  var re = new RegExp('<script(?: type="application/json")? id="' + id + '">([\\s\\S]*?)<\\/script>');
  var m = re.exec(html);
  if (!m) { throw new Error("no <script id=\"" + id + "\"> in the document"); }
  return m[1];
}
function extractState(html) { return JSON.parse(extractScript(html, "state-data")); }

var appScriptSrc = extractScript(rawHtml, "app-script");
function dewrap(src) {
  var opened = src.replace(/^\s*\(function\s*\(\)\s*\{\s*(["'])use strict\1;?/, "");
  if (opened === src) { throw new Error("could not find the `(function(){ \"use strict\";` wrapper"); }
  var closed = opened.replace(/\}\)\(\);\s*$/, "");
  if (closed === opened) { throw new Error("could not find the trailing `})();` wrapper"); }
  return closed;
}
var dewrapped = dewrap(appScriptSrc);
new vm.Script(dewrapped, { filename: "cia-intake.js" }); // fail fast on a syntax error

function memStorage() {
  var store = Object.create(null);
  return {
    getItem: function (k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
    setItem: function (k, v) { store[k] = String(v); },
    removeItem: function (k) { delete store[k]; },
    _dump: function () { return Object.assign({}, store); }
  };
}

// One "load" of the page. `opts.state` is the state object the document carries (as the
// platform would after a publish); `opts.caps` maps capability name -> namespace (or null);
// `opts.session` is a sessionStorage carried across loads (as the same tab would keep it).
function load(opts) {
  opts = opts || {};
  var doc = new Document();
  var root = doc.createElement("div"); root.setAttribute("id", "root"); doc.body.appendChild(root);
  var style = doc.createElement("style"); style.setAttribute("id", "app-style"); style.textContent = "/*css*/"; doc.body.appendChild(style);
  var sd = doc.createElement("script"); sd.setAttribute("id", "state-data");
  sd.textContent = opts.state ? JSON.stringify(opts.state) : ""; doc.body.appendChild(sd);
  var sc = doc.createElement("script"); sc.setAttribute("id", "app-script"); sc.textContent = appScriptSrc; doc.body.appendChild(sc);

  var ctx = vm.createContext({ console: console });
  ctx.document = doc;
  ctx.localStorage = opts.local || memStorage();
  ctx.sessionStorage = opts.session || memStorage();
  ctx.matchMedia = function () { return { matches: false }; };
  ctx.AbortController = AbortController;
  ctx.setTimeout = function (fn) { return setImmediate(fn); };
  ctx.clearTimeout = function (id) { clearImmediate(id); };
  ctx.Date = Date;
  ctx.window = ctx;
  var caps = opts.caps || {};
  ctx.claude = { use: function (name) { return Promise.resolve(Object.prototype.hasOwnProperty.call(caps, name) ? caps[name] : null); } };
  vm.runInContext(dewrapped, ctx);
  ctx.__doc = doc;
  ctx.__root = root;
  return ctx;
}

function drain(rounds) {
  var p = Promise.resolve();
  for (var i = 0; i < (rounds || 12); i++) {
    p = p.then(function () { return new Promise(function (r) { setImmediate(r); }); });
  }
  return p;
}

function click(ctx, selector) {
  var el = ctx.__root.querySelector(selector);
  if (!el) { throw new Error("no element matches " + selector + "\n" + ctx.__root.innerHTML.slice(0, 400)); }
  ctx.__root._dispatch("click", { target: el });
  return el;
}

function makeArtifact(behaviour) {
  var a = { published: [] };
  a.publish = function (html) {
    a.published.push(html);
    var b = typeof behaviour === "function" ? behaviour(a.published.length) : null;
    if (b && b.reject) { return Promise.reject(b.reject); }
    return Promise.resolve();
  };
  a.lastState = function () { return extractState(a.published[a.published.length - 1]); };
  return a;
}
function makeMcp(impl) {
  var m = { calls: [], invalidated: [] };
  m.callTool = function (server, tool, input, options) {
    m.calls.push({ server: server, tool: tool, input: input, options: options });
    return impl(tool, input, options);
  };
  m.invalidate = function (server, tool) { m.invalidated.push([server, tool]); return Promise.resolve(); };
  m.watchTool = function () { return function () {}; };
  return m;
}
function makeSample(impl) {
  var fn = function () { return Promise.reject({ code: "invalid_request", message: "sample(text) is not used by this page" }); };
  fn.calls = [];
  fn.json = function (input, opts) { fn.calls.push({ input: input, opts: opts }); return impl(input, opts); };
  return fn;
}
function airtableMax(id) {
  return function (tool, input) {
    if (tool === "list_records_for_table") {
      return Promise.resolve({ payload: { records: id ? [{ id: "recX", cellValuesByFieldId: { fldwB73o4DHTUo65U: id } }] : [], metadata: { totalRecordCount: id ? 1 : 0 } } });
    }
    if (tool === "update_records_for_table") {
      return Promise.resolve({ payload: { records: input.records.map(function (_, i) { return { id: "recA" + (i + 1) }; }) } });
    }
    return Promise.reject({ code: "not_in_manifest", message: tool });
  };
}

var ROW = function (over) {
  return Object.assign({
    l1: "Procure to Pay", l2: "PR", l3: "Approval", l4: "Approve PR",
    stakeholder_group: "Procurement Approvers", as_is: "Email approvals", to_be: "Fiori approvals",
    people_impact: "New tool", score_people: 2, process_impact: "Same flow", score_process: 1,
    tech_impact: "New UI", score_technology: 3, resistance_risk: "Medium",
    training_required: "Yes", training_type: "e-Learning", training_duration_hrs: 1,
    comms_required: "Yes", key_message: "Approve from your phone.", confidence: "Medium", notes: ""
  }, over || {});
};
var GOOD_SAMPLE = function () { return Promise.resolve([ROW(), ROW({ stakeholder_group: "Buyers", l4: "Raise PR" })]); };

function formState() {
  return {
    history: [],
    current: {
      programme: "S/4 Wave 1", preparedBy: "Colonel", date: "2026-09-18", mode: "process", channel: "form",
      changes: [
        { id: "chg-1", title: "PR approval", l1: "Procure to Pay", l2: "PR", l3: "Approval", l4: "Approve PR", changeType: "Brownfield",
          asIs: "Email approvals", toBe: "Fiori approvals", steer: "", sourceNote: "CM brief 21 Aug",
          stakeholders: [{ id: "sg-1", name: "Procurement Approvers", rolesHeadcount: "12", notes: "" }] },
        { id: "chg-2", title: "Raise PR", l1: "Procure to Pay", l2: "PR", l3: "Create", l4: "Raise PR", changeType: "Brownfield",
          asIs: "Paper form", toBe: "Fiori app", steer: "", sourceNote: "",
          stakeholders: [{ id: "sg-2", name: "Buyers", rolesHeadcount: "", notes: "" }] }
      ],
      freetext: "", excelFile: null, baselineClient: "", baselineScope: "", baselineGoLive: "", baselinePrompt: "", baselineFiles: []
    }
  };
}
function batchState(batchOver, topOver) {
  var batch = Object.assign({
    id: "batch-t1", channel: "form", status: "submitted", submittedAt: new Date().toISOString(),
    processedAt: null, processedNote: "", results: [], programme: "S/4 Wave 1", preparedBy: "", date: "2026-09-18",
    changes: formState().current.changes
  }, batchOver || {});
  var s = formState();
  s.current.changes = [];
  s.history = [batch];
  return Object.assign(s, topOver || {});
}
function pipelineKey(session) { var raw = session.getItem("cia-intake-pipeline"); return raw ? JSON.parse(raw) : null; }
function setKey(session, key) { session.setItem("cia-intake-pipeline", JSON.stringify(key)); }
function tail(ctx, id) { return ctx.__root.querySelector('[data-batch-id="' + id + '"]').innerHTML; }

// --- Test runner --------------------------------------------------------------------------

var results = [];
function test(name, fn) { results.push({ name: name, fn: fn }); }
function assert(cond, msg) { if (!cond) { throw new Error(msg || "assertion failed"); } }

// --- Tests ---------------------------------------------------------------------------------

test("1: form submit publishes the batch as submitted and writes the pipeline key first", function () {
  var art = makeArtifact();
  var session = memStorage();
  var ctx = load({ state: formState(), session: session, caps: { artifact: art } });
  return drain().then(function () {
    click(ctx, "#submit-btn");
    var key = pipelineKey(session);
    assert(key && key.batchId && key.token && key.startedAt, "pipeline key written synchronously before publish");
    return drain();
  }).then(function () {
    assert(art.published.length === 1, "one publish");
    var s = art.lastState();
    assert(s.history.length === 1 && s.history[0].status === "submitted", "batch is submitted");
    assert(s.history[0].id === pipelineKey(session).batchId, "key names the batch");
    assert(s.current.changes.length === 0, "form cleared");
  });
});

test("2: on reload a submitted batch with a key is claimed before any paid call", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() });
  var mcp = makeMcp(airtableMax("CI-050"));
  var sample = makeSample(GOOD_SAMPLE);
  load({ state: batchState(), session: session, caps: { artifact: art, mcp: mcp, sample: sample } });
  return drain().then(function () {
    assert(sample.calls.length === 0, "sample not called before the claim");
    assert(mcp.calls.length === 0, "mcp not called before the claim");
    assert(art.published.length === 1, "claim publish happened");
    var b = art.lastState().history[0];
    assert(b.status === "claimed", "status claimed, got " + b.status);
    assert(b.claimedBy === "page-abc" && b.leaseMs === 600000 && b.attempts === 1, "claim fields");
    assert(b.claimedAt, "claimedAt set");
  });
});

test("3: on a claimed batch, scores once, allocates from the Airtable max, publishes rows + nextImpactSeq", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() });
  var mcp = makeMcp(airtableMax("CI-050"));
  var sample = makeSample(GOOD_SAMPLE);
  var state = batchState({ status: "claimed", claimedBy: "page-abc", claimedAt: new Date().toISOString(), leaseMs: 600000, attempts: 1 });
  var ctx = load({ state: state, session: session, caps: { artifact: art, mcp: mcp, sample: sample } });
  return drain(30).then(function () {
    assert(sample.calls.length === 1, "sample.json called once");
    var p = sample.calls[0].input;
    assert(typeof p === "string" && p.indexOf(ctx.RUBRIC_BLOCK) === 0, "prompt starts with RUBRIC_BLOCK");
    assert(p.indexOf("<<<BATCH") !== -1 && p.indexOf("BATCH>>>") !== -1, "data block delimiters present");
    assert(p.indexOf("Email approvals") !== -1 && p.indexOf("Paper form") !== -1, "both changes in the prompt");
    assert(sample.calls[0].opts && sample.calls[0].opts.modelTier === "default", "default tier");
    var key = pipelineKey(session);
    assert(key && key.rows && key.rows.length === 2, "rows stashed in the key");
    var list = mcp.calls.filter(function (c) { return c.tool === "list_records_for_table"; });
    assert(list.length === 1 && list[0].options && list[0].options.cache === false, "one uncached max read");
    assert(art.published.length === 1, "one publish (allocation)");
    var s = art.lastState();
    assert(s.history[0].rows[0].impactId === "CI-051" && s.history[0].rows[1].impactId === "CI-052", "ids allocated from max+1");
    assert(s.history[0].rows[0].intakeKey === "batch-t1:0", "intake key");
    assert(s.nextImpactSeq === 53, "nextImpactSeq advanced, got " + s.nextImpactSeq);
    assert(s.history[0].status === "claimed", "still claimed");
  });
});

test("4: a document nextImpactSeq ahead of Airtable wins the allocation", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() });
  var mcp = makeMcp(airtableMax("CI-050"));
  var state = batchState({ status: "claimed", claimedBy: "page-abc", claimedAt: new Date().toISOString(), leaseMs: 600000, attempts: 1 }, { nextImpactSeq: 60 });
  load({ state: state, session: session, caps: { artifact: art, mcp: mcp, sample: makeSample(GOOD_SAMPLE) } });
  return drain(30).then(function () {
    var s = art.lastState();
    assert(s.history[0].rows[0].impactId === "CI-060" && s.history[0].rows[1].impactId === "CI-061", "ids from seq");
    assert(s.nextImpactSeq === 62, "seq advanced to 62");
  });
});

test("5: with ids on the batch, upserts on Intake Key, then publishes processed with results", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now(), rows: [ROW(), ROW()] });
  var mcp = makeMcp(airtableMax("CI-050"));
  var rows = [Object.assign(ROW(), { impactId: "CI-051", intakeKey: "batch-t1:0" }), Object.assign(ROW({ stakeholder_group: "Buyers" }), { impactId: "CI-052", intakeKey: "batch-t1:1" })];
  var state = batchState({ status: "claimed", claimedBy: "page-abc", claimedAt: new Date().toISOString(), leaseMs: 600000, attempts: 1, rows: rows }, { nextImpactSeq: 53 });
  var ctx = load({ state: state, session: session, caps: { artifact: art, mcp: mcp, sample: makeSample(GOOD_SAMPLE) } });
  return drain(30).then(function () {
    var up = mcp.calls.filter(function (c) { return c.tool === "update_records_for_table"; });
    assert(up.length === 1, "one upsert call, got " + up.length);
    var input = up[0].input;
    assert(input.baseId === "appFD6GsiE3Jh5rGQ" && input.tableId === "tblfZObW243ZAGE7W", "base/table");
    assert(input.performUpsert && input.performUpsert.fieldIdsToMergeOn.length === 1 && input.performUpsert.fieldIdsToMergeOn[0] === ctx.FIELD_INTAKE_KEY, "merge on Intake Key");
    assert(input.typecast === false, "typecast false");
    var f = input.records[0].fields;
    assert(f[ctx.FIELD_INTAKE_KEY] === "batch-t1:0", "intake key written");
    assert(f["fldwB73o4DHTUo65U"] === "CI-051", "impact id written");
    assert(f["fldiBhzQju35HLx81"] === 2 && f["fldk5fcGohZljfP48"] === 1 && f["fldKzDp6rJsPyvOKy"] === 3, "numeric scores");
    assert(!("fld8RYBqP2R55hPwH" in f) && !("fld3N4ZH6jKmG418C" in f), "formula fields never written");
    assert(f["fld4Nt3ocBYTRKy1t"] === "Draft" && f["fldeh5KINbjTlZXPh"] === "Project Evidence", "fixed Draft / Project Evidence");
    assert(f["fld3kUX1iQIhSZ9IC"] === "e-Learning", "select as plain string");
    assert(/intake batch batch-t1/.test(f["fldqFHsTgMW282smb"]), "notes carry the provenance line");
    assert(art.published.length === 1, "processed publish");
    var b = art.lastState().history[0];
    assert(b.status === "processed" && b.processedAt, "processed");
    assert(b.results.length === 2 && b.results[0].impactId === "CI-051" && b.results[0].rating === "Medium" && b.results[0].recordId === "recA1", "results derived: " + JSON.stringify(b.results[0]));
    assert(mcp.invalidated.length === 1 && mcp.invalidated[0][1] === "list_records_for_table", "live register invalidated");
    assert(pipelineKey(session) === null, "key cleared");
  });
});

test("6: a key for a batch someone else already processed is dropped without calls", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now(), rows: [ROW()] });
  var mcp = makeMcp(airtableMax("CI-050"));
  var sample = makeSample(GOOD_SAMPLE);
  load({ state: batchState({ status: "processed", processedAt: new Date().toISOString() }), session: session, caps: { artifact: art, mcp: mcp, sample: sample } });
  return drain().then(function () {
    assert(sample.calls.length === 0 && mcp.calls.length === 0 && art.published.length === 0, "nothing ran");
    assert(pipelineKey(session) === null, "key cleared");
  });
});

test("7: sample unavailable on my claimed batch releases it to submitted; no Score button", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() });
  var mcp = makeMcp(airtableMax("CI-050"));
  var state = batchState({ status: "claimed", claimedBy: "page-abc", claimedAt: new Date().toISOString(), leaseMs: 600000, attempts: 1 });
  var ctx = load({ state: state, session: session, caps: { artifact: art, mcp: mcp, sample: null } });
  return drain().then(function () {
    assert(art.published.length === 1, "release publish");
    var b = art.lastState().history[0];
    assert(b.status === "submitted" && !b.claimedBy, "released");
    assert(pipelineKey(session) === null, "key cleared");
    assert(mcp.calls.length === 0, "no mcp calls");
    // A fresh load of the released state with no sample shows the manual copy and no button.
    var ctx2 = load({ state: art.lastState(), caps: { artifact: art, mcp: mcp, sample: null } });
    return drain().then(function () {
      var t = tail(ctx2, "batch-t1");
      assert(/awaiting Claude/i.test(t), "awaiting-Claude copy");
      assert(!/data-action="process-batch"/.test(t), "no Score button without sample");
    });
  });
});

test("8: sample rejecting not_granted releases to submitted and clears the key", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() });
  var sample = makeSample(function () { return Promise.reject({ code: "not_granted", message: "no" }); });
  var state = batchState({ status: "claimed", claimedBy: "page-abc", claimedAt: new Date().toISOString(), leaseMs: 600000, attempts: 1 });
  load({ state: state, session: session, caps: { artifact: art, mcp: makeMcp(airtableMax("CI-050")), sample: sample } });
  return drain(20).then(function () {
    assert(art.published.length === 1 && art.lastState().history[0].status === "submitted", "released");
    assert(pipelineKey(session) === null, "key cleared");
  });
});

test("9: sample rejecting invalid_json marks the batch failed with a reason and a Retry button", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() });
  var sample = makeSample(function () { return Promise.reject({ code: "invalid_json", message: "no JSON value", text: "Sorry, here is prose" }); });
  var state = batchState({ status: "claimed", claimedBy: "page-abc", claimedAt: new Date().toISOString(), leaseMs: 600000, attempts: 1 });
  load({ state: state, session: session, caps: { artifact: art, mcp: makeMcp(airtableMax("CI-050")), sample: sample } });
  return drain(20).then(function () {
    assert(art.published.length === 1, "failed publish");
    var b = art.lastState().history[0];
    assert(b.status === "failed" && /JSON/.test(b.failReason), "failed with reason: " + b.failReason);
    assert(pipelineKey(session) === null, "key cleared");
    var ctx2 = load({ state: art.lastState(), caps: { artifact: art, mcp: makeMcp(airtableMax("CI-050")), sample: makeSample(GOOD_SAMPLE) } });
    return drain().then(function () {
      var t = tail(ctx2, "batch-t1");
      assert(/Failed/.test(ctx2.__root.querySelector('[data-batch-id="batch-t1"]').innerHTML), "Failed pill");
      assert(/data-action="retry-batch"/.test(t), "Retry button");
      assert(t.indexOf(b.failReason) !== -1 || t.indexOf("JSON") !== -1, "reason shown");
    });
  });
});

test("10: validator coerces scores, drops unknown options and keys, caps at 50 rows", function () {
  var ctx = load({ state: batchState(), caps: {} });
  var raw = [ROW({ score_people: 7, training_type: "Bootcamp", confidence: "Sure", record_id: "recEvil", score_process: "2", score_technology: -1 })];
  var out = ctx.validateScoredRows(raw);
  var r = out.rows[0];
  assert(r.score_people === 3 && r.score_process === 2 && r.score_technology === 0, "scores clamped/coerced: " + JSON.stringify([r.score_people, r.score_process, r.score_technology]));
  assert(!("training_type" in r), "unknown option omitted");
  assert(r.confidence === "Low", "unknown confidence -> Low");
  assert(!("record_id" in r), "unknown key dropped");
  var many = []; for (var i = 0; i < 51; i++) { many.push(ROW()); }
  var out2 = ctx.validateScoredRows(many);
  assert(out2.rows.length === 50 && /50/.test(out2.note), "capped at 50 with a note");
  assert(ctx.validateScoredRows("nonsense").rows.length === 0, "non-array -> no rows");
});

test("11: allocation publish conflict keeps the scored rows; the reload re-allocates without re-sampling", function () {
  var art = makeArtifact(function (n) { return n === 1 ? { reject: { code: "conflict", message: "conflict" } } : null; });
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() });
  var sample = makeSample(GOOD_SAMPLE);
  var state = batchState({ status: "claimed", claimedBy: "page-abc", claimedAt: new Date().toISOString(), leaseMs: 600000, attempts: 1 });
  load({ state: state, session: session, caps: { artifact: art, mcp: makeMcp(airtableMax("CI-050")), sample: sample } });
  return drain(30).then(function () {
    assert(art.published.length === 1, "first allocation publish attempted");
    var key = pipelineKey(session);
    assert(key && key.rows && key.rows.length === 2, "rows kept in the key after conflict");
    // The winner: someone else pushed the counter to 70. Our batch is still claimed by us.
    var winner = batchState({ status: "claimed", claimedBy: "page-abc", claimedAt: new Date().toISOString(), leaseMs: 600000, attempts: 1 }, { nextImpactSeq: 70 });
    var sample2 = makeSample(GOOD_SAMPLE);
    load({ state: winner, session: session, caps: { artifact: art, mcp: makeMcp(airtableMax("CI-050")), sample: sample2 } });
    return drain(30);
  }).then(function () {
    assert(sample.calls.length === 1, "original sample still once");
    assert(art.published.length === 2, "allocation retried");
    var s = art.lastState();
    assert(s.history[0].rows[0].impactId === "CI-070" && s.nextImpactSeq === 72, "re-allocated from the winner's seq");
  });
});

test("12: processed publish conflict does not repeat the upsert on reload", function () {
  var art = makeArtifact(function (n) { return n === 1 ? { reject: { code: "conflict", message: "conflict" } } : null; });
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() });
  var rows = [Object.assign(ROW(), { impactId: "CI-051", intakeKey: "batch-t1:0" })];
  var state = batchState({ status: "claimed", claimedBy: "page-abc", claimedAt: new Date().toISOString(), leaseMs: 600000, attempts: 1, rows: rows }, { nextImpactSeq: 52 });
  var mcp = makeMcp(airtableMax("CI-051"));
  load({ state: state, session: session, caps: { artifact: art, mcp: mcp, sample: makeSample(GOOD_SAMPLE) } });
  return drain(30).then(function () {
    var key = pipelineKey(session);
    assert(key && key.pushed && key.pushed.recordIds.length === 1, "pushed recorded in key: " + JSON.stringify(key));
    var mcp2 = makeMcp(airtableMax("CI-051"));
    load({ state: state, session: session, caps: { artifact: art, mcp: mcp2, sample: makeSample(GOOD_SAMPLE) } });
    return drain(30).then(function () {
      assert(mcp2.calls.filter(function (c) { return c.tool === "update_records_for_table"; }).length === 0, "no second upsert");
      assert(art.published.length === 2 && art.lastState().history[0].status === "processed", "processed publish retried");
      assert(pipelineKey(session) === null, "key cleared");
    });
  });
});

test("13: free-text batches carry the sliced brief and the extraction section in the prompt", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() });
  var sample = makeSample(GOOD_SAMPLE);
  var longText = new Array(30002).join("x");
  var state = batchState({ channel: "freetext", changes: undefined, text: longText, status: "claimed", claimedBy: "page-abc", claimedAt: new Date().toISOString(), leaseMs: 600000, attempts: 1 });
  var ctx = load({ state: state, session: session, caps: { artifact: art, mcp: makeMcp(airtableMax("CI-050")), sample: sample } });
  return drain(30).then(function () {
    var p = sample.calls[0].input;
    assert(p.indexOf("extraction-guide.md") !== -1, "extraction guide included");
    assert(p.indexOf("xxxxxxxxxx") !== -1 && p.indexOf("[truncated at 30,000 characters]") !== -1, "sliced with note");
    assert(p.length < ctx.RUBRIC_BLOCK.length + 31000, "not the whole 30,001 chars plus more");
  });
});

test("14: a claimed batch past its lease renders Stalled; Retry reuses ids and skips sample", function () {
  var art = makeArtifact();
  var session = memStorage();
  var rows = [Object.assign(ROW(), { impactId: "CI-051", intakeKey: "batch-t1:0" })];
  var state = batchState({ status: "claimed", claimedBy: "page-other", claimedAt: new Date(Date.now() - 11 * 60000).toISOString(), leaseMs: 600000, attempts: 1, rows: rows });
  var mcp = makeMcp(airtableMax("CI-051"));
  var sample = makeSample(GOOD_SAMPLE);
  var ctx = load({ state: state, session: session, caps: { artifact: art, mcp: mcp, sample: sample } });
  return drain().then(function () {
    var card = ctx.__root.querySelector('[data-batch-id="batch-t1"]').innerHTML;
    assert(/Stalled/.test(card), "Stalled pill");
    click(ctx, '[data-action="retry-batch"]');
    return drain(20);
  }).then(function () {
    assert(art.published.length === 1, "re-claim publish");
    var b = art.lastState().history[0];
    assert(b.status === "claimed" && b.attempts === 2 && b.claimedBy !== "page-other", "re-claimed with attempts 2");
    assert(b.rows[0].impactId === "CI-051", "ids preserved");
    var key = pipelineKey(session);
    assert(key && key.batchId === "batch-t1" && key.token === b.claimedBy, "key written for the re-claim");
    // Continue on the reload: push stage, no sample.
    load({ state: art.lastState(), session: session, caps: { artifact: art, mcp: mcp, sample: sample } });
    return drain(30);
  }).then(function () {
    assert(sample.calls.length === 0, "sample never called");
    assert(mcp.calls.filter(function (c) { return c.tool === "update_records_for_table"; }).length === 1, "upsert ran");
    assert(art.lastState().history[0].status === "processed", "processed");
  });
});

test("15: worker.paused stops the pipeline and says so", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() });
  var sample = makeSample(GOOD_SAMPLE);
  var ctx = load({ state: batchState({}, { worker: { paused: true } }), session: session, caps: { artifact: art, mcp: makeMcp(airtableMax("CI-050")), sample: sample } });
  return drain().then(function () {
    assert(art.published.length === 0 && sample.calls.length === 0, "nothing ran");
    assert(/paused/i.test(tail(ctx, "batch-t1")), "paused copy");
    assert(!/data-action="process-batch"/.test(tail(ctx, "batch-t1")), "no button while paused");
  });
});

test("16: a pipeline key older than 15 minutes is discarded on load", function () {
  var art = makeArtifact();
  var session = memStorage();
  setKey(session, { batchId: "batch-t1", token: "page-abc", startedAt: Date.now() - 16 * 60000 });
  var sample = makeSample(GOOD_SAMPLE);
  load({ state: batchState(), session: session, caps: { artifact: art, mcp: makeMcp(airtableMax("CI-050")), sample: sample } });
  return drain().then(function () {
    assert(pipelineKey(session) === null, "key deleted");
    assert(art.published.length === 0 && sample.calls.length === 0, "nothing ran");
  });
});

test("17: Excel and baseline batches name Claude-in-chat and offer no Score button", function () {
  var s = batchState({ id: "batch-x", channel: "excel", changes: undefined, file: { name: "cia.xlsx", size: 1000 } });
  s.history.push({ id: "batch-b", mode: "baseline", status: "submitted", submittedAt: new Date().toISOString(), processedAt: null, processedNote: "", results: [], stats: null, workbookName: "", csv: "", client: "Acme", scope: "S/4", goLive: "", prompt: "Big change", files: [] });
  var ctx = load({ state: s, caps: { artifact: makeArtifact(), mcp: makeMcp(airtableMax("CI-050")), sample: makeSample(GOOD_SAMPLE) } });
  return drain().then(function () {
    ["batch-x", "batch-b"].forEach(function (id) {
      var t = tail(ctx, id);
      assert(/Claude/.test(t) && /chat/i.test(t), id + " names Claude in chat: " + t.slice(0, 200));
      assert(!/data-action="process-batch"/.test(t), id + " has no Score button");
    });
    // And a form batch in the same view does get the button.
    var f = batchState();
    var ctx2 = load({ state: f, caps: { artifact: makeArtifact(), mcp: makeMcp(airtableMax("CI-050")), sample: makeSample(GOOD_SAMPLE) } });
    return drain().then(function () {
      assert(/data-action="process-batch"/.test(tail(ctx2, "batch-t1")), "form batch offers Score & push");
    });
  });
});

test("18: mode-2 baseline submit writes no pipeline key", function () {
  var art = makeArtifact();
  var session = memStorage();
  var s = formState();
  s.current.mode = "baseline"; s.current.baselineClient = "Acme"; s.current.baselineScope = "S/4"; s.current.baselinePrompt = "Describe";
  var ctx = load({ state: s, session: session, caps: { artifact: art } });
  return drain().then(function () {
    click(ctx, "#submit-btn");
    return drain();
  }).then(function () {
    assert(art.published.length === 1 && art.lastState().history[0].mode === "baseline", "baseline batch published");
    assert(pipelineKey(session) === null, "no pipeline key");
  });
});

test("19: regression — a lost submit publish conflict restores the form from the pending stash", function () {
  var art = makeArtifact(function () { return { reject: { code: "conflict", message: "conflict" } }; });
  var session = memStorage();
  var ctx = load({ state: formState(), session: session, caps: { artifact: art } });
  return drain().then(function () {
    click(ctx, "#submit-btn");
    return drain();
  }).then(function () {
    assert(session.getItem("cia-intake-pending"), "pending stash left in place on conflict");
    assert(pipelineKey(session) === null, "pipeline key removed on a lost submit");
    var ctx2 = load({ state: batchState({ id: "batch-someone-else" }), session: session, caps: { artifact: art } });
    assert(ctx2.state.current.changes.length === 2, "form restored from the stash");
  });
});

test("20: RUBRIC_BLOCK in the page matches build_intake_prompt.py output and is under 60,000 chars", function () {
  var ctx = load({ state: formState(), caps: {} });
  assert(typeof ctx.RUBRIC_BLOCK === "string" && ctx.RUBRIC_BLOCK.length > 10000 && ctx.RUBRIC_BLOCK.length < 60000, "size " + ctx.RUBRIC_BLOCK.length);
  assert(ctx.RUBRIC_BLOCK.indexOf("--- OUTPUT ---") !== -1 && ctx.RUBRIC_BLOCK.indexOf("rating-methodology.md") !== -1, "built from the script");
  var cp = require("child_process");
  var built = cp.execFileSync("python3", [path.join(__dirname, "..", "..", "skills", "change-impact-assessment", "scripts", "build_intake_prompt.py")], { encoding: "utf8" });
  assert(built === ctx.RUBRIC_BLOCK, "page rubric is stale — re-run build_intake_prompt.py --js and paste");
});

// --- Run -------------------------------------------------------------------------------

(function run() {
  var i = 0, pass = 0, fail = 0;
  function next() {
    if (i >= results.length) {
      console.log("\n" + pass + "/" + results.length + " passed" + (fail ? ", " + fail + " failed" : ""));
      process.exit(fail ? 1 : 0);
      return;
    }
    var t = results[i++];
    Promise.resolve().then(t.fn).then(
      function () { console.log("ok   - " + t.name); pass++; next(); },
      function (err) { console.log("FAIL - " + t.name + "\n       " + (err && err.stack || err)); fail++; next(); }
    );
  }
  next();
})();
