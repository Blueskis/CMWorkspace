#!/usr/bin/env node
"use strict";

// Tests for artifact/change-comms-console.html.
//
// The console no longer calls Gamma (or any connector) live — it only builds a copy/paste run
// request for Claude to execute the real pipeline (docx skill, pptx skill, Canva). That's a
// deliberate simplification: a page that declares an `mcp` capability cannot be shared
// publicly, and no channel was actually being built live by it any more anyway (see the git
// history on this file for the earlier per-channel routing fix). These tests cover what's left:
// channel selection, the brief-coverage checker, draft persistence, and the run request itself
// — plus a regression test that Gamma/mcp machinery doesn't come back by accident.
//
// No dependencies, no network. Runs the console's real <script> body — extracted from the
// committed HTML file and de-wrapped so its top-level `var`/`function` declarations become
// inspectable properties of a fresh vm context per test — against a hand-rolled DOM stub.
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
Element.prototype.removeChild = function (child) {
  var i = this.children.indexOf(child);
  if (i !== -1) { this.children.splice(i, 1); }
  return child;
};
Element.prototype.addEventListener = function (type, fn) {
  (this._listeners[type] = this._listeners[type] || []).push(fn);
};
Element.prototype._classes = function () {
  return (this.attrs["class"] || "").split(/\s+/).filter(Boolean);
};
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
Document.prototype.execCommand = function () { return true; };

// The static shell: every id the script's $() calls reference. Built directly rather than
// parsed from the file, since the file's real markup carries a lot of layout not relevant to
// behaviour.
var SKELETON_TAGS = {
  brief: "textarea", req: "pre", org: "input", sender: "input",
  go: "button", "clear-draft": "button", copy: "button", dl: "button", "btn-theme": "button"
};
var SKELETON_IDS = [
  "btn-theme", "brief", "cover-score", "cover", "org", "sender", "chans", "go", "count",
  "restored", "clear-draft", "out", "outsum", "copy", "dl", "req"
];
function makeDocument() {
  var doc = new Document();
  SKELETON_IDS.forEach(function (id) {
    var el = doc.createElement(SKELETON_TAGS[id] || "div");
    el.setAttribute("id", id);
    doc.body.appendChild(el);
  });
  doc.getElementById("restored").hidden = true;
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

function installFastTimers(ctx) {
  ctx.setTimeout = function (fn) { return setImmediate(fn); };
  ctx.clearTimeout = function (id) { clearImmediate(id); };
}

var rawHtml = fs.readFileSync(HTML_PATH, "utf8");
var appScriptSrc = dewrap(extractAppScript(rawHtml));
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
  vm.runInContext(appScriptSrc, ctx); // runs renderChannels()/loadDraft()/syncCount() at load, as on the real page
  ctx.__doc = doc;
  return ctx;
}

function pickChannels(ctx, ids) {
  ids.forEach(function (id) { ctx.picked[id] = true; });
  ctx.syncCount();
}
function setBrief(ctx, text) {
  ctx.document.getElementById("brief").value = text;
  ctx.syncCount();
}

var LONG_BRIEF = "From 1 October payroll moves from monthly to twice-monthly for all staff, " +
  "affecting every employee, because the current system loses vendor support in March. " +
  "Everyone needs to activate a portal account by 1 September. " +
  "Questions go to hr@example.com. This is a mandatory change with no opt-out.";

