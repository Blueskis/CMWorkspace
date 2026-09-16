/**
 * Consulting Deck Builder — brand -> deck type -> upload -> review -> generate -> deliver.
 *
 * A separate app from webapp/'s Training Deck Generator (built for FSD-sourced learner
 * decks with screenshot annotation and knowledge checks). This one covers the nine
 * consulting deck types in lib/deck/deck-types.js — steerco updates, case for change,
 * findings decks, etc. — sourced from Word/PDF/PowerPoint documents against the client's
 * own brand and template. Shares the same core (lib/deck/) as the training app and the
 * skills/deck-builder/ skill, but is its own front end with its own brand-intake step,
 * its own deck-type-aware plan generation (deck-plan.js), and its own validation gates
 * (validate-plan.js) — none of which the training pipeline has or needs.
 */

import { parseSources } from "../../lib/deck/parse.js";
import { profileTemplate } from "../../lib/deck/profile-template.js";
import { resolveLayoutRoles, ROLES, ROLE_LABELS } from "../../lib/deck/map-layouts.js";
import { buildPptx } from "../../lib/deck/build-pptx.js";
import * as brand from "../../lib/deck/brand.js";
import { DECK_TYPES, DECK_TYPE_ORDER } from "../../lib/deck/deck-types.js";
import { generateDeckPlan } from "./deck-plan.js";
import { validatePlan } from "./validate-plan.js";

const state = {
  step: "brand", // brand -> deckType -> upload -> parsing -> review -> generating -> planReview -> building -> done -> error
  brandProfile: null,
  brandRoute: "template", // "template" | "vault" | "manual"
  brandManualFields: { client: "", primary: "2E3D77", secondary: "0B6B54", accent: "8C5E0C", ink: "12161F", canvas: "F3F5F9", headingFont: "Georgia", bodyFont: "Arial" },
  brandVaultText: "",
  brandError: null,
  deckType: null,
  templateFile: null,
  sourceFiles: [],
  profile: null,
  assignment: null,
  overrides: {},
  mappingNotes: [],
  corpus: null,
  stage: null,
  planResult: null, // { brief, plan }
  planValidation: null,
  result: null, // { built, planValidation }
  error: null,
  errorCode: null,
  errorRetriable: false,
  objectUrls: [],
};

function $(sel, root = document) { return root.querySelector(sel); }
function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}
function trackUrl(blob) {
  const url = URL.createObjectURL(blob);
  state.objectUrls.push(url);
  return url;
}
function revokeAllUrls() {
  state.objectUrls.forEach((u) => URL.revokeObjectURL(u));
  state.objectUrls = [];
}
function stat(value, label) {
  return el("div", { class: "stat" }, [el("b", {}, String(value)), el("span", {}, label)]);
}

// ---------------------------------------------------------------------------
// step 1 — brand
// ---------------------------------------------------------------------------

function renderBrand(root) {
  const route = state.brandRoute;
  const tab = (id, label) => el("button", {
    class: `btn small ${route === id ? "btn--primary" : ""}`,
    onclick: () => { state.brandRoute = id; state.brandError = null; render(root); },
  }, label);

  let body;
  if (route === "template") {
    body = el("p", { class: "muted" },
      "The brand will be extracted from your template's own theme (colours, fonts) once " +
      "you upload it on the next step — nothing to do here. It won't carry a tagline, " +
      "voice, or terminology; add those later if you want the query-matching benefit.");
  } else if (route === "vault") {
    body = el("div", {}, [
      el("p", { class: "muted" }, "Paste a Brand Vault export (the .json a Brand Vault artifact exports)."),
      el("textarea", {
        rows: "6", style: "width:100%;font-family:var(--font-mono);font-size:12px;padding:8px;border-radius:6px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);",
        oninput: (e) => { state.brandVaultText = e.target.value; },
      }, state.brandVaultText),
    ]);
  } else {
    const f = state.brandManualFields;
    const field = (key, label, type = "text") => el("label", { style: "display:flex;flex-direction:column;gap:4px;font-size:12.5px;" }, [
      label,
      el("input", {
        type, value: f[key],
        style: "padding:6px 8px;border-radius:6px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);font:inherit;",
        oninput: (e) => { f[key] = e.target.value; },
      }),
    ]);
    body = el("div", { style: "display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;" }, [
      field("client", "Client name"),
      field("primary", "Primary (hex)"),
      field("secondary", "Secondary (hex)"),
      field("accent", "Accent (hex)"),
      field("ink", "Ink / text (hex)"),
      field("canvas", "Canvas / background (hex)"),
      field("headingFont", "Heading font"),
      field("bodyFont", "Body font"),
    ]);
  }

  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "1. Brand"),
      el("p", { class: "panel__lede" },
        "How should this deck's brand come from? None of these are used until you name an " +
        "approver later — an unapproved palette is treated the same as none at all."),
      el("div", { class: "row", style: "gap:8px;margin-bottom:16px;" }, [tab("template", "From template"), tab("vault", "Brand Vault export"), tab("manual", "Enter manually")]),
      body,
      state.brandError ? el("div", { class: "notice notice--error" }, state.brandError) : null,
      el("div", { class: "panel__actions" }, [
        el("button", { class: "btn btn--primary", onclick: () => confirmBrand(root) }, "Continue"),
      ]),
    ])
  );
}

