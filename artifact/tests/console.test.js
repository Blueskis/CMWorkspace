#!/usr/bin/env node
"use strict";

// Regression tests for artifact/change-comms-console.html — the "Generate first drafts"
// button hanging on "Checking for Gamma..." (root cause: a call to syncRegistry(), a
// function removed when cm-comms was retired, in the promise chain that decides whether to
// run a live Gamma generation).
//
// No dependencies, no network. Runs the console's real <script> body — extracted from the
// committed HTML file and de-wrapped so its top-level `var`/`function` declarations become
// inspectable properties of a fresh vm context per test — against a hand-rolled DOM stub and
// a fake `window.claude.use("mcp")` connector. The DOM stub implements exactly the subset of
// the platform this file's script uses (checked against the source below), not a general
// browser.
//
// Run: node artifact/tests/console.test.js

var fs = require("fs");
var path = require("path");
var vm = require("vm");

var HTML_PATH = path.join(__dirname, "..", "change-comms-console.html");

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
  this._listeners = Object.create(null);
  this._text = null; // set only for text nodes
}

Element.prototype.getAttribute = function (name) {
  return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
};
Element.prototype.setAttribute = function (name, value) {
  value = String(value);
  this.attrs[name] = value;
  if (name === "id") { this.ownerDocument._registerId(this); }
};
Element.prototype.removeAttribute = function (name) {
  delete this.attrs[name];
};
Object.defineProperty(Element.prototype, "id", {
  get: function () { return this.attrs.id || ""; },
  set: function (v) { this.setAttribute("id", v); }
});
Object.defineProperty(Element.prototype, "className", {
  get: function () { return this.attrs["class"] || ""; },
  set: function (v) { this.attrs["class"] = String(v); }
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
Object.defineProperty(Element.prototype, "innerHTML", {
  get: function () { throw new Error("innerHTML getter not implemented in test DOM stub"); },
  set: function (html) {
    this.children = [];
    var kids = parseHTML(this.ownerDocument, String(html));
    var self = this;
    kids.forEach(function (k) { self.appendChild(k); });
  }
});
Element.prototype.appendChild = function (child) {
  child.parentNode = this;
  this.children.push(child);
  return child;
};
Element.prototype.insertBefore = function (child, ref) {
  child.parentNode = this;
  var i = this.children.indexOf(ref);
  if (i === -1) { this.children.push(child); } else { this.children.splice(i, 0, child); }
  return child;
};
Element.prototype.removeChild = function (child) {
  var i = this.children.indexOf(child);
  if (i !== -1) { this.children.splice(i, 1); }
  return child;
};
Element.prototype.addEventListener = function (type, fn) {
  (this._listeners[type] = this._listeners[type] || []).push(fn);
};
Element.prototype.removeEventListener = function (type, fn) {
  var list = this._listeners[type] || [];
  var i = list.indexOf(fn);
  if (i !== -1) { list.splice(i, 1); }
};
Element.prototype._dispatch = function (type, evt) {
  evt.target = evt.target || this;
  (this._listeners[type] || []).slice().forEach(function (fn) { fn(evt); });
};
Element.prototype._classes = function () {
  return (this.attrs["class"] || "").split(/\s+/).filter(Boolean);
};
Element.prototype.classList = {};
["add", "remove", "contains"].forEach(function () {});
Object.defineProperty(Element.prototype, "classList", {
  get: function () {
    var el = this;
    return {
      add: function (c) {
        var list = el._classes();
        if (list.indexOf(c) === -1) { list.push(c); el.attrs["class"] = list.join(" "); }
      },
      remove: function (c) {
        var list = el._classes().filter(function (x) { return x !== c; });
        el.attrs["class"] = list.join(" ");
      },
      contains: function (c) { return el._classes().indexOf(c) !== -1; }
    };
  }
});
Element.prototype.scrollIntoView = function () {};
Element.prototype.select = function () {};
Element.prototype.focus = function () {};

function selectorMatches(el, sel) {
  var m = /^([a-zA-Z0-9-]*)((?:\.[a-zA-Z0-9_-]+|\[[a-zA-Z0-9_:-]+(?:="[^"]*")?\])*)$/.exec(sel.trim());
  if (!m) { throw new Error("test DOM stub: unsupported selector " + sel); }
  if (m[1] && el.tagName !== m[1].toLowerCase()) { return false; }
  var rest = m[2] || "";
  var frag = /\.[a-zA-Z0-9_-]+|\[[a-zA-Z0-9_:-]+(?:="[^"]*")?\]/g, f;
  while ((f = frag.exec(rest))) {
    var tok = f[0];
    if (tok[0] === ".") {
      if (!el.classList.contains(tok.slice(1))) { return false; }
    } else {
      var am = /^\[([a-zA-Z0-9_:-]+)(?:="([^"]*)")?\]$/.exec(tok);
      var val = el.getAttribute(am[1]);
      if (val === null) { return false; }
      if (am[2] !== undefined && val !== am[2]) { return false; }
    }
  }
  return true;
}
function walk(el, fn) {
  el.children.forEach(function (c) {
    if (c.tagName !== "#text") { fn(c); walk(c, fn); }
  });
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

// Tiny forgiving HTML parser — enough for the markup this file's template strings emit
// (flat-ish, double-quoted attributes, no scripts/comments). Not a general HTML parser.
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
      for (var i = stack.length - 1; i > 0; i--) {
        if (stack[i].tagName === tag) { stack.length = i; break; }
      }
      continue;
    }
    var el = new Element(doc, tag);
    var attrRe = /([a-zA-Z_:][a-zA-Z0-9_:.-]*)(?:\s*=\s*"([^"]*)")?/g, am;
    while ((am = attrRe.exec(m[2] || ""))) { el.setAttribute(am[1], am[2] === undefined ? "" : am[2]); }
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
Document.prototype.execCommand = function () { return true; };

// The static shell: every id the script's $() calls reference. Built directly rather than
// parsed from the file, since the file's real markup carries a lot of layout not relevant to
// behaviour — see the plan note on this tradeoff.
var SKELETON_TAGS = {
  brief: "textarea", req: "pre", org: "input", sender: "input",
  go: "button", "clear-draft": "button", copy: "button", dl: "button", "btn-theme": "button"
};
var SKELETON_IDS = [
  "btn-theme", "brief", "cover-score", "cover", "org", "sender", "chans", "go", "count",
  "restored", "clear-draft", "out", "out-h2", "out-sub", "out-live", "run-banner",
  "runlist", "results", "out-fallback", "outsum", "copy", "dl", "req"
];
function makeDocument() {
  var doc = new Document();
  SKELETON_IDS.forEach(function (id) {
    var el = doc.createElement(SKELETON_TAGS[id] || "div");
    el.setAttribute("id", id);
    doc.body.appendChild(el);
  });
  doc.getElementById("restored").hidden = true;
  doc.getElementById("out-live").style.display = "none";
  doc.getElementById("out-fallback").style.display = "none";
  return doc;
}

// --- Loading the real script -------------------------------------------------------------

function extractAppScript(html) {
  var scripts = [];
  var re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g, m;
  while ((m = re.exec(html))) { scripts.push(m[1]); }
  if (scripts.length !== 1) {
    throw new Error("expected exactly one inline <script> in change-comms-console.html, found " + scripts.length);
  }
  return scripts[0];
}

// The shipped file wraps its logic in `(function () { "use strict"; ... })();` so the page
// exposes nothing globally. For testing, strip that one outer wrapper so its top-level `var`
// and `function` declarations become properties of the vm context instead — this is a
// test-only transform, the shipped file is untouched.
function dewrap(src) {
  var opened = src.replace(/^\s*\(function\s*\(\)\s*\{\s*(["'])use strict\1;?/, "");
  if (opened === src) { throw new Error("could not find the expected `(function () { \"use strict\";` wrapper"); }
  var closed = opened.replace(/\}\)\(\);\s*$/, "");
  if (closed === opened) { throw new Error("could not find the expected trailing `})();` wrapper"); }
  return closed;
}

// setTimeout that ignores its delay and fires on the next macrotask. Tests don't care about
// wall-clock time (some of the code's real delays are minutes), only about the eventual
// outcome, so collapsing every delay to "soon" keeps the suite fast and deterministic without
// a fake-timer library.
function installFastTimers(ctx) {
  ctx.setTimeout = function (fn) { return setImmediate(fn); };
  ctx.clearTimeout = function (id) { clearImmediate(id); };
}

function makeFakeDocx() {
  function Ctor(opts) { this.opts = opts; }
  return {
    Packer: { toBlob: function (doc) { return Promise.resolve({ __fakeBlob: true, doc: doc }); } },
    Document: Ctor, Paragraph: Ctor, TextRun: Ctor,
    HeadingLevel: { HEADING_1: 1, HEADING_2: 2, HEADING_3: 3, HEADING_4: 4, HEADING_5: 5, HEADING_6: 6 }
  };
}

var appScriptSrc = dewrap(extractAppScript(fs.readFileSync(HTML_PATH, "utf8")));
new vm.Script(appScriptSrc, { filename: "change-comms-console.js" }); // fail fast on a syntax error

function loadConsole(opts) {
  opts = opts || {};
  var doc = makeDocument();
  var ctx = vm.createContext({ console: console });
  ctx.document = doc;
  ctx.localStorage = (function () {
    var store = Object.create(null);
    return {
      getItem: function (k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
      setItem: function (k, v) { store[k] = String(v); },
      removeItem: function (k) { delete store[k]; }
    };
  })();
  ctx.matchMedia = function () { return { matches: false }; };
  ctx.navigator = { clipboard: null };
  installFastTimers(ctx);
  ctx.window = ctx;
  ctx.claude = { use: opts.claudeUse || function () { return Promise.resolve(null); } };
  if (opts.withDocx) { ctx.docx = makeFakeDocx(); }
  vm.runInContext(appScriptSrc, ctx); // runs renderChannels()/loadDraft()/syncCount() at load, as on the real page
  ctx.__doc = doc;
  return ctx;
}

function makeMcp(spec) {
  return {
    listTools: spec.listTools,
    callTool: function (server, tool, args) {
      var fn = spec.calls && spec.calls[tool];
      if (!fn) { return Promise.reject(new Error("unexpected tool call: " + tool)); }
      return fn(args);
    }
  };
}
function claudeUseWithMcp(mcp) {
  return function (name) { return name === "mcp" ? Promise.resolve(mcp) : Promise.resolve(null); };
}

var GAMMA_SERVER_OK = { servers: [{ server: "Gamma", tools: [{ name: "generate" }, { name: "get_generation_status" }] }] };

function fakeGenerationDetails(text) {
  return { content: { default: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: text || "Hello colleagues" }] }] } } };
}

function pickChannels(ctx, ids) {
  ids.forEach(function (id) { ctx.picked[id] = true; });
  ctx.syncCount();
}
function setBrief(ctx, text) {
  ctx.document.getElementById("brief").value = text;
  ctx.syncCount();
}

// GAMMA_BY_CHANNEL ships empty — no shipped channel currently routes through Gamma (Email and
// Article go to the docx skill, Briefing deck to the pptx skill, Newsletter hands off to
// Canva). The live-generation machinery stays in the file dormant rather than deleted, so
// these tests exercise it by injecting a route for an existing channel id, the same way test 7
// reaches in and removes renderRunList — not because that channel is actually Gamma-routed today.
function installGammaRoute(ctx, id, cfg) {
  ctx.GAMMA_BY_CHANNEL[id] = cfg;
}

var LONG_BRIEF = "From 1 October payroll moves from monthly to twice-monthly for all staff, " +
  "affecting every employee. HR will run info sessions and the portal opens on 1 Sept. " +
  "Questions go to hr@example.com. This is a mandatory change with no opt-out.";

// --- Drain helper: let a chain of microtasks + our immediate-based timers settle ----------

function drain(rounds) {
  var p = Promise.resolve();
  for (var i = 0; i < (rounds || 40); i++) {
    p = p.then(function () { return new Promise(function (r) { setImmediate(r); }); });
  }
  return p;
}

// --- Test runner --------------------------------------------------------------------------

var results = [];
function test(name, fn) {
  results.push({ name: name, fn: fn });
}
function assert(cond, msg) {
  if (!cond) { throw new Error(msg || "assertion failed"); }
}

test("1: two live channels run end-to-end through Gamma and the button recovers", function () {
  var calls = { generate: 0, get_generation_status: 0 };
  var tries = Object.create(null);
  var mcp = makeMcp({
    listTools: function () { return Promise.resolve(GAMMA_SERVER_OK); },
    calls: {
      generate: function (input) {
        calls.generate++;
        var id = "gen-" + calls.generate;
        return Promise.resolve({ payload: { generationId: id, status: "pending", gammaUrl: "https://gamma.app/generations/" + id } });
      },
      get_generation_status: function (args) {
        calls.get_generation_status++;
        tries[args.generationId] = (tries[args.generationId] || 0) + 1;
        if (tries[args.generationId] < 2) { return Promise.resolve({ payload: { generationId: args.generationId, status: "pending" } }); }
        return Promise.resolve({
          payload: {
            generationId: args.generationId, status: "completed",
            gammaUrl: "https://gamma.app/docs/" + args.generationId,
            generationDetails: fakeGenerationDetails(),
            credits: { deducted: 5, remaining: 95 }
          }
        });
      }
    }
  });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp), withDocx: true });
  installGammaRoute(ctx, "email", { format: "document", numCards: 1, amount: "brief", docx: true });
  installGammaRoute(ctx, "briefing_deck", { format: "presentation", amount: "medium", exportAs: "pptx" });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email", "briefing_deck"]);
  ctx.tryLiveGeneration();
  assert(ctx.document.getElementById("go").textContent === "Checking for Gamma…", "button should show the checking state immediately");
  return drain(60).then(function () {
    assert(calls.generate === 2, "expected one generate call per selected channel, got " + calls.generate);
    var go = ctx.document.getElementById("go");
    assert(go.disabled === false, "button should be re-enabled once the run finishes");
    assert(go.textContent === "Generate first drafts", "button text should be restored, got: " + go.textContent);
    var results = ctx.document.getElementById("results");
    assert(results.children.length === 2, "expected one result block per channel, got " + results.children.length);
    ["pill-email", "pill-briefing_deck"].forEach(function (id) {
      assert(ctx.document.getElementById(id).textContent === "Ready", id + " should read Ready");
    });
  });
});

test("2: a completed deck payload with exportUrl renders a direct .pptx download link", function () {
  var mcp = makeMcp({
    listTools: function () { return Promise.resolve(GAMMA_SERVER_OK); },
    calls: {
      generate: function () { return Promise.resolve({ payload: { generationId: "g1" } }); },
      get_generation_status: function () {
        return Promise.resolve({
          payload: {
            generationId: "g1", status: "completed",
            gammaUrl: "https://gamma.app/docs/g1",
            exportUrl: "https://gamma.app/export/g1.pptx"
          }
        });
      }
    }
  });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp) });
  installGammaRoute(ctx, "briefing_deck", { format: "presentation", amount: "medium", exportAs: "pptx" });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["briefing_deck"]);
  ctx.tryLiveGeneration();
  return drain(30).then(function () {
    var link = ctx.document.querySelector('a[href="https://gamma.app/export/g1.pptx"]');
    assert(link, "expected a download link pointing at exportUrl");
    assert(link.textContent.indexOf("Download the .pptx") !== -1, "link text should say Download the .pptx, got: " + link.textContent);
  });
});

