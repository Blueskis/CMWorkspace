"use strict";

/* =================================================================
   The OOXML writer build_deck.py deliberately stops short of
   (scripts/build_deck.py:6-19): given a profiled template and a
   slide plan, replace its example slides with generated ones.

   Every emitted shape is placeholder-only — no explicit geometry,
   font, or colour — so everything inherits from the layout and
   theme the uploaded template already defines. That is what keeps
   `rules.respect_theme_fonts` in template_map.example.json true of
   output this writer produces, not just of the source template.
   ================================================================= */

const SLD_NS = ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
  + ' xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
  + ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"';

const REL_NS = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"';

const CT_SLIDE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml";
const CT_NOTES = "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml";
const REL_TYPE_SLIDE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide";
const REL_TYPE_LAYOUT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout";
const REL_TYPE_NOTES = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide";
const REL_TYPE_NOTES_MASTER = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster";

const utf8Encode = s => new TextEncoder().encode(s);

function xmlEscape(s) {
  return String(s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

/* --- slide XML ---------------------------------------------------- */

function buildParagraph(text, level) {
  const lvl = level ? ` lvl="${level}"` : "";
  const runs = text === "" ? "" : `<a:r><a:t>${xmlEscape(text)}</a:t></a:r>`;
  return `<a:p><a:pPr${lvl}/>${runs}</a:p>`;
}

function buildPlaceholderShape(shapeId, phSpec, paragraphs) {
  const idxAttr = phSpec.idx != null ? ` idx="${xmlEscape(phSpec.idx)}"` : "";
  const typeAttr = phSpec.type ? ` type="${xmlEscape(phSpec.type)}"` : "";
  const body = (paragraphs && paragraphs.length ? paragraphs : [{ text: "", level: 0 }])
    .map(p => buildParagraph(p.text || "", p.level || 0)).join("");
  return `<p:sp><p:nvSpPr><p:cNvPr id="${shapeId}" name="Placeholder ${shapeId}"/>`
    + `<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>`
    + `<p:nvPr><p:ph${typeAttr}${idxAttr}/></p:nvPr></p:nvSpPr>`
    + `<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>${body}</p:txBody></p:sp>`;
}

function buildSlideXml(resolvedShapes) {
  let shapeId = 2;
  const shapes = resolvedShapes.map(s => buildPlaceholderShape(shapeId++, s.phSpec, s.paragraphs)).join("");
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n`
    + `<p:sld${SLD_NS}><p:cSld><p:spTree>`
    + `<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>`
    + `${shapes}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`;
}

function buildSlideRelsXml(layoutTarget, notesTarget) {
  const rels = [`<Relationship Id="rId1" Type="${REL_TYPE_LAYOUT}" Target="${xmlEscape(layoutTarget)}"/>`];
  if (notesTarget) {
    rels.push(`<Relationship Id="rId2" Type="${REL_TYPE_NOTES}" Target="${xmlEscape(notesTarget)}"/>`);
  }
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n`
    + `<Relationships ${REL_NS}>${rels.join("")}</Relationships>`;
}

function buildNotesSlideXml(text) {
  const paragraphs = String(text || "").split(/\n+/).filter(Boolean).map(t => buildParagraph(t, 0)).join("")
    || buildParagraph("", 0);
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n`
    + `<p:notes${SLD_NS}><p:cSld><p:spTree>`
    + `<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>`
    + `<p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes Placeholder"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>`
    + `<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>`
    + `<p:txBody><a:bodyPr/><a:lstStyle/>${paragraphs}</p:txBody></p:sp>`
    + `</p:spTree></p:cSld></p:notes>`;
}

function buildNotesSlideRelsXml(notesMasterTarget) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n`
    + `<Relationships ${REL_NS}><Relationship Id="rId1" Type="${REL_TYPE_NOTES_MASTER}" `
    + `Target="${xmlEscape(notesMasterTarget)}"/></Relationships>`;
}

/* --- placeholder resolution ---------------------------------------
   A slide spec's shape names the placeholder it wants by idx, name,
   or type — whichever the caller has to hand (a plan block usually
   knows a name; the writer's own tests use type). idx is the most
   specific match, then name, then type. No match is a hard failure:
   emitting a shape with no `p:ph` would silently stop inheriting
   from the layout, which is worse than refusing to build. */
function resolvePlaceholder(layoutPlaceholders, want) {
  if (want.idx != null) {
    const hit = layoutPlaceholders.find(p => String(p.idx) === String(want.idx));
    if (hit) return hit;
  }
  if (want.name) {
    const hit = layoutPlaceholders.find(p => (p.name || "").toLowerCase() === want.name.toLowerCase());
    if (hit) return hit;
  }
  if (want.type) {
    const hit = layoutPlaceholders.find(p => p.type === want.type);
    if (hit) return hit;
  }
  return null;
}

/* --- content-types / rels / presentation.xml patching --------------
   Small, targeted string edits rather than a general XML writer: the
   parts being edited are machine-generated by PowerPoint (or by this
   same writer on a prior run) in a known, consistent shape, so a
   general-purpose serializer would add risk without adding
   correctness. Nothing here touches shape or theme content. */

function stripOverridesFor(contentTypesXml, prefix) {
  // [^>]*? (not [^/]*) — a ContentType value like ".../slide+xml" contains
  // its own "/" characters, which a slash-excluding class would stop at.
  const re = new RegExp(`<Override PartName="${prefix.replace(/\//g, "\\/")}[^"]*"[^>]*?/>`, "g");
  return contentTypesXml.replace(re, "");
}