function confirmBrand(root) {
  state.brandError = null;
  try {
    if (state.brandRoute === "template") {
      state.brandProfile = null; // resolved after the template is parsed, in runParse()
    } else if (state.brandRoute === "vault") {
      if (!state.brandVaultText.trim()) throw new Error("Paste a Brand Vault export first, or switch tabs.");
      const vault = JSON.parse(state.brandVaultText);
      state.brandProfile = brand.fromVault(vault);
    } else {
      if (!state.brandManualFields.client.trim()) throw new Error("Enter a client name.");
      state.brandProfile = brand.manual(state.brandManualFields);
    }
  } catch (e) {
    state.brandError = e.message || String(e);
    render(root);
    return;
  }
  state.step = "deckType";
  render(root);
}

// ---------------------------------------------------------------------------
// step 2 — deck type
// ---------------------------------------------------------------------------

function renderDeckType(root) {
  const cards = DECK_TYPE_ORDER.map((id) => {
    const t = DECK_TYPES[id];
    const selected = state.deckType === id;
    return el("div", {
      class: "card", style: `cursor:pointer;padding:16px;${selected ? "border-color:var(--accent);box-shadow:0 0 0 2px var(--accent-soft);" : ""}`,
      onclick: () => { state.deckType = id; render(root); },
    }, [
      el("h3", { style: "margin:0 0 4px;font-size:14.5px;" }, t.label),
      el("p", { class: "muted", style: "margin:0;font-size:12.5px;" }, t.description),
    ]);
  });

  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "2. Deck type"),
      el("p", { class: "panel__lede" }, "Picks the narrative spine and the slide roles the plan must include."),
      el("div", { style: "display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;" }, cards),
      el("div", { class: "panel__actions" }, [
        el("button", { class: "btn", onclick: () => { state.step = "brand"; render(root); } }, "Back"),
        el("button", { class: "btn btn--primary", disabled: !state.deckType ? "disabled" : null, onclick: () => { state.step = "upload"; render(root); } }, "Continue"),
      ]),
    ])
  );
}

// ---------------------------------------------------------------------------
// step 3 — upload
// ---------------------------------------------------------------------------

function dropZone(label, hint, input) {
  return el("label", { class: "drop-zone" }, [
    el("span", { class: "drop-zone__label" }, label),
    el("span", { class: "drop-zone__hint" }, hint),
    input,
  ]);
}

function renderUpload(root) {
  const status = el("p", { class: "upload-status" });
  const templateInput = el("input", {
    type: "file", accept: ".pptx,.potx",
    onchange: (e) => { state.templateFile = e.target.files[0] ?? null; refreshStatus(); },
  });
  const sourceInput = el("input", {
    type: "file", accept: ".docx,.pdf,.pptx", multiple: "multiple",
    onchange: (e) => { state.sourceFiles = Array.from(e.target.files); refreshStatus(); },
  });
  const goBtn = el("button", { class: "btn btn--primary", disabled: "disabled", onclick: () => runParse(root) }, "Parse and continue");

  function refreshStatus() {
    const bits = [];
    bits.push(state.templateFile ? `Template: ${state.templateFile.name}` : "No template chosen yet");
    bits.push(state.sourceFiles.length ? `${state.sourceFiles.length} source document(s)` : "No source documents yet");
    status.textContent = bits.join(" · ");
    goBtn.disabled = !state.templateFile || state.sourceFiles.length === 0;
  }
  refreshStatus();

  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "3. Upload"),
      el("p", { class: "panel__lede" }, `Deck type: ${DECK_TYPES[state.deckType].label}. Upload the client's approved template and the source documents this deck should be built from.`),
      el("div", { class: "drop-row" }, [
        dropZone("Slide template", ".pptx or .potx — the client's approved deck", templateInput),
        dropZone("Source documents", ".docx, .pdf or .pptx — as many as you have", sourceInput),
      ]),
      status,
      el("div", { class: "privacy-note" }, [
        "Everything here runs in your browser. Files are never uploaded anywhere — only ",
        el("em", {}, "extracted text"), " is sent to Claude to write the slide content.",
      ]),
      el("div", { class: "panel__actions" }, [
        el("button", { class: "btn", onclick: () => { state.step = "deckType"; render(root); } }, "Back"),
        goBtn,
      ]),
    ])
  );
}