test("3: a completed deck payload with no exportUrl falls back to the Gamma link", function () {
  var mcp = makeMcp({
    listTools: function () { return Promise.resolve(GAMMA_SERVER_OK); },
    calls: {
      generate: function () { return Promise.resolve({ payload: { generationId: "g1" } }); },
      get_generation_status: function () {
        return Promise.resolve({ payload: { generationId: "g1", status: "completed", gammaUrl: "https://gamma.app/docs/g1" } });
      }
    }
  });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp) });
  installGammaRoute(ctx, "briefing_deck", { format: "presentation", amount: "medium", exportAs: "pptx" });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["briefing_deck"]);
  ctx.tryLiveGeneration();
  return drain(30).then(function () {
    var results = ctx.document.getElementById("results");
    var html = results.children.map(function (c) { return c.textContent; }).join(" ");
    assert(html.indexOf("export as .pptx from there") !== -1, "expected the export-by-hand hint, got: " + html);
    assert(html.indexOf("Download the .pptx") === -1, "should not render a download link with no exportUrl");
  });
});

test("4: no Gamma server present falls back to the copy/paste request and restores the button", function () {
  var mcp = makeMcp({ listTools: function () { return Promise.resolve({ servers: [] }); }, calls: {} });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp) });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email"]);
  ctx.tryLiveGeneration();
  return drain(20).then(function () {
    var go = ctx.document.getElementById("go");
    assert(go.disabled === false && go.textContent === "Generate first drafts", "button should be restored, got: " + go.textContent);
    assert(ctx.document.getElementById("out-fallback").style.display === "block", "fallback request should be shown");
  });
});

