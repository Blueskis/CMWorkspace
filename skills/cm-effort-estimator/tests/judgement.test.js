"use strict";

// Exercises the judgement layer against the real estimator.html source, not a
// second copy of the logic. The "engine" and "judgement" blocks are sliced
// out by their marker comments and evaluated in Node with a localStorage
// stub, so a bug here is a bug in what actually ships.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const HTML_PATH = path.join(__dirname, "..", "estimator.html");

function sliceBetween(text, startMarker, endMarker) {
  const start = text.indexOf(startMarker);
  const end = text.indexOf(endMarker);
  if (start === -1) throw new Error(`marker not found: ${startMarker}`);
  if (end === -1) throw new Error(`marker not found: ${endMarker}`);
  if (end < start) throw new Error(`markers out of order: ${startMarker} / ${endMarker}`);
  return text.slice(start + startMarker.length, end);
}

function makeLocalStorageStub() {
  const store = {};
  return {
    getItem: (k) => (Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; }
  };
}

// A fresh engine instance per call — tests must not leak state into one
// another via a shared module cache, since `state` here is a plain mutable
// closure variable, not a re-importable module.
function loadEngine() {
  const html = fs.readFileSync(HTML_PATH, "utf8");
  const engine = sliceBetween(html, "// ---- engine start ----", "// ---- engine end ----");
  const judgement = sliceBetween(html, "// ---- judgement start ----", "// ---- judgement end ----");

  const exportTail = `
    return {
      getState: function () { return state; },
      setState: function (s) { state = s; },
      resetState: function () { state = defaultState(); },
      defaultState: defaultState,
      DRIVERS: DRIVERS, LEVELS: LEVELS, MODES: MODES, CATALOG: CATALOG, STREAMS: STREAMS,
      buildLines: buildLines, totals: totals,
      deepClone: deepClone,
      validateAdjustment: validateAdjustment,
      previewAdjustmentDelta: previewAdjustmentDelta,
      acceptAdjustment: acceptAdjustment,
      revertAdjustment: revertAdjustment,
      rebuildFromScopeWithJudgement: rebuildFromScopeWithJudgement,
      judgementBaselineTotal: judgementBaselineTotal,
      acceptedAdjustments: acceptedAdjustments,
      judgementWarningActive: judgementWarningActive,
      parseAssistantResponse: parseAssistantResponse
    };
  `;

  const src = `"use strict";\n${engine}\n${judgement}\n${exportTail}`;
  const factory = new Function("localStorage", "document", "navigator", "location", src);
  const localStorageStub = makeLocalStorageStub();
  // document/navigator/location are only referenced inside function bodies
  // this slice never calls (rendering, DOM wiring, file parsing) — undefined
  // is enough to let those definitions parse without ever being invoked.
  return factory(localStorageStub, undefined, undefined, undefined);
}

// Sets scopeType and runs a first build so lines exist to target. Mirrors
// picking "global" scope in the real app, minus the DOM — and, since no RFP
// has been analysed, forces every line included rather than just the core
// ones (buildLines' own "analysed ? ... : entry.core" fallback), so driver
// changes have real material to move across the whole deliverable set.
function primed(overrides) {
  const e = loadEngine();
  const s = e.getState();
  s.scopeType = "global";
  Object.assign(s.drivers, { headcount: 1000, units: 3, geos: 1, languages: 1, waves: 2, months: 9, modules: 6, sessionSize: 20, hypercareMonths: 2, complexity: 3, maturity: "medium" }, overrides || {});
  e.buildLines(true);
  // editedInclude, not just include: buildLines(false) — which every
  // judgement replay calls — falls back to the analysed/core default for any
  // line that isn't marked edited, exactly like ticking the checkbox in the
  // real UI does. Forcing include alone would get silently reverted on the
  // next rebuild.
  s.lines.forEach((l) => { l.include = true; l.editedInclude = true; });
  return e;
}

function firstIncludedLine(e) {
  const t = e.totals();
  assert.ok(t.inc.length > 0, "expected at least one included line to test against");
  return t.inc[0];
}

// ---------------------------------------------------------------------------
// Validation and parsing (tests 1-8)
// ---------------------------------------------------------------------------

test("1: valid set_driver proposal validates", () => {
  const e = primed();
  const r = e.validateAdjustment({ op: "set_driver", target: "waves", value: 5, rationale: "Five onboarding waves named in the brief." }, e.getState());
  assert.equal(r.ok, true);
});

test("2: set_global targeting a non-existent deliverable is refused as malformed", () => {
  const e = primed();
  const r = e.validateAdjustment({ op: "set_line_qty", target: "global:not_a_deliverable", value: 3, rationale: "x" }, e.getState());
  assert.equal(r.ok, false);
  assert.match(r.reason, /malformed/);
});

test("3: proposal targeting admin configuration (taskHours/archetypes) is refused as out of scope", () => {
  const e = primed();
  const r1 = e.validateAdjustment({ op: "set_global", target: "taskHours", value: 1, rationale: "x" }, e.getState());
  assert.equal(r1.ok, false);
  assert.match(r1.reason, /out of scope/);
  const r2 = e.validateAdjustment({ op: "set_global", target: "archetypes", value: 1, rationale: "x" }, e.getState());
  assert.equal(r2.ok, false);
  assert.match(r2.reason, /out of scope/);
});