async function runParse(root) {
  state.step = "parsing";
  render(root);
  try {
    const templateBytes = await state.templateFile.arrayBuffer();
    const [corpus, profile] = await Promise.all([
      parseSources(state.sourceFiles),
      profileTemplate(templateBytes),
    ]);
    state.corpus = corpus;
    state.profile = profile;

    if (state.brandRoute === "template") {
      state.brandProfile = brand.fromTemplate(profile, state.brandManualFields.client || "");
    }

    const { assignment, notes } = resolveLayoutRoles(profile);
    state.assignment = assignment;
    state.mappingNotes = notes;
    state.overrides = {};
    state.step = "review";
  } catch (e) {
    state.error = e.message || String(e);
    state.errorCode = null;
    state.errorRetriable = true;
    state.step = "error";
  }
  render(root);
}

function renderParsing(root) {
  root.replaceChildren(
    el("div", { class: "panel panel--center" }, [
      el("div", { class: "spinner" }),
      el("p", {}, "Reading the template and source documents…"),
    ])
  );
}

// ---------------------------------------------------------------------------
// step 4 — review (layout mapping + brand approval)
// ---------------------------------------------------------------------------

function renderReview(root) {
  const { corpus, profile, assignment, mappingNotes } = state;
  const usedRoles = new Set([...DECK_TYPES[state.deckType].required_roles, ...(DECK_TYPES[state.deckType].optional_roles ?? [])]);
  const relevantRoles = ROLES.filter((r) => usedRoles.has(r));

  const mappingTable = el("table", { class: "table" }, [
    el("thead", {}, el("tr", {}, [el("th", {}, "Slide role"), el("th", {}, "Layout"), el("th", {}, "Why")])),
    el("tbody", {}, relevantRoles.map((role) => {
      const current = state.overrides[role] ?? assignment[role]?.part;
      const select = el("select", {
        onchange: (e) => { state.overrides[role] = e.target.value; render(root); },
      }, profile.layouts.map((l) =>
        el("option", { value: l.part, selected: l.part === current ? "selected" : null }, l.name || l.part.split("/").pop())
      ));
      const a = assignment[role];
      return el("tr", {}, [
        el("td", {}, ROLE_LABELS[role]),
        el("td", {}, select),
        el("td", { class: a?.auto ? "muted" : "warn-text" }, a ? a.reason : "no usable layout"),
      ]);
    })),
  ]);

  const outlineRows = corpus.sections.slice(0, 12).map((s) =>
    el("tr", {}, [el("td", { class: "mono muted" }, s.section_id), el("td", {}, s.section_path)])
  );

  const notesBox = mappingNotes.length
    ? el("div", { class: "notice" }, [el("p", { class: "notice__title" }, "⚠ Template notes"), el("ul", {}, mappingNotes.map((n) => el("li", {}, n)))])
    : null;

  const approval = state.brandProfile?.approval ?? {};
  const brandBox = el("div", { class: "notice" }, [
    el("p", { class: "notice__title" }, approval.approved_by ? "Brand approved" : "⚠ Brand not yet approved"),
    approval.approved_by
      ? el("p", {}, `${approval.approved_by} (${approval.role}), ${approval.approved_date}`)
      : el("div", {}, [
          el("p", {}, "A profile with no named approver is a lookalike, not an approved brand. Name one to proceed, or continue without — the deck will build on the template's own defaults only."),
          el("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;" }, [
            el("input", { placeholder: "Approved by", style: "padding:6px 8px;border-radius:6px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);", oninput: (e) => { state.brandApprovedBy = e.target.value; } }),
            el("input", { placeholder: "Role", style: "padding:6px 8px;border-radius:6px;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);", oninput: (e) => { state.brandApprovedRole = e.target.value; } }),
            el("button", { class: "btn small", onclick: () => {
              if (!state.brandApprovedBy || !state.brandApprovedRole) return;
              state.brandProfile.approval = { approved_by: state.brandApprovedBy, role: state.brandApprovedRole, approved_date: new Date().toISOString().slice(0, 10) };
              render(root);
            } }, "Record approval"),
          ]),
        ]),
  ]);

  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "4. Review"),
      el("div", { class: "stats" }, [
        stat(corpus.sections.length, "Sections found"),
        stat(corpus.documents.length, "Source documents"),
        stat(profile.layout_count, "Template layouts"),
        stat(DECK_TYPES[state.deckType].required_roles.length, "Required roles"),
      ]),
      notesBox,
      brandBox,
      el("h3", {}, "Layout mapping — check this before generating"),
      el("p", { class: "panel__lede" }, "Each slide role below will use the layout selected. Change any that look wrong for this template."),
      mappingTable,
      el("h3", {}, "Document outline (first 12 of " + corpus.sections.length + ")"),
      el("div", { class: "table-scroll" }, el("table", { class: "table" }, [
        el("thead", {}, el("tr", {}, [el("th", {}, "id"), el("th", {}, "section")])),
        el("tbody", {}, outlineRows),
      ])),
      el("div", { class: "panel__actions" }, [
        el("button", { class: "btn", onclick: () => { state.step = "upload"; render(root); } }, "Back"),
        el("button", { class: "btn btn--primary", onclick: () => runGenerate(root) }, "Generate deck"),
      ]),
    ])
  );
}

