/**
 * Brand profile: load, adapt, validate — the JS twin of lib/brand_profile.py, kept in the
 * same canonical shape (lib/schemas/brand_profile.schema.json) so a profile built in the
 * browser (this file) and one built by the Python skill are interchangeable. See that
 * schema's own description for why two prior shapes had to be reconciled into this one.
 *
 * Three intake routes, matching the Python side exactly:
 *   - fromVault(vaultExport)      — the Brand Vault artifact's export JSON
 *   - fromTemplate(profile, client) — a .potx/.pptx's own theme, via profile-template.js's
 *     theme_colors/theme_fonts (NOT lib/profile_template.py's Python output — this reads
 *     the shape profileTemplate() in this same lib/deck/ produces)
 *   - manual(fields)              — typed in by hand, for a client with no template yet
 *     and no Brand Vault export to hand
 *
 * None of the three ever invents an `approval` block — a profile with it empty is treated
 * as no profile at all, same stop condition as the Python side.
 */

function hex(v) {
  if (!v) return null;
  const h = v.startsWith("#") ? v : "#" + v;
  return h.toUpperCase();
}

function colour(hexValue, name) {
  if (!hexValue) return null;
  const c = { hex: hex(hexValue) };
  if (name) c.name = name;
  return c;
}

function prune(obj, keep = new Set(["approval"])) {
  if (Array.isArray(obj)) return obj.map((v) => prune(v, keep));
  if (obj && typeof obj === "object") {
    const out = {};
    for (const [k, v] of Object.entries(obj)) {
      const p = prune(v, keep);
      if (keep.has(k) || !(p == null || (typeof p === "object" && Object.keys(p).length === 0) || p === "")) {
        out[k] = p;
      }
    }
    return out;
  }
  return obj;
}

export function fromVault(vault) {
  const colors = vault.colors ?? {};
  const typ = vault.typography ?? {};
  const logo = vault.logo ?? {};
  const voice = vault.voice ?? {};
  const messaging = vault.messaging ?? {};
  const meta = vault.meta ?? {};

  const role = (key) => {
    const v = colors[key];
    if (v && typeof v === "object") return colour(v.hex, v.note);
    return colour(v);
  };

  const personMap = { 1: "first", 2: "second", 3: "third" };
  const formality = typeof voice.formality === "number"
    ? (voice.formality >= 4 ? "formal" : voice.formality <= 2 ? "informal" : "neutral")
    : (voice.formality ?? "neutral");

  const profile = {
    client: meta.name ?? "",
    source: "client-supplied-guidelines",
    x_source_schema: "brand-vault-v1",
    approval: {},
    palette: {
      primary: role("primary"), secondary: role("secondary"), accent: role("accent"),
      ink: role("ink"), muted: role("muted"), canvas: role("background"), panel: role("surface"),
    },
    typography: {
      heading: { family: typ.headingFont ?? "", fallbacks: typ.headingFallback ? [typ.headingFallback] : [], weight: typ.headingWeight },
      body: { family: typ.bodyFont ?? "", fallbacks: typ.bodyFallback ? [typ.bodyFallback] : [], weight: typ.bodyWeight },
    },
    logo: { dataUri: logo.dataUri, variant: logo.variant, clear_space: logo.clearSpace, min_width_px: logo.minWidthPx },
    tone: {
      voice: voice.toneDescriptors ?? [], person: personMap[voice.person] ?? "third", formality,
      banned_words: voice.bannedVocabulary ?? [],
      preferred_terms: Object.fromEntries((voice.preferredVocabulary ?? []).map((t) => [t, t])),
    },
    messaging: {
      tagline: messaging.tagline ?? "", one_liner: messaging.oneLiner ?? "", boilerplate: messaging.boilerplate ?? "",
      proof_points: messaging.proofPoints ?? [], terminology: messaging.terminology ?? [],
    },
  };
  if (voice.rewriteExample) profile.tone.rewrite_example = voice.rewriteExample;
  return prune(profile);
}