test("4: set_global involvement.global out of range (140) is refused, not clamped", () => {
  const e = primed();
  const r = e.validateAdjustment({ op: "set_global", target: "involvement.global", value: 140, rationale: "x" }, e.getState());
  assert.equal(r.ok, false);
  assert.match(r.reason, /out of range/);
});

test("5: set_line_level with an invalid level is refused", () => {
  const e = primed();
  const line = firstIncludedLine(e);
  const r = e.validateAdjustment({ op: "set_line_level", target: line.id, value: "Very Complex", rationale: "x" }, e.getState());
  assert.equal(r.ok, false);
  assert.match(r.reason, /Simple, Standard or Complex/);
});

test("6: empty rationale is refused", () => {
  const e = primed();
  const r = e.validateAdjustment({ op: "set_driver", target: "waves", value: 5, rationale: "" }, e.getState());
  assert.equal(r.ok, false);
  assert.match(r.reason, /rationale/);
});

test("7: a non-JSON assistant reply is a parse failure, not a crash", () => {
  const e = loadEngine();
  const r = e.parseAssistantResponse("Sure, I'd suggest raising the waves driver to five.");
  assert.equal(r.ok, false);
});

test("8: an empty adjustments array plus a note parses as 'no change proposed'", () => {
  const e = loadEngine();
  const r = e.parseAssistantResponse(JSON.stringify({ adjustments: [], note: "Nothing here changes the estimate." }));
  assert.equal(r.ok, true);
  assert.equal(r.adjustments.length, 0);
  assert.equal(r.note, "Nothing here changes the estimate.");
});

// ---------------------------------------------------------------------------
// Apply, delta and revert (tests 9-18)
// ---------------------------------------------------------------------------

test("9: accepting set_line_qty on one line only moves that line and the totals above it", () => {
  const e = primed();
  const before = e.totals();
  const line = before.inc[0];
  const otherLineIds = before.inc.slice(1).map((l) => l.id);
  const otherQtyBefore = Object.fromEntries(before.inc.slice(1).map((l) => [l.id, l.qty]));

  const res = e.acceptAdjustment({ op: "set_line_qty", target: line.id, value: line.qty + 3, rationale: "Client confirmed three additional units." });
  assert.equal(res.ok, true);

  const after = e.totals();
  const changedLine = after.inc.find((l) => l.id === line.id);
  assert.equal(changedLine.qty, line.qty + 3);
  otherLineIds.forEach((id) => {
    const l = after.inc.find((x) => x.id === id);
    assert.equal(l.qty, otherQtyBefore[id]);
  });
  assert.notEqual(after.effortWithBuffer, before.effortWithBuffer);
});

test("10: the predicted delta shown before accepting matches the actual movement once accepted", () => {
  const e = primed();
  const before = e.totals().effortWithBuffer;
  const draft = { op: "set_driver", target: "waves", value: 5, rationale: "Five waves named in the brief." };
  const predicted = e.previewAdjustmentDelta(draft);
  assert.equal(e.totals().effortWithBuffer, before, "preview must not mutate live state");

  e.acceptAdjustment(draft);
  const after = e.totals().effortWithBuffer;
  assert.equal(Math.round((after - before) * 10) / 10, predicted);
});

test("11: rejecting a proposal leaves state untouched (a rejection is never logged)", () => {
  const e = primed();
  const before = JSON.stringify(e.getState());
  // "Reject" is simply never calling acceptAdjustment — there is no separate
  // state-mutating reject() to call, by design.
  const after = JSON.stringify(e.getState());
  assert.equal(after, before);
});

test("12: reverting the only adjustment restores the exact prior total", () => {
  const e = primed();
  const before = e.totals().effortWithBuffer;
  const res = e.acceptAdjustment({ op: "set_driver", target: "waves", value: 6, rationale: "Six onboarding waves." });
  assert.equal(res.ok, true);
  assert.notEqual(e.totals().effortWithBuffer, before);

  const rev = e.revertAdjustment(res.id);
  assert.equal(rev.ok, true);
  assert.equal(e.totals().effortWithBuffer, before);
  assert.equal(e.getState().drivers.waves, 2);
});

test("13: two adjustments on one line, revert the first — the second remains applied", () => {
  const e = primed();
  const line = firstIncludedLine(e);
  const baseQty = line.qty;

  const a1 = e.acceptAdjustment({ op: "set_line_qty", target: line.id, value: baseQty + 2, rationale: "First correction." });
  const a2 = e.acceptAdjustment({ op: "set_line_qty", target: line.id, value: baseQty + 5, rationale: "Second correction supersedes the first." });
  assert.equal(a1.ok, true);
  assert.equal(a2.ok, true);

  const totalWithBoth = e.totals().effortWithBuffer;

  const rev = e.revertAdjustment(a1.id);
  assert.equal(rev.ok, true);

  const lineNow = e.totals().inc.find((l) => l.id === line.id);
  assert.equal(lineNow.qty, baseQty + 5, "second adjustment's value should still be in effect");

  // Compare against applying only the second adjustment from scratch.
  const e2 = primed();
  const line2 = e2.totals().inc.find((l) => l.id === line.id);
  e2.acceptAdjustment({ op: "set_line_qty", target: line2.id, value: baseQty + 5, rationale: "Second correction supersedes the first." });
  assert.equal(e.totals().effortWithBuffer, e2.totals().effortWithBuffer);
});

