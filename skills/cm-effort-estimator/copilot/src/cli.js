  /* =====================================================================
     Copilot skill CLI

     Appended by build_copilot_pack.py after the engine and judgement blocks
     sliced out of estimator.html, inside the same function scope, so every
     call below runs the artifact's own code. Nothing here does arithmetic of
     its own: it hydrates state, calls the engine, and shapes the report.

     Usage:  node engine.js <command> [input.json]      (or JSON on stdin)
     ===================================================================== */

  const ENGINE_VERSION = "0.5.1";
  const STATUS_LABEL = { accepted: "Accepted", reverted: "Reverted", superseded: "Superseded", proposed: "Proposed", rejected: "Rejected" };
  const round1 = (n) => Math.round((+n || 0) * 10) / 10;

  // ---- compact state: what the agent carries between turns -------------

  function toCompact() {
    const lineEdits = {};
    const customLines = [];
    (state.lines || []).forEach((l) => {
      if (l.judgementAdded) return;
      if (l.custom) {
        customLines.push({ id: l.id, stream: l.stream, name: l.name, archetype: l.archetype, level: l.level,
          mode: l.mode || null, qty: l.qty, include: l.include, optional: l.optional });
        return;
      }
      const ov = lineOverrideOf(l);
      if (ov) {
        const e = {};
        if (ov.editedQty) e.qty = ov.qty;
        if (ov.editedInclude) e.include = ov.include;
        if (ov.editedOptional) e.optional = ov.optional;
        lineEdits[l.id] = e;
      }
    });
    const flags = (o) => Object.fromEntries(Object.keys(o || {}).map((k) => [k, true]));
    return {
      v: ENGINE_VERSION,
      client: state.settings.client || "",
      scopeType: state.scopeType || "",
      rfpAnalysed: Object.keys(state.signals || {}).length > 0 || Object.keys(state.catSignals || {}).length > 0,
      drivers: state.drivers,
      detected: Object.fromEntries(Object.entries(state.detected || {}).map(([k, v]) => [k, v.value])),
      signals: flags(state.signals),
      catSignals: flags(state.catSignals),
      optionalSignals: flags(state.optionalSignals),
      optionalCat: flags(state.optionalCat),
      clientTerms: state.clientTerms || {},
      involvement: state.involvement,
      reviewCycles: state.reviewCycles,
      localisationFactor: state.localisationFactor,
      deliveryMode: state.deliveryMode,
      settings: { hoursPerDay: state.settings.hoursPerDay, contingency: state.settings.contingency },
      lineComplexity: state.lineComplexity,
      lineMode: state.lineMode,
      lineEdits,
      customLines,
      adjustments: state.adjustments || [],
      judgementBaseline: state.judgementBaseline || null
    };
  }

  function fromCompact(c) {
    state = defaultState();
    if (!c) return;
    state.settings.client = c.client || "";
    state.scopeType = c.scopeType || "";
    Object.assign(state.drivers, c.drivers || {});
    state.detected = Object.fromEntries(Object.entries(c.detected || {}).map(([k, v]) => [k, { value: v, evidence: "" }]));
    state.signals = Object.assign({}, c.signals);
    state.catSignals = Object.assign({}, c.catSignals);
    state.optionalSignals = Object.assign({}, c.optionalSignals);
    state.optionalCat = Object.assign({}, c.optionalCat);
    state.clientTerms = Object.assign({}, c.clientTerms);
    if (c.involvement) state.involvement = Object.assign({ global: 100, local: 100 }, c.involvement);
    if (c.reviewCycles) state.reviewCycles = c.reviewCycles;
    if (c.localisationFactor !== undefined) state.localisationFactor = c.localisationFactor;
    if (c.deliveryMode) state.deliveryMode = c.deliveryMode;
    if (c.settings) Object.assign(state.settings, c.settings);
    state.lineComplexity = Object.assign({}, c.lineComplexity);
    state.lineMode = Object.assign({}, c.lineMode);
    state.adjustments = (c.adjustments || []).map((a) => ({ ...a }));
    state.judgementBaseline = c.judgementBaseline || null;

    state.lines = (c.customLines || []).map((cl) => customLine(cl));
    buildLines(false);
    applyLineEdits(c.lineEdits || {});
    buildLines(false);
    // Lines the judgement layer added are not stored: replaying the log
    // re-creates them, with the same ids, exactly as the page does.
    if (state.judgementBaseline) { rebaseJudgement(); replayJudgement(state); }
  }

  function customLine(cl) {
    return rebuildCustom({
      id: cl.id || "custom_" + Date.now(), catId: "", stream: cl.stream || "global", name: cl.name, clientTerm: "",
      desc: `Added for this pursuit · sized as a ${String(cl.archetype || "Strategic Plans & Models").toLowerCase()} deliverable.`,
      unit: cl.unit || "item", cat: "Added for this pursuit", rateKey: "",
      archetype: cl.archetype || "Strategic Plans & Models", level: cl.level || "Standard", mode: cl.mode || null,
      include: cl.include !== false, optional: !!cl.optional, qty: Math.max(0, +cl.qty || 0),
      editedQty: true, editedInclude: true, editedOptional: true, detected: false, custom: true
    });
  }

  function applyLineEdits(edits) {
    state.lines.forEach((l) => {
      const e = edits[l.id];
      if (!e || l.custom) return;
      if (e.qty !== undefined) { l.qty = Math.max(0, +e.qty || 0); l.editedQty = true; }
      if (e.include !== undefined) { l.include = !!e.include; l.editedInclude = true; }
      if (e.optional !== undefined) { l.optional = !!e.optional; l.editedOptional = true; }
    });
  }

  // ---- the report the agent renders ------------------------------------

  function lineRow(l) {
    return {
      id: l.id, stream: l.stream, deliverable: l.name, clientTerm: l.clientTerm || "", unit: l.unit,
      qty: l.qty, level: l.level, mode: l.mode || "", mandaysPerUnit: l.dpu, mandays: round1(l.qty * l.dpu),
      optional: !!l.optional, fromRfp: !!l.detected, custom: !!l.custom, judgementAdded: !!l.judgementAdded
    };
  }

  function report() {
    const t = totals();
    const d = effDrivers();
    const baseline = judgementBaselineTotal();
    const current = t.effortWithBuffer;
    const lines = state.lines.filter((l) => l.include);
    return {
      engine: ENGINE_VERSION,
      client: state.settings.client || "",
      scope: state.scopeType || "(not set)",
      totals: {
        ourMandays: round1(current),
        coreBeforeBuffer: round1(t.effort),
        buffer: round1(t.bufferDays),
        bufferPct: +state.settings.contingency || 0,
        clientMandays: round1(t.clientEffort),
        optionsMandays: round1(t.optEffort),
        averageFte: Math.round(t.fte * 10) / 10,
        months: driverValue("months"),
        deliverables: t.inc.length
      },
      streams: t.streams.map((s) => ({
        stream: s.streamId, buildAllParties: round1(s.build), ourSharePct: Math.round(s.share * 100),
        ourBuild: round1(s.ourBuild), ourReview: round1(s.ourReview), reviewCycles: s.cycles, ourTotal: round1(s.ourTotal)
      })),
      byRank: RANKS.slice().reverse().filter((r) => t.byRank[r.id] >= 0.05).map((r) => ({ rank: r.name, mandays: round1(t.byRank[r.id]) })),
      drivers: DRIVERS.map((dr) => ({
        key: dr.key, label: dr.label, value: d[dr.key],
        source: state.detected[dr.key] ? "read from RFP" : (state.drivers[dr.key] === "" ? "default assumed" : "entered")
      })),
      lines: lines.filter((l) => !l.optional).map(lineRow),
      options: lines.filter((l) => l.optional).map(lineRow),
      excluded: state.lines.filter((l) => !l.include).map((l) => ({ id: l.id, deliverable: l.name })),
      judgement: {
        baseline: round1(baseline),
        current: round1(current),
        movedPct: baseline > 0 ? Math.round(((current - baseline) / baseline) * 1000) / 10 : 0,
        warning: judgementWarningActive(),
        log: (state.adjustments || []).map((a) => ({
          id: a.id, op: a.op, target: a.target, value: a.value, rationale: a.rationale,
          confidence: a.confidence, status: STATUS_LABEL[a.status] || a.status, deltaMandays: a.deltaMandays || 0
        }))
      },
      assumptions: state.lines.length ? assumptionItems() : [],
      adjustmentsTsv: workbookTsv()["Adjustments!A6"]
    };
  }

  // ---- TSV blocks for the Excel workbook -------------------------------
  // Column order here is the workbook's column order; build_copilot_pack.py
  // generates both from the same spec, so a paste lands in the right cells.

  const yn = (b) => (b ? "Y" : "");
  const tsv = (rows) => rows.map((r) => r.map((c) => String(c == null ? "" : c).replace(/[\t\n]/g, " ")).join("\t")).join("\n");

  function workbookTsv() {
    const lineIds = [];
    STREAMS.forEach((st) => CATALOG.forEach((c) => lineIds.push(lineKey(st.id, c.id))));
    const byId = Object.fromEntries(state.lines.map((l) => [l.id, l]));
    const lineRows = lineIds.map((id) => {
      const [, catId] = id.split(":");
      const entry = CATALOG.find((c) => c.id === catId);
      const l = byId[id];
      const signal = (state.catSignals || {})[catId] || (state.signals || {})[entry.rateKey];
      // Overrides only where a person set them by hand: everything else the
      // workbook derives itself, exactly as the engine does.
      const snapOv = state.judgementBaseline ? (state.judgementBaseline.lineOverrides[id] || {}) : null;
      const src = snapOv || (l ? lineOverrideOf(l) || {} : {});
      const baseLevel = state.judgementBaseline ? state.judgementBaseline.lineComplexity[id] : state.lineComplexity[id];
      const baseMode = state.judgementBaseline ? state.judgementBaseline.lineMode[id] : state.lineMode[id];
      return [yn(signal), yn(isOptional(entry)), (state.clientTerms || {})[catId] || "",
        src.editedInclude ? (src.include ? "Y" : "N") : "",
        src.editedQty ? src.qty : "",
        baseLevel || "", baseMode || "",
        src.editedOptional ? (src.optional ? "Y" : "N") : ""];
    });

    // Custom lines as they stood before judgement; lines judgement added carry
    // the id of the adjustment that added them, so the workbook can count them
    // only while that adjustment stands.
    const baseCustom = state.lines.filter((l) => l.custom && !l.judgementAdded).map((l) => {
      const ov = state.judgementBaseline ? state.judgementBaseline.lineOverrides[l.id] : null;
      const v = ov || l;
      return [l.id, l.stream, l.name, l.archetype, v.level || l.level, v.mode || "", v.qty, v.include ? "Y" : "N", v.optional ? "Y" : "N", ""];
    });
    const judgedCustom = (state.adjustments || []).filter((a) => a.op === "add_line").map((a) => [
      "judgement_" + a.id, a.target, a.value.name, a.value.archetype || "Strategic Plans & Models", a.value.level || "Standard",
      "", Math.max(0, +a.value.qty || 1), "Y", "", a.id]);

    const adjRows = (state.adjustments || []).map((a) => [a.id, a.op, a.target,
      a.op === "add_line" ? a.value.name : (typeof a.value === "boolean" ? String(a.value) : (a.value == null ? "" : a.value)),
      a.rationale, a.confidence, STATUS_LABEL[a.status] || a.status, a.deltaMandays || 0]);

    const base = state.judgementBaseline;
    const drv = base ? base.drivers : state.drivers;
    const inv = base ? base.involvement : state.involvement;
    const inputs = [
      [state.settings.client || ""], [state.scopeType || ""], [state.deliveryMode || "blended"],
      [base ? base.reviewCycles : state.reviewCycles], [state.settings.hoursPerDay || 8],
      [base ? base.contingency : state.settings.contingency], [inv.global], [inv.local],
      [(base ? base.localisationFactor : state.localisationFactor) || ""],
      [yn(Object.keys(state.signals || {}).length > 0 || Object.keys(state.catSignals || {}).length > 0)]
    ];

    return {
      "Inputs!C5": tsv(inputs),
      "Inputs!C18": tsv(DRIVERS.map((dr) => [drv[dr.key] === undefined ? "" : drv[dr.key]])),
      "Lines!E6": tsv(lineRows),
      "Custom lines!A6": tsv(baseCustom.concat(judgedCustom)),
      "Adjustments!A6": tsv(adjRows),
      // The whole estimate, so a saved workbook can restart a new chat.
      "State!A6": JSON.stringify(toCompact())
    };
  }

  // ---- commands ---------------------------------------------------------

  function refuse(draft, reason) { return { proposal: draft, ok: false, reason }; }

  const COMMANDS = {
    // Read an RFP the way the page's Analyse button does.
    analyse(input) {
      fromCompact(input.state || null);
      state.rfpText = String(input.rfpText || "");
      if (input.scopeType) state.scopeType = input.scopeType;
      if (input.client) state.settings.client = input.client;
      if (!state.scopeType) state.scopeType = "global";
      if (!state.rfpText.trim()) throw new Error("rfpText is empty: pass the RFP's scope text");
      analyseScope();
      const evidence = Object.entries(state.detected).map(([k, v]) => ({
        driver: k, label: (DRIVERS.find((d) => d.key === k) || {}).label, value: v.value, evidence: v.evidence }));
      const signalled = CATALOG.filter((c) => (state.catSignals || {})[c.id] || (state.signals || {})[c.rateKey]).map((c) => ({
        catalogueId: c.id, deliverable: c.name, clientTerm: (state.clientTerms || {})[c.id] || "",
        optional: isOptional(c), evidence: (state.catSignals || {})[c.id] || (state.signals || {})[c.rateKey] }));
      const notStated = DRIVERS.filter((d) => !state.detected[d.key]).map((d) => ({
        driver: d.key, label: d.label, defaultAssumed: d.type === "select" ? d.def : d.def }));
      state.rfpText = "";
      return { evidence, signalled, notStated, state: toCompact(), report: report() };
    },

    estimate(input) {
      fromCompact(input.state || null);
      if (!state.scopeType) state.scopeType = input.scopeType || "global";
      if (!state.lines.length) buildLines(true);
      return { state: toCompact(), report: report() };
    },

    // Hand edits: the person changing a lever directly, not via judgement.
    set(input) {
      fromCompact(input.state || null);
      const ch = input.changes || {};
      if (ch.client !== undefined) state.settings.client = ch.client;
      if (ch.scopeType) state.scopeType = ch.scopeType;
      if (ch.deliveryMode) state.deliveryMode = ch.deliveryMode;
      if (ch.reviewCycles !== undefined) state.reviewCycles = Math.min(3, Math.max(1, +ch.reviewCycles || 1));
      if (ch.contingency !== undefined) state.settings.contingency = Math.max(0, +ch.contingency || 0);
      if (ch.localisationFactor !== undefined) state.localisationFactor = Math.max(0, +ch.localisationFactor || 0);
      if (ch.involvement) Object.assign(state.involvement, ch.involvement);
      Object.entries(ch.drivers || {}).forEach(([k, v]) => {
        if (DRIVERS.some((d) => d.key === k)) state.drivers[k] = v === "" || v === null ? "" : v;
      });
      buildLines(false);
      Object.entries(ch.lines || {}).forEach(([id, e]) => {
        const l = state.lines.find((x) => x.id === id);
        if (!l) return;
        if (e.level) { if (l.custom) l.level = e.level; else state.lineComplexity[id] = e.level; }
        if (e.mode) { if (l.custom) l.mode = e.mode; else state.lineMode[id] = e.mode; }
      });
      applyLineEdits(ch.lines || {});
      (ch.addLines || []).forEach((cl) => state.lines.push(customLine(cl)));
      buildLines(false);
      rebaseJudgement();
      return { state: toCompact(), report: report() };
    },

    // Validate each proposal and give its own delta, plus the batch's
    // combined delta. Touches nothing: the state handed back is unchanged.
    preview(input) {
      fromCompact(input.state || null);
      const results = (input.proposals || []).map((p) => {
        const c = coerceForValidation(p);
        const v = validateAdjustment(c, state);
        if (!v.ok) return refuse(p, v.reason);
        return { proposal: normaliseAdjustment(c), ok: true, deltaMandays: previewAdjustmentDelta(c) };
      });
      const current = totals().effortWithBuffer;
      const batchDelta = previewAdjustmentsDelta(input.proposals || []);
      return { results, current: round1(current), batchDelta, ifAllAccepted: round1(current + batchDelta), state: toCompact() };
    },

    accept(input) {
      fromCompact(input.state || null);
      const results = (input.proposals || []).map((p) => {
        const r = acceptAdjustment(p);
        return r.ok ? { proposal: p, ok: true, id: r.id } : refuse(p, r.reason);
      });
      return { results, state: toCompact(), report: report() };
    },

    revert(input) {
      fromCompact(input.state || null);
      const results = (input.ids || []).map((id) => ({ id, ...revertAdjustment(id) }));
      return { results, state: toCompact(), report: report() };
    },

    // Every block the workbook needs, keyed by the cell to paste it at.
    export(input) {
      fromCompact(input.state || null);
      return { blocks: workbookTsv(), state: toCompact(), report: report() };
    },

    // The page's "how this was estimated" line, so the agent explains a
    // number from the engine's own working rather than paraphrasing it.
    explain(input) {
      fromCompact(input.state || null);
      const ids = input.ids || [];
      const hpd = state.settings.hoursPerDay || 8;
      const results = ids.map((id) => {
        const l = state.lines.find((x) => x.id === id);
        if (!l) return { id, ok: false, reason: `no line "${id}" in this estimate` };
        const source = l.daysBasis === "library"
          ? `${l.libHours} h from ${l.daysN} library task${l.daysN === 1 ? "" : "s"} at ${l.level} ÷ ${hpd} h/day`
          : l.daysBasis === "custom"
            ? `${l.customPerTask} h per task at ${l.level} × ${l.customTasks} tasks ÷ ${hpd} h/day`
            : l.daysBasis === "benchmark" ? `benchmarked on ${l.daysN} past project line${l.daysN === 1 ? "" : "s"}`
              : "standard effort assumption";
        const factors = [
          l.localF !== 1 ? `× ${Math.round(l.localF * 100)}% to adapt rather than build` : "",
          l.multParts && l.multParts.length ? `× ${l.multParts.join(" × ")}` : "",
          l.mode && l.effortF !== 1 ? `× ${l.mode} delivery ×${l.effortF}` : ""
        ].filter(Boolean);
        const plural = `${l.qty} ${l.unit}${l.qty === 1 ? "" : "s"}`;
        const steps = factors.length
          ? [source, `= ${l.baseDpu} mandays per ${l.unit}`, ...factors, `= ${l.dpu} mandays per ${l.unit} × ${plural}`]
          : [source, `= ${l.dpu} mandays per ${l.unit} × ${plural}`];
        steps.push(`= ${round1(l.qty * l.dpu)} mandays`);
        return { id, ok: true, deliverable: l.name, clientTerm: l.clientTerm || "", included: l.include, optional: l.optional,
          tasks: l.desc, working: steps.join(" ") };
      });
      return { results, state: toCompact() };
    },

    rebuild(input) {
      fromCompact(input.state || null);
      rebuildFromScopeWithJudgement();
      return { state: toCompact(), report: report() };
    },

    // Reference data for knowledge files and the workbook.
    data() {
      return {
        engine: ENGINE_VERSION,
        drivers: DRIVERS.map((d) => ({ key: d.key, label: d.label, type: d.type, def: d.def, options: d.options || null })),
        catalogue: CATALOG, tasks: TASKS, archetypeHours: ARCHETYPE_HOURS, rankMix: RANK_MIX, defaultMix: DEFAULT_MIX,
        ranks: RANKS, modes: MODES, modeFactors: MODE_FACTORS, modeApplies: [...MODE_APPLIES],
        complexityMult: COMPLEXITY_MULT, maturityMult: MATURITY_MULT,
        localisationFactor: LOCALISATION_FACTOR, reviewClientPct: REVIEW_CLIENT_PCT, reviewOursPct: REVIEW_OURS_PCT,
        quotes: SAMPLE_QUOTES, taxonomy: TAXONOMY.map((t) => ({ id: t.id, name: t.name, kw: t.kw })),
        judgementGlobals: JUDGEMENT_GLOBAL_RANGES, samples: { publicAuthority: SAMPLE_RFP, transport: SAMPLE_RFP_TRANSPORT }
      };
    },

    // A one-line health check the agent runs before anything else.
    selftest() {
      fromCompact(null);
      state.scopeType = "global";
      state.rfpText = SAMPLE_RFP;
      analyseScope();
      const total = totals().effortWithBuffer;
      return { ok: isFinite(total) && total > 0, engine: ENGINE_VERSION, sampleMandays: round1(total) };
    }
  };

  function readInput(argv) {
    const file = argv[3];
    if (file) return JSON.parse(require("fs").readFileSync(file, "utf8"));
    try { const raw = require("fs").readFileSync(0, "utf8"); return raw.trim() ? JSON.parse(raw) : {}; }
    catch (e) { return {}; }
  }

  function main(argv) {
    const cmd = argv[2];
    if (!COMMANDS[cmd]) {
      process.stdout.write(JSON.stringify({ ok: false, error: `unknown command "${cmd}"`, commands: Object.keys(COMMANDS) }) + "\n");
      process.exitCode = 2;
      return;
    }
    try {
      const out = COMMANDS[cmd](cmd === "data" || cmd === "selftest" ? {} : readInput(argv));
      process.stdout.write(JSON.stringify(out, null, argv.includes("--pretty") ? 2 : 0) + "\n");
    } catch (e) {
      process.stdout.write(JSON.stringify({ ok: false, error: String(e && e.message || e) }) + "\n");
      process.exitCode = 1;
    }
  }

  if (typeof module !== "undefined" && require.main === module) main(process.argv);
  else if (typeof module !== "undefined") module.exports = { COMMANDS, toCompact, fromCompact, getState: () => state };
