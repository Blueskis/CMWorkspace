/**
 * The page itself: upload -> parse -> review & confirm mapping -> generate -> deliver.
 *
 * Steps 1-3 and 5 touch only the modules already tested in Node (parse.js,
 * profile-template.js, map-layouts.js, build-pptx.js, qa.js) and spend no Claude usage.
 * Only step 4 calls plan.js's generatePlan(), which is the only thing here that cannot
 * run outside a published artifact — everything it calls into was verified in Node first.
 */

import { parseSources } from "./parse.js";
import { profileTemplate } from "./profile-template.js";
import { resolveLayoutRoles, ROLES, ROLE_LABELS } from "./map-layouts.js";
import { generatePlan } from "./plan.js";
import { buildPptx } from "./build-pptx.js";
import { audit, hardFail, renderReport } from "./qa.js";
import { SAMPLE_TEMPLATE, SAMPLE_FSD } from "./sample-data.js";

/** base64 -> File, for the "use sample files" quick-start (some corporate laptops block
 * the native file picker outright, so this bypasses <input type="file"> entirely, feeding
 * runParse() the exact same File-shaped object it already knows how to consume). */
function fileFromBase64({ filename, mimeType, base64 }) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new File([bytes], filename, { type: mimeType });
}

const QUESTION_COUNT = 5; // fixed by standing instruction — not a user-facing setting

const state = {
  step: "upload",
  templateFile: null,
  sourceFiles: [],
  profile: null,
  assignment: null,
  overrides: {}, // role -> layout part, when the user picks something other than the auto pick
  corpus: null,
  stage: null,
  result: null, // { brief, plan, questions, built, qaResult, qaReport }
  error: null,
  errorCode: null,
  errorStage: null,
  errorRetriable: false,
  errorReplyText: null, // the raw reply text from a failed sample.json() call, when any streamed
  generationResume: null, // { brief?, moduleSkeletons?, modules?, questions? } from a failed run's e.progress
  objectUrls: [],
};

function $(sel, root = document) {
  return root.querySelector(sel);
}
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

// ---------------------------------------------------------------------------
// step 1 — upload
// ---------------------------------------------------------------------------

function renderUpload(root) {
  const status = el("p", { class: "upload-status" });

  const refreshStatus = () => {
    const bits = [];
    bits.push(state.templateFile ? `Template: ${state.templateFile.name}` : "No template chosen yet");
    bits.push(
      state.sourceFiles.length
        ? `${state.sourceFiles.length} source document${state.sourceFiles.length > 1 ? "s" : ""}: ${state.sourceFiles.map((f) => f.name).join(", ")}`
        : "No source documents chosen yet"
    );
    status.textContent = bits.join("  ·  ");
    goBtn.disabled = !state.templateFile || state.sourceFiles.length === 0;
  };

  const templateInput = el("input", {
    type: "file", accept: ".pptx,.potx",
    onchange: (e) => { state.templateFile = e.target.files[0] ?? null; refreshStatus(); },
  });
  const sourceInput = el("input", {
    type: "file", accept: ".docx,.pptx,.pdf", multiple: "multiple",
    onchange: (e) => { state.sourceFiles = Array.from(e.target.files); refreshStatus(); },
  });

  const dropZone = (label, hint, input) =>
    el("label", { class: "drop-zone" }, [
      el("span", { class: "drop-zone__label" }, label),
      el("span", { class: "drop-zone__hint" }, hint),
      input,
    ]);

  const goBtn = el("button", { class: "btn btn--primary", disabled: "disabled", onclick: () => runParse(root) }, "Parse documents");

  const useSamples = SAMPLE_TEMPLATE.base64 && SAMPLE_FSD.base64
    ? el("div", { class: "notice" }, [
        el("p", { class: "notice__title" }, "Can't upload files here?"),
        el("p", {},
          `If your device blocks the file picker, use the sample template ` +
          `(${SAMPLE_TEMPLATE.filename}) and FSD (${SAMPLE_FSD.filename}) already ` +
          `loaded into this page instead.`),
        el("button", {
          class: "btn",
          onclick: () => {
            state.templateFile = fileFromBase64(SAMPLE_TEMPLATE);
            state.sourceFiles = [fileFromBase64(SAMPLE_FSD)];
            refreshStatus();
          },
        }, "Use the sample files"),
      ])
    : null;

  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "1. Upload"),
      el("p", { class: "panel__lede" },
        "Everything here runs in your browser. Files are never uploaded anywhere — only " +
        "the text extracted from your source documents is sent to Claude, in the next step, " +
        "to write the slide content. Screenshots and the template itself are never sent."),
      el("div", { class: "drop-row" }, [
        dropZone("Slide template", ".pptx or .potx — the client's approved deck", templateInput),
        dropZone("Source documents", ".docx, .pptx or .pdf — the FSD and anything else", sourceInput),
      ]),
      status,
      useSamples,
      el("div", { class: "panel__actions" }, [goBtn]),
    ])
  );
  refreshStatus();
}