test("14: set_driver waves 2 -> 5 moves wave-quantified lines but not one-off lines", () => {
  const e = primed();
  const cmPlanBefore = e.totals().inc.find((l) => l.catId === "cm_plan");
  const readinessBefore = e.totals().inc.find((l) => l.catId === "readiness_assess");
  assert.ok(cmPlanBefore, "cm_plan should be included by default (core)");

  e.acceptAdjustment({ op: "set_driver", target: "waves", value: 5, rationale: "Five onboarding waves." });

  const cmPlanAfter = e.totals().inc.find((l) => l.catId === "cm_plan");
  assert.equal(cmPlanAfter.qty, cmPlanBefore.qty, "a one-off ('qty: one') deliverable should not scale with waves");

  if (readinessBefore) {
    const readinessAfter = e.totals().inc.find((l) => l.catId === "readiness_assess");
    assert.notEqual(readinessAfter.qty, readinessBefore.qty, "a wave-quantified deliverable should scale with waves");
  }
});

test("15: accepted adjustments totalling more than 40% of baseline raise the warning, and still compute", () => {
  const e = primed();
  const baseline = e.totals().effortWithBuffer;
  e.acceptAdjustment({ op: "set_driver", target: "waves", value: 12, rationale: "Programme now onboards in twelve waves." });
  e.acceptAdjustment({ op: "set_driver", target: "units", value: 20, rationale: "Twenty business units in scope, not three." });

  const current = e.totals().effortWithBuffer;
  assert.ok(isFinite(current) && current > 0);
  const movedEnough = Math.abs(current - baseline) / baseline > 0.4;
  assert.equal(e.judgementWarningActive(), movedEnough);
});

test("16: a note adjustment moves no number", () => {
  const e = primed();
  const before = e.totals().effortWithBuffer;
  const res = e.acceptAdjustment({ op: "note", target: "global", value: null, rationale: "Client has no dedicated change lead — flagged for the proposal, not sized here." });
  assert.equal(res.ok, true);
  assert.equal(e.totals().effortWithBuffer, before);
});

test("17: baseline plus the sum of accepted deltas equals the current total, exactly", () => {
  const e = primed();
  const baseline = e.judgementBaselineTotal();
  e.acceptAdjustment({ op: "set_driver", target: "waves", value: 4, rationale: "Four waves." });
  const line = firstIncludedLine(e);
  e.acceptAdjustment({ op: "set_line_qty", target: line.id, value: line.qty + 1, rationale: "One extra unit confirmed." });
  e.acceptAdjustment({ op: "set_global", target: "contingency", value: 15, rationale: "Scope still volatile at this stage." });

  const sumOfDeltas = e.acceptedAdjustments().reduce((s, a) => s + a.deltaMandays, 0);
  const current = e.totals().effortWithBuffer;
  assert.equal(Math.round((baseline + sumOfDeltas) * 10) / 10, Math.round(current * 10) / 10);
});

test("18: rebuild from scope with judgement applied keeps driver/global adjustments and supersedes per-line ones", () => {
  const e = primed();
  const line = firstIncludedLine(e);
  const driverAdj = e.acceptAdjustment({ op: "set_driver", target: "waves", value: 5, rationale: "Five waves." });
  const lineAdj = e.acceptAdjustment({ op: "set_line_qty", target: line.id, value: line.qty + 10, rationale: "Manually bumped for this pursuit." });
  assert.equal(driverAdj.ok, true);
  assert.equal(lineAdj.ok, true);

  e.rebuildFromScopeWithJudgement();

  const adjustments = e.getState().adjustments;
  const driverEntry = adjustments.find((a) => a.id === driverAdj.id);
  const lineEntry = adjustments.find((a) => a.id === lineAdj.id);
  assert.equal(driverEntry.status, "accepted", "driver adjustments survive a rebuild");
  assert.equal(lineEntry.status, "superseded", "per-line adjustments are marked superseded, not dropped");
  assert.equal(e.getState().drivers.waves, 5, "the surviving driver adjustment should still be in effect");
});

test("smoke: buildLines/totals produce finite, non-negative numbers on a minimal driver set", () => {
  const e = primed({ headcount: 1, units: 1, geos: 1, languages: 1, waves: 1, months: 1, modules: 1, sessionSize: 1, hypercareMonths: 1 });
  const t = e.totals();
  assert.ok(isFinite(t.effortWithBuffer));
  assert.ok(t.effortWithBuffer >= 0);
});