test("5: Gamma listed but not connected (empty tool set) is treated the same as absent", function () {
  var mcp = makeMcp({
    listTools: function () { return Promise.resolve({ servers: [{ server: "Gamma", tools: [] }] }); },
    calls: {}
  });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp) });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email"]);
  ctx.tryLiveGeneration();
  return drain(20).then(function () {
    var go = ctx.document.getElementById("go");
    assert(go.textContent === "Generate first drafts", "button should be restored, got: " + go.textContent);
    assert(ctx.document.getElementById("out-fallback").style.display === "block", "fallback request should be shown");
  });
});

test("6 (regression): listTools never settles no longer hangs the button forever", function () {
  var mcp = makeMcp({ listTools: function () { return new Promise(function () {}); }, calls: {} });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp) });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email"]);
  ctx.tryLiveGeneration();
  assert(ctx.document.getElementById("go").textContent === "Checking for Gamma…", "should show the checking state right away");
  return drain(20).then(function () {
    var go = ctx.document.getElementById("go");
    assert(go.disabled === false, "button should recover once the timeout fires, not stay stuck checking forever");
    assert(go.textContent === "Generate first drafts", "button text should be restored, got: " + go.textContent);
    assert(ctx.document.getElementById("out-fallback").style.display === "block", "fallback request should be shown after the timeout");
  });
});