function addOverrides(contentTypesXml, overrides) {
  const additions = overrides.map(o => `<Override PartName="${o.part}" ContentType="${o.contentType}"/>`).join("");
  return contentTypesXml.replace("</Types>", `${additions}</Types>`);
}

function swapTemplateContentType(contentTypesXml) {
  return contentTypesXml.replace(
    /(<Override PartName="\/ppt\/presentation\.xml" ContentType=")[^"]*(")/,
    "$1application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml$2"
  );
}

function stripSlideRelationships(relsXml) {
  // Target="slides/slideN.xml" contains its own "/", so the trailing match
  // must stop at ">" (never present inside an attribute value here), not "/".
  return relsXml.replace(
    new RegExp(`<Relationship [^>]*Type="${REL_TYPE_SLIDE.replace(/\//g, "\\/")}"[^>]*?/>`, "g"),
    ""
  );
}

function maxRelId(relsXml) {
  let max = 0;
  const re = /Id="rId(\d+)"/g;
  let m;
  while ((m = re.exec(relsXml))) max = Math.max(max, Number(m[1]));
  return max;
}

function addRelationships(relsXml, rels) {
  const additions = rels.map(r => `<Relationship Id="${r.id}" Type="${r.type}" Target="${r.target}"/>`).join("");
  return relsXml.replace("</Relationships>", `${additions}</Relationships>`);
}

function replaceSldIdLst(presentationXml, sldIdEntries) {
  const block = `<p:sldIdLst>${sldIdEntries.join("")}</p:sldIdLst>`;
  if (/<p:sldIdLst>[\s\S]*?<\/p:sldIdLst>/.test(presentationXml)) {
    return presentationXml.replace(/<p:sldIdLst>[\s\S]*?<\/p:sldIdLst>/, block);
  }
  if (/<p:sldIdLst\s*\/>/.test(presentationXml)) {
    return presentationXml.replace(/<p:sldIdLst\s*\/>/, block);
  }
  // No sldIdLst at all (a template with zero example slides) — CT_Presentation
  // requires it immediately before sldSz.
  return presentationXml.replace(/<p:sldSz/, `${block}<p:sldSz`);
}

/* --- assembly -------------------------------------------------------

   entries: Map<partName, Uint8Array> from unzipAll() of the uploaded
   template — the full package, not a filtered read.

   slides: [{ layoutPart: "ppt/slideLayouts/slideLayoutN.xml",
              layoutPlaceholders: [{type, idx, name}, ...],   // from profileTemplate
              shapes: [{ want: {idx?, name?, type?}, paragraphs: [{text, level}] }],
              notes?: string }]

   Returns { entries, warnings, errors }. On any error the entries map
   is NOT returned usable for zipping — callers must check errors
   first and never emit a file when errors.length > 0. */
function assemblePresentation(sourceEntries, slides) {
  const errors = [];
  const warnings = [];
  const entries = new Map(sourceEntries);
  const decode = bytes => new TextDecoder().decode(bytes);
  const encode = s => utf8Encode(s);

  const notesMasterName = [...entries.keys()].find(n => /^ppt\/notesMasters\/notesMaster\d+\.xml$/.test(n));
  const notesSupported = Boolean(notesMasterName);

  // Wipe existing slides and notes slides — we replace the deck wholesale.
  for (const name of [...entries.keys()]) {
    if (/^ppt\/slides\//.test(name) || /^ppt\/notesSlides\//.test(name)) entries.delete(name);
  }

  let contentTypes = decode(entries.get("[Content_Types].xml"));
  contentTypes = stripOverridesFor(contentTypes, "/ppt/slides/slide");
  contentTypes = stripOverridesFor(contentTypes, "/ppt/notesSlides/notesSlide");
  contentTypes = swapTemplateContentType(contentTypes);

  let presRels = decode(entries.get("ppt/_rels/presentation.xml.rels"));
  presRels = stripSlideRelationships(presRels);
  let nextRelId = maxRelId(presRels) + 1;

  let presentation = decode(entries.get("ppt/presentation.xml"));

  const newContentTypeOverrides = [];
  const newPresRels = [];
  const sldIdEntries = [];
  let nextSldId = 256;

  slides.forEach((slide, slideIndex) => {
    const slideNo = slideIndex + 1;
    const slidePart = `ppt/slides/slide${slideNo}.xml`;

    const resolvedShapes = [];
    for (const shape of slide.shapes) {
      const phSpec = resolvePlaceholder(slide.layoutPlaceholders || [], shape.want || {});
      if (!phSpec) {
        errors.push({
          slide: slideNo,
          message: `Slide ${slideNo}: no placeholder on layout "${slide.layoutPart}" matches `
            + `${JSON.stringify(shape.want)}.`,
        });
        continue;
      }
      resolvedShapes.push({ phSpec, paragraphs: shape.paragraphs });
    }
    if (errors.length) return; // stop resolving further slides once one has failed; report all found so far

    entries.set(slidePart, encode(buildSlideXml(resolvedShapes)));

    const layoutRelTarget = "../" + slide.layoutPart.replace(/^ppt\//, "");
    let notesTarget = null;
    let noteWarningAdded = false;

    if (slide.notes) {
      if (!notesSupported) {
        if (!noteWarningAdded) {
          warnings.push(`Slide ${slideNo}: speaker notes dropped — this template has no notes master.`);
          noteWarningAdded = true;
        }
      } else {
        const notesPart = `ppt/notesSlides/notesSlide${slideNo}.xml`;
        entries.set(notesPart, encode(buildNotesSlideXml(slide.notes)));
        entries.set(
          `ppt/notesSlides/_rels/notesSlide${slideNo}.xml.rels`,
          encode(buildNotesSlideRelsXml("../" + notesMasterName.replace(/^ppt\//, "")))
        );
        newContentTypeOverrides.push({ part: `/ppt/notesSlides/notesSlide${slideNo}.xml`, contentType: CT_NOTES });
        notesTarget = `../notesSlides/notesSlide${slideNo}.xml`;
      }
    }

    entries.set(`ppt/slides/_rels/slide${slideNo}.xml.rels`, encode(buildSlideRelsXml(layoutRelTarget, notesTarget)));
    newContentTypeOverrides.push({ part: `/${slidePart}`, contentType: CT_SLIDE });

    const rId = `rId${nextRelId++}`;
    newPresRels.push({ id: rId, type: REL_TYPE_SLIDE, target: `slides/slide${slideNo}.xml` });
    sldIdEntries.push(`<p:sldId id="${nextSldId++}" r:id="${rId}"/>`);
  });

  if (errors.length) {
    return { entries: null, warnings, errors };
  }

  contentTypes = addOverrides(contentTypes, newContentTypeOverrides);
  presRels = addRelationships(presRels, newPresRels);
  presentation = replaceSldIdLst(presentation, sldIdEntries);

  entries.set("[Content_Types].xml", encode(contentTypes));
  entries.set("ppt/_rels/presentation.xml.rels", encode(presRels));
  entries.set("ppt/presentation.xml", encode(presentation));

  return { entries, warnings, errors: [] };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    buildSlideXml, buildSlideRelsXml, buildNotesSlideXml, buildNotesSlideRelsXml,
    resolvePlaceholder, assemblePresentation,
  };
}
