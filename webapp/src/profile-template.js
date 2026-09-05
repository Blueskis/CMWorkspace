/**
 * Profile an uploaded .pptx/.potx: what layouts exist and what each can hold.
 *
 * Browser port of lib/profile_template.py's pptx path. Same output shape, so a plan
 * validated against a Python-produced profile validates identically against this one.
 *
 * One deliberate difference: element lookups here match on LOCAL name rather than a
 * namespace-prefixed path (see xml.js findAll). Real client templates do not agree on
 * prefixes, and a prefix-sensitive read returns an empty layout list on a perfectly
 * valid template — which would look like "your template has no layouts" to the user.
 */

import { getJSZip, parseXml } from "./env.js";
import { attr, children, findAll, findFirst, geometryOf, textOf, EMU_PER_INCH } from "./xml.js";

const COLOR_SLOTS = [
  "dk1", "lt1", "dk2", "lt2",
  "accent1", "accent2", "accent3", "accent4", "accent5", "accent6",
  "hlink", "folHlink",
];

function slideSizeInches(presentationDoc) {
  const sz = presentationDoc ? findFirst(presentationDoc, "sldSz") : null;
  if (!sz) return { w_in: 13.333, h_in: 7.5 }; // widescreen default
  return {
    w_in: parseInt(attr(sz, "cx") || "0", 10) / EMU_PER_INCH,
    h_in: parseInt(attr(sz, "cy") || "0", 10) / EMU_PER_INCH,
  };
}

function profileLayout(doc, partName) {
  const placeholders = [];
  for (const sp of findAll(doc, "sp")) {
    const ph = findFirst(sp, "ph");
    if (!ph) continue;
    const cNvPr = findFirst(sp, "cNvPr");
    placeholders.push({
      type: attr(ph, "type") || "body",
      idx: attr(ph, "idx"),
      name: cNvPr ? attr(cNvPr, "name") : null,
      prompt_text: textOf(sp, "t").trim() || null,
      geometry: geometryOf(sp),
    });
  }

  const cSld = findFirst(doc, "cSld");
  return {
    part: partName,
    name: cSld ? attr(cSld, "name") : null,
    type: attr(doc.documentElement, "type"),
    placeholder_count: placeholders.length,
    placeholders,
    static_images: findAll(doc, "pic").length,
    graphic_frames: findAll(doc, "graphicFrame").length,
    has_picture_placeholder: placeholders.some((p) => p.type === "pic"),
  };
}

function resolveSchemeColor(slotEl) {
  if (!slotEl) return null;
  const srgb = findFirst(slotEl, "srgbClr");
  if (srgb) return attr(srgb, "val");
  const sys = findFirst(slotEl, "sysClr");
  if (sys) return attr(sys, "lastClr") || attr(sys, "val");
  return null;
}

function profileTheme(doc) {
  const colors = {};
  const scheme = findFirst(doc, "clrScheme");
  if (scheme) {
    for (const slot of COLOR_SLOTS) {
      const el = children(scheme, slot)[0];
      const val = resolveSchemeColor(el);
      if (val) colors[slot] = val;
    }
  }
  const fonts = {};
  const fontScheme = findFirst(doc, "fontScheme");
  if (fontScheme) {
    const major = findFirst(children(fontScheme, "majorFont")[0] ?? fontScheme, "latin");
    const minor = findFirst(children(fontScheme, "minorFont")[0] ?? fontScheme, "latin");
    fonts.major = major ? attr(major, "typeface") : null;
    fonts.minor = minor ? attr(minor, "typeface") : null;
  }
  return { colors, fonts };
}

/**
 * @param {ArrayBuffer|Uint8Array} bytes  the uploaded template file
 * @returns profile object (same shape as lib/profile_template.py's JSON)
 */
export async function profileTemplate(bytes) {
  const JSZip = await getJSZip();
  const zip = await JSZip.loadAsync(bytes);

  const names = Object.keys(zip.files);
  const layoutNames = names
    .filter((n) => /^ppt\/slideLayouts\/slideLayout\d+\.xml$/.test(n))
    .sort((a, b) => {
      const na = parseInt(a.match(/(\d+)\.xml$/)[1], 10);
      const nb = parseInt(b.match(/(\d+)\.xml$/)[1], 10);
      return na - nb;
    });

  if (layoutNames.length === 0) {
    throw new Error(
      "This file has no slide layouts (ppt/slideLayouts/). It may not be a PowerPoint " +
        "template — check you picked a .pptx or .potx."
    );
  }

  const layouts = [];
  for (const name of layoutNames) {
    try {
      layouts.push(profileLayout(await parseXml(await zip.file(name).async("string")), name));
    } catch (e) {
      // Skip a malformed layout rather than failing the whole template: a template with
      // one bad layout is still usable via its others.
      console.warn(`could not parse ${name}: ${e.message}`);
    }
  }

  let theme = { colors: {}, fonts: {} };
  const themeName = names.find((n) => /^ppt\/theme\/theme\d+\.xml$/.test(n));
  if (themeName) {
    try {
      theme = profileTheme(await parseXml(await zip.file(themeName).async("string")));
    } catch { /* a template with an unreadable theme still builds; colours inherit */ }
  }

  let slideSize = { w_in: 13.333, h_in: 7.5 };
  if (zip.file("ppt/presentation.xml")) {
    try {
      slideSize = slideSizeInches(await parseXml(await zip.file("ppt/presentation.xml").async("string")));
    } catch { /* keep the default */ }
  }

  const exampleSlides = names.filter((n) => /^ppt\/slides\/slide\d+\.xml$/.test(n));

  return {
    kind: "pptx",
    layout_count: layouts.length,
    master_count: names.filter((n) => /^ppt\/slideMasters\/slideMaster\d+\.xml$/.test(n)).length,
    example_slide_count: exampleSlides.length,
    example_slides: exampleSlides,
    slide_size: slideSize,
    theme_colors: theme.colors,
    theme_fonts: theme.fonts,
    layouts_with_picture_placeholder: layouts
      .filter((l) => l.has_picture_placeholder)
      .map((l) => l.part),
    layouts,
  };
}