// ---------------------------------------------------------------------------
// step 5 — generate + validate
// ---------------------------------------------------------------------------

const STAGE_LABELS = { brief: "Writing the key messages", plan: "Planning the slides", validating: "Checking fit and provenance", building: "Assembling the .pptx", done: "Done" };

async function runGenerate(root) {
  state.step = "generating";
  state.stage = "brief";
  render(root);

  try {
    const sample = await window.claude?.use?.("sample");
    if (!sample) throw new Error("This view can't reach Claude to write the deck. Open this page directly (not embedded) and try again.");

    const deckType = DECK_TYPES[state.deckType];
    const { brief, plan } = await generateDeckPlan(state.corpus, deckType, {
      sampleJson: (prompt, opts) => sample.json(prompt, opts),
      brand: state.brandProfile,
      onStage: (s) => { state.stage = s; render(root); },
    });
    state.planResult = { brief, plan };

    state.stage = "validating";
    render(root);

    const finalAssignment = { ...state.assignment };
    for (const [role, part] of Object.entries(state.overrides)) {
      const layout = state.profile.layouts.find((l) => l.part === part);
      if (layout) finalAssignment[role] = { part: layout.part, name: layout.name, auto: false, reason: "manually selected" };
    }
    const planValidation = validatePlan(plan, deckType, state.profile, finalAssignment);
    state.planValidation = planValidation;
    state.finalAssignment = finalAssignment;

    if (planValidation.hardFail) {
      state.step = "planReview";
      render(root);
      return;
    }

    await buildAndFinish(root, finalAssignment);
  } catch (e) {
    const code = e?.code;
    const RETRIABLE = new Set(["invalid_json", "upstream_error", "rate_limited", "refused", "empty_completion"]);
    state.error = e.message || String(e);
    state.errorCode = code;
    state.errorRetriable = RETRIABLE.has(code) || !code;
    state.step = "error";
  }
  render(root);
}

async function buildAndFinish(root, finalAssignment) {
  state.stage = "building";
  render(root);

  const assetsByRole = new Map(); // no images generated in v1 — text/table/metric content only
  const built = await buildPptx({
    templateBytes: await state.templateFile.arrayBuffer(),
    profile: state.profile,
    assignment: finalAssignment,
    plan: state.planResult.plan,
    assets: assetsByRole,
  });

  state.result = { built, planValidation: state.planValidation };
  state.step = "done";
}

function renderGenerating(root) {
  root.replaceChildren(
    el("div", { class: "panel panel--center" }, [
      el("div", { class: "spinner" }),
      el("p", {}, (STAGE_LABELS[state.stage] ?? "Working") + "…"),
    ])
  );
}

// ---------------------------------------------------------------------------
// plan review — shown only when validatePlan() hard-fails
// ---------------------------------------------------------------------------

function renderPlanReview(root) {
  const { failures, warnings } = state.planValidation;
  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "Plan needs fixing before it can build"),
      el("p", { class: "panel__lede" }, "The generated plan failed one or more mechanical checks — a template genuinely cannot hold this content as drafted. Retry generation, or go back and adjust the layout mapping."),
      el("div", { class: "notice notice--error" }, [
        el("p", { class: "notice__title" }, `${failures.length} failure(s)`),
        el("ul", {}, failures.map((f) => el("li", {}, `[${f.type}] ${f.message}`))),
      ]),
      warnings.length ? el("div", { class: "notice" }, [el("p", { class: "notice__title" }, `${warnings.length} warning(s)`), el("ul", {}, warnings.map((w) => el("li", {}, `[${w.type}] ${w.message}`)))]) : null,
      el("div", { class: "panel__actions" }, [
        el("button", { class: "btn", onclick: () => { state.step = "review"; render(root); } }, "Back to layout mapping"),
        el("button", { class: "btn btn--primary", onclick: () => runGenerate(root) }, "Regenerate"),
      ]),
    ])
  );
}