function drain(rounds) {
  var p = Promise.resolve();
  for (var i = 0; i < (rounds || 10); i++) {
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

// --- Regression: no Gamma/mcp machinery -----------------------------------------------

test("0 (regression): no Gamma or mcp capability code ships in the console", function () {
  // A page that declares the mcp capability cannot be shared publicly — that's exactly why
  // Gamma was removed. Guard against it quietly coming back.
  assert(!/Gamma/.test(rawHtml), "found a reference to Gamma in the shipped file");
  assert(!/window\.claude\.use\(\s*["']mcp["']/.test(rawHtml), "found a call to window.claude.use(\"mcp\")");
  assert(!/callTool|listTools/.test(rawHtml), "found MCP call-surface code (callTool/listTools)");
});

// --- Channel selection & the brief input -----------------------------------------------

test("1: picking channels and typing a brief enables Generate", function () {
  var ctx = loadConsole();
  assert(ctx.document.getElementById("go").disabled === true, "button starts disabled");
  pickChannels(ctx, ["email"]);
  assert(ctx.document.getElementById("go").disabled === true, "still disabled with too short a brief");
  setBrief(ctx, LONG_BRIEF);
  assert(ctx.document.getElementById("go").disabled === false, "should enable once a channel is picked and the brief is long enough");
});

test("2: unpicking a channel disables Generate again once none remain", function () {
  var ctx = loadConsole();
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email"]);
  assert(ctx.document.getElementById("go").disabled === false);
  var box = ctx.document.querySelector('.chan[data-id="email"]').querySelector("input");
  box.checked = false;
  box._listeners.change[0]();
  assert(ctx.document.getElementById("go").disabled === true, "should disable once the only picked channel is unpicked");
});

test("3: all seven channels render with the correct producer labels", function () {
  var ctx = loadConsole();
  var chans = ctx.document.querySelectorAll(".chan");
  assert(chans.length === 7, "expected 7 channels, got " + chans.length);
  var byId = {};
  ctx.CHANNELS.forEach(function (c) { byId[c.id] = c; });
  assert(byId.email.by === "docx skill", "Email should be built by the docx skill");
  assert(byId.article.by === "docx skill", "Article should be built by the docx skill");
  assert(byId.briefing_deck.by === "pptx skill", "Briefing deck should be built by the pptx skill");
  assert(byId.newsletter.by === "Canva", "Newsletter should be built by Canva, got: " + byId.newsletter.by);
  assert(byId.banner.by === "Canva", "Intranet banner should be built by Canva");
});

// --- The coverage checker ----------------------------------------------------------------

test("4: a short brief scores nothing and a full brief covers all six required prompts", function () {
  var ctx = loadConsole();
  setBrief(ctx, "too short");
  assert(ctx.document.getElementById("cover-score").textContent === "—", "a short brief should show no score");
  setBrief(ctx, LONG_BRIEF);
  var score = ctx.document.getElementById("cover-score").textContent;
  assert(score === "6 of 6 covered", "expected the long brief to cover all six required prompts, got: " + score);
});

// --- Generate -> the run request ----------------------------------------------------------

test("5: clicking Generate shows the run request naming every picked channel", function () {
  var ctx = loadConsole();
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email", "newsletter", "briefing_deck"]);
  ctx.document.getElementById("go")._listeners.click[0]();
  var req = ctx.document.getElementById("req").textContent;
  // chosen() filters CHANNELS in its declared array order, not selection order.
  assert(req.indexOf("CHANNELS: email, briefing_deck, newsletter") !== -1,
    "expected the run request to list all three channels, got: " + req);
  assert(req.indexOf(LONG_BRIEF) !== -1, "expected the run request to include the brief text");
  assert(ctx.document.getElementById("out").classList.contains("show"), "the output section should be revealed");
});

test("6: the run request carries open questions instead of inventing answers", function () {
  var ctx = loadConsole();
  // Long enough to score, but missing a stated action and a help route.
  setBrief(ctx, "From 1 October we are changing how payroll works for everyone, because the old system is retiring.");
  pickChannels(ctx, ["email"]);
  ctx.document.getElementById("go")._listeners.click[0]();
  var req = ctx.document.getElementById("req").textContent;
  assert(req.indexOf("NOT ANSWERED ABOVE") !== -1, "expected an open-questions section, got: " + req);
  assert(req.indexOf("do not invent answers") !== -1, "expected the explicit no-inventing instruction");
});

// --- Draft persistence ---------------------------------------------------------------------

test("7: the draft survives a reload via localStorage", function () {
  var store = Object.create(null);
  var fakeStorage = {
    getItem: function (k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
    setItem: function (k, v) { store[k] = String(v); },
    removeItem: function (k) { delete store[k]; }
  };
  var ctx1 = loadConsole();
  ctx1.localStorage = fakeStorage;
  setBrief(ctx1, LONG_BRIEF);
  pickChannels(ctx1, ["article"]);

  var ctx2 = loadConsole();
  ctx2.localStorage = fakeStorage;
  var restored = ctx2.loadDraft();
  assert(restored, "expected loadDraft() to find the saved draft");
  assert(ctx2.document.getElementById("brief").value === LONG_BRIEF, "brief text should be restored");
  assert(ctx2.picked.article === true, "the picked channel should be restored");
});

test("8: Start fresh clears the brief, the picks and the saved draft", function () {
  var ctx = loadConsole();
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email"]);
  ctx.document.getElementById("clear-draft")._listeners.click[0]();
  assert(ctx.document.getElementById("brief").value === "", "brief should be cleared");
  assert(Object.keys(ctx.picked).length === 0, "picks should be cleared");
  // syncCount() re-saves after clearing (it always persists current state), so the stored
  // draft is now empty rather than absent — loadDraft() treats an empty brief as "nothing saved".
  assert(ctx.loadDraft() === false, "an empty draft should no longer be treated as a saved one");
});

// --- Download .md ---------------------------------------------------------------------------

test("9: Download .md saves the run request through the downloads capability", function () {
  var saved = null;
  var ctx = loadConsole({
    claudeUse: function (name) {
      return Promise.resolve(name === "downloads" ? { save: function (f) { saved = f; return Promise.resolve(); } } : null);
    }
  });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email"]);
  ctx.document.getElementById("org").value = "Northwind Foods";
  ctx.document.getElementById("dl")._listeners.click[0]();
  return drain(5).then(function () {
    assert(saved, "expected downloads.save() to be called");
    assert(saved.filename === "northwind-foods-run-request.md", "expected a slugified filename, got: " + saved.filename);
    assert(saved.data.indexOf("CHANNELS: email") !== -1, "expected the saved file to contain the run request");
  });
});

test("10: Download .md degrades gracefully when the downloads capability is unavailable", function () {
  var ctx = loadConsole({ claudeUse: function () { return Promise.resolve(null); } });
  setBrief(ctx, LONG_BRIEF);
  pickChannels(ctx, ["email"]);
  var alerted = null;
  ctx.alert = function (msg) { alerted = msg; };
  ctx.document.getElementById("dl")._listeners.click[0]();
  return drain(5).then(function () {
    assert(alerted && alerted.indexOf("Copy instead") !== -1, "expected a fallback alert pointing at Copy, got: " + alerted);
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
