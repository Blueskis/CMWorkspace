/**
 * Assemble a .pptx from a deck plan and an uploaded template.
 *
 * Browser port of the v0.2 Stage 4 path (add_slide.py + inject_slide_xml.py +
 * _build_pptx.py), with one structural change that the platform requires: the v0.2 build
 * carried a hardcoded table mapping module → layout → placeholder names, which only
 * worked because the template was known in advance. Here a slide's blocks name a
 * SEMANTIC SLOT ("body", "picture", "caption"), and the slot is resolved against whatever
 * placeholders the uploaded template's chosen layout actually has.
 *
 * Invariants kept from v0.2, each of which caused a real bug when it was missing:
 *   - all structural work (creating slides) happens before any content edit;
 *   - a picture writes its media part, its relationship and its <p:pic> together, or not
 *     at all, so a deck is never left half-wired;
 *   - pictures are aspect-fitted, never stretched;
 *   - injected diagram shape ids are renumbered above the slide's current maximum;
 *   - the template's own example slides are dropped, rather than kept and appended to.
 *
 * New here: speaker notes are actually written (v0.2 shipped without them and the QA
 * report flagged it), synthesising a notes master when the template lacks one.
 */

import { getJSZip, parseXml } from "./env.js";
import { targetPlaceholders } from "./map-layouts.js";
import { emu, xmlEscape, findAll, attr, resolveTarget } from "./xml.js";
import { renderDiagram } from "./render-diagram.js";

const P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main";
const A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main";
const R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships";

const CONTENT_TYPE_BY_EXT = {
  png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg",
  gif: "image/gif", bmp: "image/bmp", emf: "image/x-emf", wmf: "image/x-wmf",
};

const MINIMAL_SLIDE = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="${A_NS}" xmlns:r="${R_NS}" xmlns:p="${P_NS}"><p:cSld><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`;

// ---------------------------------------------------------------------------
// image helpers
// ---------------------------------------------------------------------------

/** Pixel size from raw bytes — enough formats for what Word/PowerPoint embed. */
export function imagePixelSize(bytes) {
  const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  const dv = new DataView(b.buffer, b.byteOffset, b.byteLength);
  if (b.length > 24 && b[0] === 0x89 && b[1] === 0x50) {
    return { width: dv.getUint32(16), height: dv.getUint32(20) };
  }
  if (b.length > 4 && b[0] === 0xff && b[1] === 0xd8) {
    let i = 2;
    while (i < b.length - 9) {
      if (b[i] !== 0xff) { i++; continue; }
      const marker = b[i + 1];
      if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) { i += 2; continue; }
      const segLen = dv.getUint16(i + 2);
      if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
        return { height: dv.getUint16(i + 5), width: dv.getUint16(i + 7) };
      }
      i += 2 + segLen;
    }
    return null;
  }
  if (b.length > 10 && b[0] === 0x47 && b[1] === 0x49) {
    return { width: dv.getUint16(6, true), height: dv.getUint16(8, true) };
  }
  return null;
}

/** Aspect-fit into a box, centred. Never stretches. */
export function fitExtent([bx, by, bw, bh], px) {
  if (!px || !px.width || !px.height) return [bx, by, bw, bh];
  const imgAspect = px.width / px.height;
  const boxAspect = bw / bh;
  let w, h;
  if (imgAspect > boxAspect) { w = bw; h = bw / imgAspect; }
  else { h = bh; w = bh * imgAspect; }
  return [bx + (bw - w) / 2, by + (bh - h) / 2, w, h];
}

// ---------------------------------------------------------------------------
// shape XML
// ---------------------------------------------------------------------------

function paraXml(text, { bullet = false, align = null, bold = false, sizePt = null } = {}) {
  const alignAttr = align ? ` algn="${align}"` : "";
  const bu = bullet ? '<a:buFont typeface="Arial"/><a:buChar char="&#8226;"/>' : "<a:buNone/>";
  const rPr = `<a:rPr lang="en-US"${bold ? ' b="1"' : ""}${sizePt ? ` sz="${sizePt * 100}"` : ""} dirty="0"/>`;
  return `<a:p><a:pPr${alignAttr}>${bu}</a:pPr><a:r>${rPr}<a:t>${xmlEscape(text)}</a:t></a:r></a:p>`;
}

function textShapeXml(sid, name, ph, geom, paragraphs, anchor = "t") {
  const idxAttr = ph.idx ? ` idx="${ph.idx}"` : "";
  const [x, y, w, h] = geom;
  return `<p:sp>
  <p:nvSpPr><p:cNvPr id="${sid}" name="${xmlEscape(name)}"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
  <p:nvPr><p:ph type="${ph.type}"${idxAttr}/></p:nvPr></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(w)}" cy="${emu(h)}"/></a:xfrm></p:spPr>
  <p:txBody><a:bodyPr wrap="square" anchor="${anchor}"><a:normAutofit/></a:bodyPr><a:lstStyle/>${paragraphs.join("")}</p:txBody>