test("7 (regression): a throw inside the generation chain restores the button instead of hanging", function () {
  var mcp = makeMcp({ listTools: function () { return Promise.resolve(GAMMA_SERVER_OK); }, calls: {} });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp) });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email"]);
  // Simulate exactly the shape of today's bug: a function the chain calls has gone missing.
  ctx.renderRunList = undefined;
  ctx.tryLiveGeneration();
  return drain(20).then(function () {
    var go = ctx.document.getElementById("go");
    assert(go.disabled === false, "button should recover even when a dependency inside the chain throws");
    assert(go.textContent === "Generate first drafts", "button text should be restored, got: " + go.textContent);
  });
});

test("8: a needs_reauth error on one channel is reported without blocking the others", function () {
  var mcp = makeMcp({
    listTools: function () { return Promise.resolve(GAMMA_SERVER_OK); },
    calls: {
      generate: function () {
        return Promise.reject({ code: "needs_reauth" });
      }
    }
  });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp) });
  installGammaRoute(ctx, "email", { format: "document", numCards: 1, amount: "brief", docx: true });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email"]);
  ctx.tryLiveGeneration();
  return drain(20).then(function () {
    var stage = ctx.document.getElementById("stage-email");
    assert(stage.textContent === "Failed", "expected the row to report Failed, got: " + stage.textContent);
    var results = ctx.document.getElementById("results");
    var html = results.children.map(function (c) { return c.textContent; }).join(" ");
    assert(html.indexOf("reconnect it") !== -1, "expected the reauth wording, got: " + html);
  });
});