function luminance(hex6) {
  const h = hex6.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const [lr, lg, lb] = [lin(r), lin(g), lin(b)];
  return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb;
}

export function contrastRatio(hexA, hexB) {
  const [la, lb] = [luminance(hexA), luminance(hexB)];
  const [lighter, darker] = la > lb ? [la, lb] : [lb, la];
  return (lighter + 0.05) / (darker + 0.05);
}

/** profile: profileTemplate()'s output (lib/deck/profile-template.js), NOT the Python profiler's. */
export function fromTemplate(profile, client = "") {
  // profile-template.js's own output shape: theme_colors/theme_fonts are flat objects
  // already (dk1/lt1/accent1.../major/minor), unlike lib/profile_template.py's Python
  // profiler, which keys them by theme part name — that divergence is documented in
  // lib/deck/cli/profile.mjs's own header; this function only ever reads the JS shape.
  const themeColors = profile.theme_colors;
  const themeFonts = profile.theme_fonts ?? {};
  if (!themeColors) throw new Error("fromTemplate: no theme_colors in this template's profile");

  let dk = themeColors.dk2 ?? themeColors.dk1;
  let lt = themeColors.lt1 ?? themeColors.lt2;
  if (themeColors.dk1 && themeColors.dk2) {
    dk = luminance(hex(themeColors.dk1)) < luminance(hex(themeColors.dk2)) ? themeColors.dk1 : themeColors.dk2;
  }
  if (themeColors.lt1 && themeColors.lt2) {
    lt = luminance(hex(themeColors.lt1)) > luminance(hex(themeColors.lt2)) ? themeColors.lt1 : themeColors.lt2;
  }

  return prune({
    client, source: "extracted-from-template", x_source_schema: "canonical", approval: {},
    palette: {
      primary: colour(themeColors.accent1), secondary: colour(themeColors.accent2),
      accent: colour(themeColors.accent3), ink: colour(dk), canvas: colour(lt),
    },
    typography: { heading: { family: themeFonts.major ?? "" }, body: { family: themeFonts.minor ?? "" } },
    tone: { voice: [], person: "third" },
  });
}

/** fields: {client, primary, secondary, accent, ink, canvas, headingFont, bodyFont} — all hex/strings, typed by hand. */
export function manual(fields) {
  return prune({
    client: fields.client ?? "", source: "practitioner-authored-from-approved-materials",
    x_source_schema: "canonical", approval: {},
    palette: {
      primary: colour(fields.primary), secondary: colour(fields.secondary), accent: colour(fields.accent),
      ink: colour(fields.ink), canvas: colour(fields.canvas),
    },
    typography: { heading: { family: fields.headingFont ?? "" }, body: { family: fields.bodyFont ?? "" } },
    tone: { voice: [], person: "third" },
  });
}

export function validate(profile) {
  const errors = [];
  for (const req of ["client", "source", "approval", "palette", "typography", "tone"]) {
    if (!(req in profile)) errors.push(`missing required top-level key '${req}'`);
  }
  const approval = profile.approval ?? {};
  if (!approval.approved_by || !approval.role || !approval.approved_date) {
    errors.push("approval.approved_by / role / approved_date not all set — a profile with no named approver is treated as no profile at all");
  }
  const hexRe = /^#?[0-9a-fA-F]{6}$/;
  for (const [role, c] of Object.entries(profile.palette ?? {})) {
    if (c && !hexRe.test(c.hex ?? "")) errors.push(`palette.${role}.hex is not a 6-digit hex colour: ${c.hex}`);
  }
  return errors;
}

export function checkContrast(profile, minRatio) {
  const palette = profile.palette ?? {};
  const min = minRatio ?? profile.accessibility?.min_contrast_ratio ?? 4.5;
  const ink = palette.ink?.hex;
  const canvas = palette.canvas?.hex;
  if (!ink || !canvas) return [];
  const ratio = contrastRatio(ink, canvas);
  return ratio < min ? [{ pair: "ink/canvas", ink, canvas, ratio: +ratio.toFixed(2), min }] : [];
}