</p:sp>`;
}

function tableShapeXml(sid, name, geom, headers, rows) {
  const [x, y, w, h] = geom;
  const colW = Math.floor(emu(w) / headers.length);
  const grid = headers.map(() => `<a:gridCol w="${colW}"/>`).join("");
  const cell = (text, header) => {
    const fill = header ? '<a:solidFill><a:schemeClr val="accent1"/></a:solidFill>' : "";
    const color = header ? '<a:solidFill><a:schemeClr val="bg1"/></a:solidFill>' : "";
    return `<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="1200"${header ? ' b="1"' : ""} dirty="0">${color}</a:rPr><a:t>${xmlEscape(text)}</a:t></a:r></a:p></a:txBody><a:tcPr>${fill}</a:tcPr></a:tc>`;
  };
  const headerH = emu(0.4);
  const bodyH = Math.floor((emu(h) - headerH) / Math.max(1, rows.length));
  const trs = [`<a:tr h="${headerH}">${headers.map((c) => cell(c, true)).join("")}</a:tr>`]
    .concat(rows.map((r) => `<a:tr h="${bodyH}">${r.map((c) => cell(c, false)).join("")}</a:tr>`));
  return `<p:graphicFrame>
  <p:nvGraphicFramePr><p:cNvPr id="${sid}" name="${xmlEscape(name)}"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
  <p:xfrm><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(w)}" cy="${emu(h)}"/></p:xfrm>
  <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl>
    <a:tblPr firstRow="1"><a:tableStyleId>{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}</a:tableStyleId></a:tblPr>
    <a:tblGrid>${grid}</a:tblGrid>${trs.join("")}
  </a:tbl></a:graphicData></a:graphic>
</p:graphicFrame>`;
}

function picShapeXml(sid, name, rId, geom, altText) {
  const [x, y, w, h] = geom;
  return `<p:pic>
  <p:nvPicPr><p:cNvPr id="${sid}" name="${xmlEscape(name)}" descr="${xmlEscape(altText ?? "")}"/>
  <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>
  <p:blipFill><a:blip r:embed="${rId}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
  <p:spPr><a:xfrm><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(w)}" cy="${emu(h)}"/></a:xfrm>
  <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
</p:pic>`;
}

const NOTES_MASTER = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notesMaster xmlns:a="${A_NS}" xmlns:r="${R_NS}" xmlns:p="${P_NS}"><p:cSld><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
<p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes Placeholder"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>
<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>
</p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/></p:notesMaster>`;

const notesSlideXml = (text) => `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:notes xmlns:a="${A_NS}" xmlns:r="${R_NS}" xmlns:p="${P_NS}"><p:cSld><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
<p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes Placeholder"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>
<p:txBody><a:bodyPr/><a:lstStyle/>${String(text).split("\n").map((l) => `<a:p><a:r><a:rPr lang="en-US" dirty="0"/><a:t>${xmlEscape(l)}</a:t></a:r></a:p>`).join("")}</p:txBody></p:sp>
</p:spTree></p:cSld></p:notes>`;

// ---------------------------------------------------------------------------
// slot resolution
// ---------------------------------------------------------------------------

/**
 * Resolve a semantic slot to a concrete placeholder + geometry on the chosen layout.
 * Returns null when the layout genuinely cannot host the slot.
 */