test("9: one failing channel does not stop a second channel from completing", function () {
  var mcp = makeMcp({
    listTools: function () { return Promise.resolve(GAMMA_SERVER_OK); },
    calls: {
      generate: function (input) {
        if (input.format === "presentation") { return Promise.reject({ code: "server_unavailable" }); }
        return Promise.resolve({ payload: { generationId: "g-email" } });
      },
      get_generation_status: function () {
        return Promise.resolve({ payload: { generationId: "g-email", status: "completed", gammaUrl: "https://gamma.app/docs/g-email" } });
      }
    }
  });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp) });
  installGammaRoute(ctx, "email", { format: "document", numCards: 1, amount: "brief", docx: true });
  installGammaRoute(ctx, "briefing_deck", { format: "presentation", amount: "medium", exportAs: "pptx" });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email", "briefing_deck"]);
  ctx.tryLiveGeneration();
  return drain(40).then(function () {
    assert(ctx.document.getElementById("stage-briefing_deck").textContent === "Failed", "deck channel should report Failed");
    assert(ctx.document.getElementById("stage-email").textContent === "Draft ready", "email channel should still complete");
    var go = ctx.document.getElementById("go");
    assert(go.disabled === false && go.textContent === "Generate first drafts", "button should still recover, got: " + go.textContent);
  });
});

