"use strict";

/* =================================================================
   Template profiling — a browser port of scripts/profile_template.py's
   .potx/.pptx path. Reads ppt/slideLayouts/*.xml for layouts and their
   placeholders, ppt/theme/theme*.xml for the colour scheme and fonts,
   ppt/presentation.xml for slide size, and checks for a notes master.
   Read-only: this module never writes back into a template.
   ================================================================= */

const NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main";
const NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main";
const NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const EMU_PER_INCH = 914400;

/* Browser code always uses the real DOMParser; Node's test environment
   has none, so it falls back to the minimal shim in xml-shim.js. */
function parseXml(text) {
  if (typeof DOMParser !== "undefined") {
    return new DOMParser().parseFromString(text, "application/xml");
  }
  const { DOMParser: ShimDOMParser } = require("./xml-shim.js");
  return new ShimDOMParser().parseFromString(text, "application/xml");
}

const utf8 = new TextDecoder();
const toText = bytes => utf8.decode(bytes);

function textOfShape(shapeEl) {
  const runs = shapeEl.getElementsByTagNameNS(NS_A, "t");
  const parts = [];
  for (let i = 0; i < runs.length; i++) parts.push(runs[i].textContent || "");
  return parts.join(" ").trim();
}

function geometryOf(shapeEl) {
  const xfrms = shapeEl.getElementsByTagNameNS(NS_A, "xfrm");
  if (!xfrms.length) return null;
  const xfrm = xfrms[0];
  const off = xfrm.getElementsByTagNameNS(NS_A, "off")[0];
  const ext = xfrm.getElementsByTagNameNS(NS_A, "ext")[0];
  if (!off || !ext) return null;
  return {
    xIn: Math.round((Number(off.getAttribute("x") || 0) / EMU_PER_INCH) * 100) / 100,
    yIn: Math.round((Number(off.getAttribute("y") || 0) / EMU_PER_INCH) * 100) / 100,
    wIn: Math.round((Number(ext.getAttribute("cx") || 0) / EMU_PER_INCH) * 100) / 100,
    hIn: Math.round((Number(ext.getAttribute("cy") || 0) / EMU_PER_INCH) * 100) / 100,
  };
}

function profileLayoutXml(xmlText, partName) {
  const doc = parseXml(xmlText);
  const placeholders = [];
  const shapes = doc.getElementsByTagNameNS(NS_P, "sp");

  for (let i = 0; i < shapes.length; i++) {
    const shape = shapes[i];
    const phNodes = shape.getElementsByTagNameNS(NS_P, "ph");
    if (!phNodes.length) continue;
    const ph = phNodes[0];
    const cNvPrNodes = shape.getElementsByTagNameNS(NS_P, "cNvPr");
    const cNvPr = cNvPrNodes[0] || null;
    placeholders.push({
      type: ph.getAttribute("type") || "body",
      idx: ph.getAttribute("idx"),
      name: cNvPr ? cNvPr.getAttribute("name") : null,
      promptText: textOfShape(shape) || null,
      geometry: geometryOf(shape),
    });
  }

  const pics = doc.getElementsByTagNameNS(NS_P, "pic").length;
  const graphics = doc.getElementsByTagNameNS(NS_P, "graphicFrame").length;
  const cSldNodes = doc.getElementsByTagNameNS(NS_P, "cSld");
  const cSld = cSldNodes[0] || null;
  const root = doc.documentElement;

  return {
    part: partName,
    name: cSld ? cSld.getAttribute("name") : null,
    type: root ? root.getAttribute("type") : null,
    placeholderCount: placeholders.length,
    placeholders,
    staticImages: pics,
    graphicFrames: graphics,
  };
}