// ---------------------------------------------------------------------------
// step 2 — parsing (transient)
// ---------------------------------------------------------------------------

async function runParse(root) {
  state.step = "parsing";
  render(root);
  try {
    const [profile, corpus] = await Promise.all([
      profileTemplate(await state.templateFile.arrayBuffer()),
      parseSources(state.sourceFiles),
    ]);
    state.profile = profile;
    state.corpus = corpus;
    const { assignment, notes, pictureFallback } = resolveLayoutRoles(profile);
    state.assignment = assignment;
    state.mappingNotes = notes;
    state.pictureFallback = pictureFallback;
    state.step = "review";
  } catch (e) {
    state.error = e.message || String(e);
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
// step 3 — review & confirm
// ---------------------------------------------------------------------------

function classifierCounts(sections) {
  const counts = {};
  sections.forEach((s) => { counts[s.classifier] = (counts[s.classifier] ?? 0) + 1; });
  return counts;
}

function renderReview(root) {
  const { corpus, profile, assignment, mappingNotes, pictureFallback } = state;
  const counts = classifierCounts(corpus.sections);
  const screenshots = corpus.assets.filter((a) => a.role === "screenshot");

  const mappingTable = el("table", { class: "table" }, [
    el("thead", {}, el("tr", {}, [el("th", {}, "Slide role"), el("th", {}, "Layout"), el("th", {}, "Why")])),
    el("tbody", {}, ROLES.map((role) => {
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
    el("tr", {}, [
      el("td", { class: "mono muted" }, s.section_id),
      el("td", {}, s.section_path),
      el("td", {}, el("span", { class: `pill pill--${s.classifier}` }, s.classifier)),
    ])
  );

  const thumbs = screenshots.slice(0, 8).map((a) => {
    const blob = new Blob([a.bytes], { type: `image/${a.format === "jpg" ? "jpeg" : a.format}` });
    return el("figure", { class: "thumb" }, [
      el("img", { src: trackUrl(blob), alt: a.caption_candidate ?? a.nearest_heading ?? "" }),
      el("figcaption", {}, a.caption_candidate ?? a.nearest_heading ?? a.asset_id),
    ]);
  });

  const notesBox = mappingNotes.length
    ? el("div", { class: "notice" }, [
        el("p", { class: "notice__title" }, "⚠ Template notes"),
        el("ul", {}, mappingNotes.map((n) => el("li", {}, n))),
      ])
    : null;

  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "2. Review"),
      el("div", { class: "stats" }, [
        stat(corpus.sections.length, "Sections found"),
        stat(counts.procedure ?? 0, "Procedures"),
        stat(screenshots.length, "Screenshots"),
        stat(profile.layout_count, "Template layouts"),
      ]),
      notesBox,
      el("h3", {}, "Layout mapping — check this before generating"),
      el("p", { class: "panel__lede" }, "Each slide role below will use the layout selected. Change any that look wrong for this template."),
      mappingTable,
      el("h3", {}, "Document outline (first 12 of " + corpus.sections.length + ")"),
      el("div", { class: "table-scroll" }, el("table", { class: "table" }, [
        el("thead", {}, el("tr", {}, [el("th", {}, "id"), el("th", {}, "section"), el("th", {}, "type")])),
        el("tbody", {}, outlineRows),
      ])),
      screenshots.length ? el("h3", {}, `Screenshots found (${screenshots.length})`) : null,
      screenshots.length ? el("div", { class: "thumb-grid" }, thumbs) : null,
      el("div", { class: "panel__actions" }, [
        el("button", { class: "btn", onclick: () => { state.step = "upload"; render(root); } }, "Back"),
        el("button", { class: "btn btn--primary", onclick: () => runGenerate(root) },
          `Generate deck (${QUESTION_COUNT} knowledge-check questions)`),
      ]),
    ])
  );
}

function stat(value, label) {
  return el("div", { class: "stat" }, [el("b", {}, String(value)), el("span", {}, label)]);
}

// ---------------------------------------------------------------------------
// step 4 — generate (transient, spends Claude usage)
// ---------------------------------------------------------------------------

const STAGE_LABELS = {
  brief: "Writing the training brief",
  "module-plan": "Planning modules and slides",
  "slide-copy": "Writing slide content",
  questions: "Writing knowledge-check questions",
  building: "Assembling the .pptx",
  done: "Done",
};

async function runGenerate(root) {
  state.step = "generating";
  state.stage = "brief";
  render(root);

  try {
    const sample = await window.claude?.use?.("sample");
    if (!sample) {
      throw new Error(
        "This view can't reach Claude to write the deck. Open this page directly " +
          "(not embedded) and try again."
      );
    }

    const { brief, plan, questions } = await generatePlan(state.corpus, {
      sampleJson: (prompt, opts) => sample.json(prompt, opts),
      questionCount: QUESTION_COUNT,
      onStage: (s) => { state.stage = s; render(root); },
      resume: state.generationResume ?? {},
    });
    state.generationResume = null; // fully succeeded — nothing left to resume from

    state.stage = "building";
    render(root);

    const finalAssignment = { ...state.assignment };
    for (const [role, part] of Object.entries(state.overrides)) {
      const layout = state.profile.layouts.find((l) => l.part === part);
      if (layout) finalAssignment[role] = { part: layout.part, name: layout.name, auto: false, reason: "manually selected" };
    }

    const assetsByRole = new Map(
      state.corpus.assets.map((a) => [a.asset_id, { bytes: a.bytes, ext: a.ext, alt: a.caption_candidate }])
    );

    const built = await buildPptx({
      templateBytes: await state.templateFile.arrayBuffer(),
      profile: state.profile,
      assignment: finalAssignment,
      plan,
      assets: assetsByRole,
    });

    const qaResult = audit(brief, plan, state.corpus, questions);
    const qaReport = renderReport(qaResult, plan.run_id);

    state.result = { brief, plan, questions, built, qaResult, qaReport };
    state.stage = "done";
    state.step = "done";
  } catch (e) {
    // sample()/sample.json() reject a {code, message, text?} object, never a plain Error
    // — branch on .code, per its own contract, not on .message. A viewer-initiated retry
    // (never an automatic one — the platform is explicit that invalid_json in particular
    // must not be retried from code) is worth offering for the error classes the spec
    // itself calls retriable; state.corpus/profile/assignment are untouched by a failed
    // runGenerate(), so retrying re-enters here directly without re-uploading anything.
    const code = e?.code;
    const RETRIABLE = new Set(["invalid_json", "upstream_error", "rate_limited", "refused", "empty_completion"]);
    state.error = e.message || String(e);
    state.errorCode = code;
    state.errorStage = state.stage; // which of brief/module-plan/slide-copy/questions/building was in flight
    state.errorRetriable = RETRIABLE.has(code);
    state.errorReplyText = typeof e?.text === "string" ? e.text : null;
    // generatePlan() attaches whatever it had already completed to e.progress before
    // throwing — carry it forward so "Try again" resumes past the stages (and, within
    // slide-copy, the individual modules) that already succeeded, instead of re-asking
    // Claude for them again identically.
    state.generationResume = e?.progress ?? state.generationResume ?? null;
    state.step = "error";
  }
  render(root);
}

function renderGenerating(root) {
  const order = ["brief", "module-plan", "slide-copy", "questions", "building"];
  const currentIdx = order.indexOf(state.stage);
  root.replaceChildren(
    el("div", { class: "panel panel--center" }, [
      el("div", { class: "spinner" }),
      el("ol", { class: "stage-list" }, order.map((s, i) =>
        el("li", { class: i < currentIdx ? "done" : i === currentIdx ? "active" : "" }, STAGE_LABELS[s])
      )),
      el("p", { class: "muted" }, "The first step asks your permission to talk to Claude — accept it to continue."),
    ])
  );
}

// ---------------------------------------------------------------------------
// step 5 — deliver
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
  const { qaResult, qaReport, built, plan } = state.result;
  const fail = hardFail(qaResult);
  const filename = `${(state.corpus.documents[0]?.document_id ?? "training").replace(/[^a-z0-9-]+/gi, "-")}-DRAFT.pptx`;

  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "3. Deliver"),
      el("div", { class: "download-card" }, [
        el("div", { class: "download-card__info" }, [
          el("h3", {}, "Training deck"),
          el("p", {}, `${built.slideCount} slides · PowerPoint (.pptx)`),
          el("span", { class: `status-pill ${fail ? "status-pill--fail" : "status-pill--ok"}` },
            fail ? "QA: needs attention" : "QA: mechanical checks passed"),
        ]),
        el("button", { id: "dl-btn", class: "btn btn--primary", onclick: () => handleDownload(filename) }, "Download deck (.pptx)"),
      ]),
      el("div", { id: "dl-status", class: "dl-status" }),
      built.warnings?.length
        ? el("div", { class: "notice" }, [
            el("p", { class: "notice__title" }, "⚠ Build warnings"),
            el("ul", {}, built.warnings.slice(0, 8).map((w) => el("li", {}, w))),
          ])
        : null,
      el("h3", {}, "QA report"),
      el("pre", { class: "qa-report" }, qaReport),
      el("div", { class: "panel__actions" }, [
        el("button", { class: "btn", onclick: () => startOver(root) }, "Generate another deck"),
      ]),
    ])
  );
}