// ---------------------------------------------------------------------------
// deliver
// ---------------------------------------------------------------------------

async function handleDownload(filename) {
  const btn = $("#dl-btn");
  const statusEl = $("#dl-status");
  try {
    const downloads = await window.claude?.use?.("downloads");
    if (!downloads) throw new Error("unavailable");
    btn.disabled = true;
    const blob = state.result.built.file instanceof Blob
      ? state.result.built.file
      : new Blob([state.result.built.file], { type: "application/vnd.openxmlformats-officedocument.presentationml.presentation" });
    await downloads.save({ filename, data: blob });
    statusEl.textContent = "Saved — check your downloads.";
    statusEl.className = "dl-status show ok";
  } catch (e) {
    const code = e?.code ?? "unavailable";
    statusEl.textContent = code === "declined" ? "Download cancelled." : `Couldn't save the file (${code}).`;
    statusEl.className = "dl-status show err";
  } finally {
    btn.disabled = false;
  }
}

function renderDone(root) {
  const { built, planValidation } = state.result;
  const filename = `${(state.brandProfile?.client || DECK_TYPES[state.deckType].label).replace(/[^a-z0-9-]+/gi, "-")}-DRAFT.pptx`;
  const warnCount = (planValidation?.warnings?.length ?? 0) + (built.warnings?.length ?? 0);

  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "5. Deliver"),
      el("div", { class: "download-card" }, [
        el("div", { class: "download-card__info" }, [
          el("h3", {}, DECK_TYPES[state.deckType].label),
          el("p", {}, `${built.slideCount} slides · PowerPoint (.pptx)`),
          el("span", { class: `status-pill ${warnCount ? "status-pill--fail" : "status-pill--ok"}` },
            warnCount ? `${warnCount} warning(s) to check` : "Mechanical checks passed"),
        ]),
        el("button", { id: "dl-btn", class: "btn btn--primary", onclick: () => handleDownload(filename) }, "Download deck (.pptx)"),
      ]),
      el("div", { id: "dl-status", class: "dl-status" }),
      (planValidation?.warnings?.length || built.warnings?.length)
        ? el("div", { class: "notice" }, [
            el("p", { class: "notice__title" }, "⚠ Worth checking before handover"),
            el("ul", {}, [...(planValidation?.warnings ?? []).map((w) => `[${w.type}] ${w.message}`), ...(built.warnings ?? [])].slice(0, 10).map((w) => el("li", {}, w))),
          ])
        : null,
      el("p", { class: "muted" }, "First-draft consulting material for practitioner review — not finished content."),
      el("div", { class: "panel__actions" }, [
        el("button", { class: "btn", onclick: () => startOver(root) }, "Build another deck"),
      ]),
    ])
  );
}

function startOver(root) {
  revokeAllUrls();
  Object.assign(state, {
    step: "brand", brandProfile: null, deckType: null, templateFile: null, sourceFiles: [],
    profile: null, assignment: null, overrides: {}, mappingNotes: [], corpus: null, stage: null,
    planResult: null, planValidation: null, result: null, error: null, errorCode: null, errorRetriable: false,
  });
  render(root);
}

// ---------------------------------------------------------------------------
// error step
// ---------------------------------------------------------------------------

function renderError(root) {
  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "Something went wrong"),
      el("div", { class: "notice notice--error" }, state.error ?? "Unknown error."),
      el("div", { class: "panel__actions" }, [
        el("button", { class: "btn", onclick: () => { state.step = "review"; render(root); } }, "Back"),
        state.errorRetriable ? el("button", { class: "btn btn--primary", onclick: () => runGenerate(root) }, "Try again") : null,
      ]),
    ])
  );
}

// ---------------------------------------------------------------------------
// dispatch
// ---------------------------------------------------------------------------

const RENDERERS = {
  brand: renderBrand, deckType: renderDeckType, upload: renderUpload, parsing: renderParsing,
  review: renderReview, generating: renderGenerating, planReview: renderPlanReview,
  done: renderDone, error: renderError,
};

function render(root) {
  (RENDERERS[state.step] ?? renderBrand)(root);
}

export function initApp() {
  const root = document.getElementById("app");
  if (!root) return;
  render(root);
}