function profileThemeXml(xmlText) {
  const doc = parseXml(xmlText);
  const scheme = doc.getElementsByTagNameNS(NS_A, "fontScheme")[0] || null;
  let major = null, minor = null;
  if (scheme) {
    const majorFont = scheme.getElementsByTagNameNS(NS_A, "majorFont")[0];
    const minorFont = scheme.getElementsByTagNameNS(NS_A, "minorFont")[0];
    const majorLatin = majorFont && majorFont.getElementsByTagNameNS(NS_A, "latin")[0];
    const minorLatin = minorFont && minorFont.getElementsByTagNameNS(NS_A, "latin")[0];
    major = majorLatin ? majorLatin.getAttribute("typeface") : null;
    minor = minorLatin ? minorLatin.getAttribute("typeface") : null;
  }

  const clrScheme = doc.getElementsByTagNameNS(NS_A, "clrScheme")[0] || null;
  const colors = {};
  if (clrScheme) {
    for (const child of Array.from(clrScheme.childNodes)) {
      if (!child.tagName) continue;
      const localName = child.localName || child.tagName.split(":").pop();
      const srgb = child.getElementsByTagNameNS(NS_A, "srgbClr")[0];
      const sys = child.getElementsByTagNameNS(NS_A, "sysClr")[0];
      const value = srgb ? srgb.getAttribute("val")
        : sys ? sys.getAttribute("lastClr") : null;
      if (value) colors[localName] = "#" + value.toLowerCase();
    }
  }

  return { major, minor, colors };
}

function slideSizeOf(presentationXmlText) {
  const doc = parseXml(presentationXmlText);
  const sz = doc.getElementsByTagNameNS(NS_P, "sldSz")[0] || null;
  if (!sz) return null;
  return {
    wIn: Math.round((Number(sz.getAttribute("cx") || 0) / EMU_PER_INCH) * 100) / 100,
    hIn: Math.round((Number(sz.getAttribute("cy") || 0) / EMU_PER_INCH) * 100) / 100,
  };
}

/* Profile a full .potx/.pptx package already unzipped into a Map of
   part name -> bytes (see unzipAll in ooxml-zip.js). Returns the same
   shape profile_template.py emits, plus theme colours (which the
   Python script doesn't read) and notesSupported. */
function profileTemplate(entriesMap, templateName) {
  const names = [...entriesMap.keys()];
  const layoutNames = names.filter(n => /^ppt\/slideLayouts\/slideLayout\d+\.xml$/.test(n)).sort(
    (a, b) => Number(a.match(/(\d+)/)[1]) - Number(b.match(/(\d+)/)[1])
  );
  const layouts = [];
  const parseErrors = [];
  for (const name of layoutNames) {
    try {
      layouts.push(profileLayoutXml(toText(entriesMap.get(name)), name));
    } catch (err) {
      parseErrors.push({ part: name, message: String(err.message || err) });
    }
  }

  const themeNames = names.filter(n => /^ppt\/theme\/theme\d+\.xml$/.test(n));
  let themeFonts = null, themeColors = null;
  if (themeNames.length) {
    const first = profileThemeXml(toText(entriesMap.get(themeNames[0])));
    themeFonts = { major: first.major, minor: first.minor };
    themeColors = first.colors;
  }

  const presName = names.find(n => n === "ppt/presentation.xml");
  const slideSize = presName ? slideSizeOf(toText(entriesMap.get(presName))) : null;

  const slideCount = names.filter(n => /^ppt\/slides\/slide\d+\.xml$/.test(n)).length;
  const masterCount = names.filter(n => /^ppt\/slideMasters\/slideMaster\d+\.xml$/.test(n)).length;
  const notesSupported = names.some(n => /^ppt\/notesMasters\/notesMaster\d+\.xml$/.test(n));

  const isTemplate = (entriesMap.get("[Content_Types].xml")
    ? toText(entriesMap.get("[Content_Types].xml")).includes("presentationml.template")
    : /\.potx$/i.test(templateName || ""));

  return {
    template: templateName || null,
    kind: isTemplate ? "potx" : "pptx",
    layoutCount: layouts.length,
    masterCount,
    exampleSlideCount: slideCount,
    slideSize,
    themeFonts,
    themeColors,
    notesSupported,
    layouts,
    parseErrors,
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { profileLayoutXml, profileThemeXml, slideSizeOf, profileTemplate };
}