function startOver(root) {
  revokeAllUrls();
  Object.assign(state, {
    step: "upload", templateFile: null, sourceFiles: [], profile: null, assignment: null,
    overrides: {}, corpus: null, stage: null, result: null, error: null,
    errorCode: null, errorStage: null, errorRetriable: false, errorReplyText: null,
    generationResume: null,
  });
  render(root);
}

// ---------------------------------------------------------------------------
// error step
// ---------------------------------------------------------------------------

// Copy for the error classes the sample() contract calls out by name — everything else
// falls back to the raw message. Matches sample.d.ts's own grouping: retriable-with-a-
// button, permanent/hide-the-feature, or "tell the viewer, they may try again later".
const ERROR_COPY = {
  invalid_json: "Claude's reply for this step didn't come back as usable data. This isn't " +
    "cached, so trying again usually works — if it keeps happening, the source content " +
    "for this step may be unusually large or unusual in a way worth reporting.",
  upstream_error: "A temporary issue reaching Claude. This one usually clears up on retry.",
  rate_limited: "Too many requests right now (yours or Claude's usage limit). Wait a moment before trying again.",
  refused: "Claude declined to continue with this content. Retrying with the same input will likely give the same result.",
  empty_completion: "Claude's reply for this step came back empty. Try again, or check the source documents parsed as expected.",
  not_granted: "This page doesn't have permission to use Claude in this view — generation isn't available here.",
  sampling_disabled: "Claude isn't available for this account or organisation in this view.",
  session_expired: "Your session needs to be refreshed — reload the page and try again.",
};