test("10 (regression): #results survives a run so the .dl-docx delegated handler stays live", function () {
  var mcp = makeMcp({
    listTools: function () { return Promise.resolve(GAMMA_SERVER_OK); },
    calls: {
      generate: function () { return Promise.resolve({ payload: { generationId: "g1" } }); },
      get_generation_status: function () {
        return Promise.resolve({
          payload: {
            generationId: "g1", status: "completed", gammaUrl: "https://gamma.app/docs/g1",
            generationDetails: fakeGenerationDetails("All colleagues, from HR")
          }
        });
      }
    }
  });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp), withDocx: true });
  installGammaRoute(ctx, "email", { format: "document", numCards: 1, amount: "brief", docx: true });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email"]);
  var resultsBefore = ctx.document.getElementById("results");
  ctx.tryLiveGeneration();
  return drain(30).then(function () {
    var resultsAfter = ctx.document.getElementById("results");
    assert(resultsAfter === resultsBefore, "#results must be the same node throughout a run, not replaced by an innerHTML wipe");
    assert(ctx.DOCX_FILES.email, "expected the email channel to produce a .docx file");
    var btn = ctx.document.querySelector(".dl-docx");
    assert(btn, "expected a Download .docx button to be rendered");
    var clicked = false;
    var save = { save: function () { clicked = true; return Promise.resolve(); } };
    ctx.claude.use = function (name) { return Promise.resolve(name === "downloads" ? save : null); };
    resultsAfter._dispatch("click", { target: btn, closest: function (sel) { return btn.closest(sel); } });
    return drain(5).then(function () { assert(clicked, "the delegated .dl-docx click handler should still fire after a run"); });
  });
});

test("11 (regression): no shipped channel reaches Gamma even when the connector is present", function () {
  var generateCalls = 0;
  var mcp = makeMcp({
    listTools: function () { return Promise.resolve(GAMMA_SERVER_OK); },
    calls: { generate: function () { generateCalls++; return Promise.reject(new Error("should not be called")); } }
  });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp) });
  // Deliberately NOT calling installGammaRoute: GAMMA_BY_CHANNEL ships empty, so none of
  // Email, Article, Briefing deck or Newsletter should ever reach mcp.callTool("generate").
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email", "article", "briefing_deck", "newsletter"]);
  ctx.tryLiveGeneration();
  return drain(30).then(function () {
    assert(generateCalls === 0, "expected zero Gamma generate calls, got " + generateCalls);
    var results = ctx.document.getElementById("results");
    assert(results.children.length === 4, "expected a not-built-here result for every picked channel, got " + results.children.length);
    var html = results.children.map(function (c) { return c.textContent; }).join(" ");
    ["docx skill", "pptx skill", "Canva"].forEach(function (producer) {
      assert(html.indexOf(producer) !== -1, "expected the results to name " + producer + " as the producer, got: " + html);
    });
    assert(ctx.document.getElementById("out-fallback").style.display === "block", "the run request should still be offered for these channels");
  });
});

test("12: the run request lists every selected channel that Gamma doesn't build", function () {
  var mcp = makeMcp({ listTools: function () { return Promise.resolve(GAMMA_SERVER_OK); }, calls: {} });
  var ctx = loadConsole({ claudeUse: claudeUseWithMcp(mcp) });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email", "article", "briefing_deck", "newsletter"]);
  ctx.tryLiveGeneration();
  return drain(30).then(function () {
    var req = ctx.document.getElementById("req").textContent;
    assert(req.indexOf("CHANNELS: email, article, briefing_deck, newsletter") !== -1,
      "expected the run request to list all four channels, got: " + req);
  });
});

// --- Run -------------------------------------------------------------------------------

(function run() {
  var i = 0;
  var pass = 0, fail = 0;
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