function resolveSlot(slot, targets, slideSize) {
  const fullBleed = [0.6, 1.6, slideSize.w_in - 1.2, slideSize.h_in - 2.4];
  const geomOf = (ph, fallback) =>
    ph?.geometry ? [ph.geometry.x_in, ph.geometry.y_in, ph.geometry.w_in, ph.geometry.h_in] : fallback;

  switch (slot) {
    case "title":
      return targets.title
        ? { ph: targets.title, geom: geomOf(targets.title, [0.6, 0.6, slideSize.w_in - 1.2, 1.1]) }
        : null;
    case "subtitle": {
      const ph = targets.subTitle ?? targets.bodies[0];
      return ph ? { ph, geom: geomOf(ph, [0.6, 4.0, slideSize.w_in - 1.2, 1.0]) } : null;
    }
    case "body": {
      const ph = targets.bodies[0];
      return ph ? { ph, geom: geomOf(ph, fullBleed) } : null;
    }
    case "body2": {
      const ph = targets.bodies[1] ?? targets.bodies[0];
      return ph ? { ph, geom: geomOf(ph, fullBleed) } : null;
    }
    case "caption": {
      // On a picture layout the caption is the body slot; skip if there isn't one.
      const ph = targets.bodies[0];
      return ph ? { ph, geom: geomOf(ph, null) } : null;
    }
    case "picture": {
      if (targets.pic) return { ph: targets.pic, geom: geomOf(targets.pic, fullBleed), native: true };
      // Fallback for a template with no picture placeholder: use the body's geometry
      // but emit a free-floating <p:pic> rather than filling a placeholder.
      const ph = targets.bodies[0];
      return ph ? { ph, geom: geomOf(ph, fullBleed), native: false } : { ph: null, geom: fullBleed, native: false };
    }
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// package bookkeeping
// ---------------------------------------------------------------------------

function nextRid(relsXml) {
  let max = 0;
  for (const m of relsXml.matchAll(/Id="rId(\d+)"/g)) max = Math.max(max, parseInt(m[1], 10));
  return `rId${max + 1}`;
}

// [Content_Types].xml's root is conventionally unprefixed (<Types xmlns="...">), but
// nothing requires that — a real uploaded template's XML tooling can just as easily emit
// <ns0:Types>. A literal "</Types>" match then silently finds nothing and String.replace
// no-ops, so every part registered afterward (new slides included) is missing from
// Content_Types and the deck fails validation with no error at build time. Matching the
// closing tag by an optional-prefix pattern, the same local-name-not-prefix principle
// xml.js already applies to reading a template, closes that gap here too.
const CLOSE_TYPES_RE = /<\/(?:[\w.-]+:)?Types>/;

function addOverride(ctXml, partName, contentType) {
  if (ctXml.includes(`PartName="${partName}"`)) return ctXml;
  return ctXml.replace(CLOSE_TYPES_RE, (tag) => `<Override PartName="${partName}" ContentType="${contentType}"/>${tag}`);
}

function ensureDefault(ctXml, ext, contentType) {
  if (new RegExp(`Extension="${ext}"`, "i").test(ctXml)) return ctXml;
  return ctXml.replace(CLOSE_TYPES_RE, (tag) => `<Default Extension="${ext}" ContentType="${contentType}"/>${tag}`);
}

/**
 * Drop media/embeddings/tags parts that no surviving relationship points to any more.
 *
 * Dropping the template's own example slides (step 1) removes their <Override> and
 * <p:sldId> entries, but a real template's example deck often carries its own assets —
 * embedded OLE objects, decorative SVGs, PowerPoint co-authoring "tags" — reachable ONLY
 * from those now-deleted slides. Left behind, they are legal but orphaned OPC parts:
 * validate.py correctly flags every one as "Unreferenced file". Every OOXML reference to
 * a package part goes through a .rels relationship (never a bare path in slide XML), so
 * walking every SURVIVING .rels file's targets and removing anything in these three
 * folders that no relationship still names is a complete, exact sweep — not a heuristic.
 */
async function sweepOrphanedParts(zip, ctXml) {
  const SWEPT_DIRS = ["ppt/media/", "ppt/embeddings/", "ppt/tags/"];
  const referenced = new Set();

  for (const relPath of Object.keys(zip.files)) {
    if (!relPath.endsWith(".rels") || zip.files[relPath].dir) continue;
    const idx = relPath.lastIndexOf("_rels/");
    const sourcePart = relPath.slice(0, idx) + relPath.slice(idx + 6, -".rels".length);
    const doc = await parseXml(await zip.file(relPath).async("string"));
    for (const rel of findAll(doc, "Relationship")) {
      if (attr(rel, "TargetMode") === "External") continue;
      const target = attr(rel, "Target");
      if (target) referenced.add(resolveTarget(target, sourcePart));
    }
  }

  let newCt = ctXml;
  for (const name of Object.keys(zip.files)) {
    if (zip.files[name].dir) continue;
    if (!SWEPT_DIRS.some((d) => name.startsWith(d))) continue;
    if (referenced.has(name)) continue;
    zip.remove(name);
    newCt = newCt.replace(new RegExp(`<Override[^>]*PartName="/${name}"[^>]*/>`, "g"), "");
  }
  return newCt;
}

// ---------------------------------------------------------------------------

/**
 * @param {ArrayBuffer|Uint8Array} templateBytes
 * @param {object} profile      from profileTemplate()
 * @param {object} assignment   from resolveLayoutRoles()
 * @param {object} plan         { modules: [{ slides: [{ role, title, blocks, speaker_notes }] }] }
 * @param {Map<string,{bytes,ext,alt}>} assets  asset_id -> image
 * @returns {Promise<Blob|Uint8Array>} the built .pptx
 */
export async function buildPptx({ templateBytes, profile, assignment, plan, assets = new Map() }) {
  const JSZip = await getJSZip();
  const zip = await JSZip.loadAsync(templateBytes);
  const slideSize = profile.slide_size;
  const warnings = [];

  let ctXml = await zip.file("[Content_Types].xml").async("string");
  let presXml = await zip.file("ppt/presentation.xml").async("string");
  let presRels = await zip.file("ppt/_rels/presentation.xml.rels").async("string");

  // --- 1. drop the template's own example slides -------------------------
  // They are the template's demo content; keeping them would append our deck after
  // somebody else's slides. Remove the sldId entries, the parts, and the overrides.
  for (const part of profile.example_slides ?? []) {
    const file = part.split("/").pop();
    const relMatch = presRels.match(
      new RegExp(`<Relationship[^>]*Id="([^"]+)"[^>]*Target="(?:/ppt/)?slides/${file}"[^>]*/>`)
    );
    if (relMatch) {
      const rid = relMatch[1];
      presXml = presXml.replace(new RegExp(`<p:sldId[^>]*r:id="${rid}"[^>]*/>`, "g"), "");
      presRels = presRels.replace(relMatch[0], "");
    }
    zip.remove(part);
    zip.remove(`ppt/slides/_rels/${file}.rels`);
    ctXml = ctXml.replace(new RegExp(`<Override[^>]*PartName="/${part}"[^>]*/>`, "g"), "");
  }
  if ((profile.example_slides ?? []).length) {
    ctXml = await sweepOrphanedParts(zip, ctXml);
  }

  // --- 2. notes master (synthesised only when the template lacks one) -----
  const hasNotesMaster = Object.keys(zip.files).some((n) => /^ppt\/notesMasters\/notesMaster\d+\.xml$/.test(n));
  let notesMasterRid = null;
  if (!hasNotesMaster) {
    zip.file("ppt/notesMasters/notesMaster1.xml", NOTES_MASTER);
    // A notes master needs its OWN theme part — pointing it at the slide master's
    // theme1.xml trips validate.py's "two masters sharing one theme part" check (the same
    // OOXML rule test/make-template-matrix.py's two-masters.pptx fixture exists to catch,
    // just hit here via the synthesised notes master instead of a second slide master).
    // Slide masters are named slideMasterN.xml (no gaps), so scanning them for the
    // highest N and adding one gives a theme number no existing part can already own.
    let themeNo = 1;
    for (const n of Object.keys(zip.files)) {
      const m = n.match(/^ppt\/slideMasters\/slideMaster(\d+)\.xml$/);
      if (m) themeNo = Math.max(themeNo, parseInt(m[1], 10) + 1);
    }
    const theme1Xml = await zip.file("ppt/theme/theme1.xml").async("string");
    zip.file(`ppt/theme/theme${themeNo}.xml`, theme1Xml);
    ctXml = addOverride(ctXml, `/ppt/theme/theme${themeNo}.xml`,
      "application/vnd.openxmlformats-officedocument.theme+xml");
    zip.file(
      "ppt/notesMasters/_rels/notesMaster1.xml.rels",
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="${REL_NS}"><Relationship Id="rId1" Type="${R_NS}/theme" Target="../theme/theme${themeNo}.xml"/></Relationships>`
    );
    ctXml = addOverride(ctXml, "/ppt/notesMasters/notesMaster1.xml",
      "application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml");
    notesMasterRid = nextRid(presRels);
    presRels = presRels.replace("</Relationships>",
      `<Relationship Id="${notesMasterRid}" Type="${R_NS}/notesMaster" Target="notesMasters/notesMaster1.xml"/></Relationships>`);
    // notesMasterIdLst must sit directly after sldIdLst — PowerPoint refuses a deck whose
    // <p:presentation> children are out of order.
    if (!presXml.includes("<p:notesMasterIdLst>")) {
      presXml = presXml.replace("</p:sldIdLst>",
        `</p:sldIdLst><p:notesMasterIdLst><p:notesMasterId r:id="${notesMasterRid}"/></p:notesMasterIdLst>`);
    }
  } else {
    notesMasterRid = "existing";
  }

  // --- 3. structural pass: create every slide from its layout -------------
  const flatSlides = [];
  for (const mod of [...plan.modules].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))) {
    for (const slide of mod.slides) flatSlides.push({ ...slide, module_id: mod.module_id });
  }

  // <p:sldIdLst> is optional in the OOXML schema — a template built from scratch with no
  // slides ever added can genuinely omit it entirely (see
  // test/fixtures/templates/real-training-template.pptx), not just leave it empty. The
  // per-slide loop below only knows how to APPEND before "</p:sldIdLst>", so without this
  // the whole loop's presXml.replace() calls silently no-op and no slide is ever wired
  // into the deck — the same failure mode notesMasterIdLst already guards against below.
  if (!presXml.includes("<p:sldIdLst>")) {
    presXml = presXml.includes("<p:sldMasterIdLst>")
      ? presXml.replace(/(<\/p:sldMasterIdLst>)/, "$1<p:sldIdLst></p:sldIdLst>")
      : presXml.replace(/(<p:presentation[^>]*>)/, "$1<p:sldIdLst></p:sldIdLst>");
  }

  let slideNo = 0;
  let sldIdSeed = 256;
  for (const m of presXml.matchAll(/<p:sldId id="(\d+)"/g)) {
    sldIdSeed = Math.max(sldIdSeed, parseInt(m[1], 10) + 1);
  }

  const created = [];
  for (const slide of flatSlides) {
    slideNo++;
    const roleAssignment = assignment[slide.role] ?? assignment.content;
    if (!roleAssignment) {
      warnings.push(`${slide.slide_id}: no layout available for role "${slide.role}" — slide skipped`);
      continue;
    }
    const layoutPart = roleAssignment.part;
    const file = `slide${slideNo}.xml`;
    zip.file(`ppt/slides/${file}`, MINIMAL_SLIDE);
    zip.file(
      `ppt/slides/_rels/${file}.rels`,
      `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="${REL_NS}"><Relationship Id="rId1" Type="${R_NS}/slideLayout" Target="../${layoutPart.replace("ppt/", "")}"/></Relationships>`
    );
    ctXml = addOverride(ctXml, `/ppt/slides/${file}`,
      "application/vnd.openxmlformats-officedocument.presentationml.slide+xml");
    const rid = nextRid(presRels);
    presRels = presRels.replace("</Relationships>",
      `<Relationship Id="${rid}" Type="${R_NS}/slide" Target="slides/${file}"/></Relationships>`);
    presXml = presXml.replace("</p:sldIdLst>", `<p:sldId id="${sldIdSeed++}" r:id="${rid}"/></p:sldIdLst>`);
    created.push({ slide, file, layoutPart });
  }

  // --- 4. content pass ----------------------------------------------------
  let mediaSeq = Object.keys(zip.files).filter((n) => n.startsWith("ppt/media/")).length;
  let notesSeq = 0;

  for (const { slide, file, layoutPart } of created) {
    const targets = targetPlaceholders(profile, layoutPart);
    const shapes = [];
    let nextShapeId = 2;
    let slideRels = await zip.file(`ppt/slides/_rels/${file}.rels`).async("string");

    for (const block of slide.blocks ?? []) {
      const resolved = resolveSlot(block.slot, targets, slideSize);
      if (!resolved) {
        warnings.push(`${slide.slide_id}: layout has no "${block.slot}" slot — block dropped`);
        continue;
      }
      const { ph, geom } = resolved;
      const isGap = !!block.gap;
      const isTitle = ph && (ph.type === "title" || ph.type === "ctrTitle");

      if (block.kind === "image" && !isGap) {
        const asset = assets.get(block.content?.asset_id);
        if (!asset) {
          warnings.push(`${slide.slide_id}: asset "${block.content?.asset_id}" not found — block dropped`);
          continue;
        }
        const ext = (asset.ext || "png").toLowerCase();
        const ct = CONTENT_TYPE_BY_EXT[ext];
        if (!ct) {
          warnings.push(`${slide.slide_id}: unsupported image type ".${ext}" — block dropped`);
          continue;
        }
        // media part + relationship + <p:pic>, together or not at all.
        const mediaName = `image${++mediaSeq}.${ext}`;
        zip.file(`ppt/media/${mediaName}`, asset.bytes);
        ctXml = ensureDefault(ctXml, ext, ct);
        const picRid = nextRid(slideRels);
        slideRels = slideRels.replace("</Relationships>",
          `<Relationship Id="${picRid}" Type="${R_NS}/image" Target="../media/${mediaName}"/></Relationships>`);
        const fitted = fitExtent(geom, imagePixelSize(asset.bytes));
        shapes.push(picShapeXml(nextShapeId++, `Picture ${nextShapeId}`, picRid, fitted,
          block.content?.caption ?? asset.alt));
      } else if (block.kind === "diagram" && !isGap) {
        try {
          const { ooxml } = renderDiagram(block.content.diagram_type, block.content.spec, geom, {
            idStart: nextShapeId,
            themeColors: profile.theme_colors,
          });
          // renderDiagram numbers from idStart; advance past everything it used.
          const used = (ooxml.match(/<p:cNvPr id="(\d+)"/g) || [])
            .map((s) => parseInt(s.match(/(\d+)/)[1], 10));
          nextShapeId = Math.max(nextShapeId, ...used) + 1;
          shapes.push(ooxml);
        } catch (e) {
          warnings.push(`${slide.slide_id}: diagram failed (${e.message}) — replaced with a text note`);
          if (ph) {
            shapes.push(textShapeXml(nextShapeId++, "Diagram", ph, geom,
              [paraXml(`[Diagram could not be drawn: ${e.message}]`)]));
          }
        }
      } else if (block.kind === "table" && !isGap) {
        shapes.push(tableShapeXml(nextShapeId++, block.slot, geom,
          block.content.headers, block.content.rows));
      } else {
        const text = isGap ? `[GAP] ${block.gap_note ?? ""}` : block.content;
        const paragraphs =
          Array.isArray(text)
            ? text.map((line) => paraXml(line, { bullet: !isTitle, bold: isTitle }))
            : [paraXml(text, {
                bullet: false,
                bold: isTitle,
                align: ph?.type === "ctrTitle" ? "ctr" : null,
              })];
        if (ph) {
          shapes.push(textShapeXml(nextShapeId++, block.slot, ph, geom, paragraphs,
            ph.type === "ctrTitle" ? "ctr" : "t"));
        }
      }
    }

    let slideXml = MINIMAL_SLIDE.replace("</p:spTree>", `${shapes.join("\n")}</p:spTree>`);

    // speaker notes
    if (slide.speaker_notes && notesMasterRid) {
      const nFile = `notesSlide${++notesSeq}.xml`;
      zip.file(`ppt/notesSlides/${nFile}`, notesSlideXml(slide.speaker_notes));
      const nmTarget = hasNotesMaster
        ? Object.keys(zip.files).find((n) => /^ppt\/notesMasters\/notesMaster\d+\.xml$/.test(n))
        : "ppt/notesMasters/notesMaster1.xml";
      zip.file(
        `ppt/notesSlides/_rels/${nFile}.rels`,
        `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="${REL_NS}">` +
          `<Relationship Id="rId1" Type="${R_NS}/notesMaster" Target="../${nmTarget.replace("ppt/", "")}"/>` +
          `<Relationship Id="rId2" Type="${R_NS}/slide" Target="../slides/${file}"/></Relationships>`
      );
      ctXml = addOverride(ctXml, `/ppt/notesSlides/${nFile}`,
        "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml");
      const nRid = nextRid(slideRels);
      slideRels = slideRels.replace("</Relationships>",
        `<Relationship Id="${nRid}" Type="${R_NS}/notesSlide" Target="../notesSlides/${nFile}"/></Relationships>`);
    }

    zip.file(`ppt/slides/${file}`, slideXml);
    zip.file(`ppt/slides/_rels/${file}.rels`, slideRels);
  }

  zip.file("[Content_Types].xml", ctXml);
  zip.file("ppt/presentation.xml", presXml);
  zip.file("ppt/_rels/presentation.xml.rels", presRels);

  const isNode = typeof process !== "undefined" && process.versions?.node;
  const out = await zip.generateAsync({
    type: isNode ? "uint8array" : "blob",
    mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    compression: "DEFLATE",
  });
  return { file: out, warnings, slideCount: created.length };
}