function renderError(root) {
  const copy = ERROR_COPY[state.errorCode];
  const stageLabel = STAGE_LABELS[state.errorStage];
  const resumedStages = Object.entries(state.generationResume ?? {})
    .filter(([, v]) => v != null && (!Array.isArray(v) || v.length > 0))
    .map(([k]) => k);
  root.replaceChildren(
    el("div", { class: "panel" }, [
      el("h2", {}, "Something went wrong"),
      el("div", { class: "notice notice--error" }, [
        stageLabel ? el("p", { class: "mono muted" }, `Failed at: ${stageLabel}`) : null,
        el("p", {}, state.error),
        copy ? el("p", { class: "muted" }, copy) : null,
        state.errorRetriable && resumedStages.length
          ? el("p", { class: "muted" }, "Trying again will resume from here — earlier steps that already succeeded won't be re-asked.")
          : null,
        state.errorReplyText
          ? el("div", {}, [
              el("p", { class: "muted" }, "Claude's raw reply:"),
              el("pre", { class: "qa-report" }, state.errorReplyText.slice(0, 600)
                + (state.errorReplyText.length > 600 ? "…" : "")),
            ])
          : null,
      ]),
      el("div", { class: "panel__actions" }, [
        state.errorRetriable && state.corpus
          ? el("button", { class: "btn btn--primary", onclick: () => { state.error = null; state.errorCode = null; runGenerate(root); } }, "Try again")
          : null,
        el("button", { class: state.errorRetriable && state.corpus ? "btn" : "btn btn--primary", onclick: () => startOver(root) }, "Start over"),
      ]),
    ])
  );
}

// ---------------------------------------------------------------------------

function render(root) {
  const renderers = {
    upload: renderUpload, parsing: renderParsing, review: renderReview,
    generating: renderGenerating, done: renderDone, error: renderError,
  };
  renderers[state.step](root);
}

export function initApp() {
  const root = document.getElementById("app");
  if (!root) return;
  render(root);
}
