/* =================================================================
   In-browser .pptx renderer — a port of scripts/render_pptx.py.

   The Python stays the reference implementation: it is the one with
   the test suite and the one the pipeline runs. This exists so the
   build half needs no terminal, and it must produce an equivalent
   deck — same slides, same placeholders, same absence of fonts and
   colours in slide XML. Where the two disagree, the Python is right.

   A .pptx is a ZIP of XML. DecompressionStream reads one;
   CompressionStream writes one; the rest is string building.
   ================================================================= */

const PPTX = (() => {
  "use strict";

  const EMU = 914400;
  const XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
  const NS_P = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ' +
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ' +
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"';
  const REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
  const CT_SLIDE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml";
  const CT_NOTES = "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml";
  const CT_PRESENTATION =
    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml";
  const TABLE_STYLE_ID = "{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}";

  // Gap panels are review annotations, not design — fixed colours so they read as a
  // warning on any template, and named so the fidelity scan knows to skip them.
  const GAP_FILL = "FEF3C7", GAP_LINE = "B45309", GAP_TEXT = "78350F";
  const GAP_PREFIX = "GAP-marker-";

  const DEFAULT_BODY_PT = 18, DEFAULT_TITLE_PT = 26, MIN_FONT_SCALE = 0.70;
  const TEXT_KINDS = new Set(["text", "heading", "paragraph", "bullets"]);
  const SHAPE_KINDS = new Set(["table", "metric", "phases", "members", "image"]);
  const STACK_GAP = 0.14;

  const enc = new TextEncoder();
  const dec = new TextDecoder();

  // Matches Python's html.escape(quote=True) entity-for-entity, so a deck built here is
  // byte-identical to one built by render_pptx.py — which is how the two stay honest.
  const esc = v => String(v).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;" }[c]));
  const emu = inches => Math.round(inches * EMU);
  const norm = v => String(v).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  const xfrm = (x, y, w, h, tag = "a") =>
    `<${tag}:xfrm><a:off x="${emu(x)}" y="${emu(y)}"/>` +
    `<a:ext cx="${emu(w)}" cy="${emu(h)}"/></${tag}:xfrm>`;

  /* --- ZIP -------------------------------------------------------- */

  const CRC_TABLE = (() => {
    const t = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      t[i] = c >>> 0;
    }
    return t;
  })();

  function crc32(bytes) {
    let c = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  async function deflateRaw(bytes) {
    const s = new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate-raw"));
    return new Uint8Array(await new Response(s).arrayBuffer());
  }

  async function inflateRaw(bytes) {
    const s = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    return new Uint8Array(await new Response(s).arrayBuffer());
  }

  async function unzip(buffer) {
    const dv = new DataView(buffer);
    let eocd = -1;
    for (let i = buffer.byteLength - 22; i >= Math.max(0, buffer.byteLength - 66000); i--) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new Error("template is not a valid .potx/.pptx");
    const count = dv.getUint16(eocd + 10, true);
    let at = dv.getUint32(eocd + 16, true);
    const out = new Map();
    for (let n = 0; n < count; n++) {
      if (dv.getUint32(at, true) !== 0x02014b50) break;
      const method = dv.getUint16(at + 10, true);
      const compSize = dv.getUint32(at + 20, true);
      const nameLen = dv.getUint16(at + 28, true);
      const extraLen = dv.getUint16(at + 30, true);
      const commentLen = dv.getUint16(at + 32, true);
      const localAt = dv.getUint32(at + 42, true);
      const name = dec.decode(new Uint8Array(buffer, at + 46, nameLen));
      at += 46 + nameLen + extraLen + commentLen;
      const start = localAt + 30 + dv.getUint16(localAt + 26, true)
                              + dv.getUint16(localAt + 28, true);
      const raw = new Uint8Array(buffer, start, compSize);
      out.set(name, method === 0 ? new Uint8Array(raw) : await inflateRaw(raw));
    }
    return out;
  }

  async function zip(parts) {
    const chunks = [], central = [];
    let offset = 0;
    const DOS_DATE = 0x5C21;  // 2026-01-01, fixed so a rebuild is byte-comparable

    for (const [name, data] of parts) {
      const nameBytes = enc.encode(name);
      const crc = crc32(data);
      const deflated = await deflateRaw(data);
      const shrinks = deflated.length < data.length;
      const body = shrinks ? deflated : data;
      const method = shrinks ? 8 : 0;

      const lh = new Uint8Array(30 + nameBytes.length);
      const lv = new DataView(lh.buffer);
      lv.setUint32(0, 0x04034b50, true);
      lv.setUint16(4, 20, true);
      lv.setUint16(8, method, true);
      lv.setUint16(12, DOS_DATE, true);
      lv.setUint32(14, crc, true);
      lv.setUint32(18, body.length, true);
      lv.setUint32(22, data.length, true);
      lv.setUint16(26, nameBytes.length, true);
      lh.set(nameBytes, 30);
      chunks.push(lh, body);

      const cd = new Uint8Array(46 + nameBytes.length);
      const cv = new DataView(cd.buffer);
      cv.setUint32(0, 0x02014b50, true);
      cv.setUint16(4, 20, true);
      cv.setUint16(6, 20, true);
      cv.setUint16(10, method, true);
      cv.setUint16(14, DOS_DATE, true);
      cv.setUint32(16, crc, true);
      cv.setUint32(20, body.length, true);
      cv.setUint32(24, data.length, true);
      cv.setUint16(28, nameBytes.length, true);
      cv.setUint32(42, offset, true);
      cd.set(nameBytes, 46);
      central.push(cd);

      offset += lh.length + body.length;
    }

    const centralSize = central.reduce((n, c) => n + c.length, 0);
    const eocd = new Uint8Array(22);
    const ev = new DataView(eocd.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(8, parts.size, true);
    ev.setUint16(10, parts.size, true);
    ev.setUint32(12, centralSize, true);
    ev.setUint32(16, offset, true);
    return new Blob([...chunks, ...central, eocd]);
  }

  /* --- plan resolution (port of build_deck.build) ------------------ */

  function layoutLookup(profile) {
    const table = new Map();
    for (const layout of profile.layouts || []) {
      const stem = layout.part.split("/").pop().replace(/\.xml$/, "");
      for (const key of [stem, norm(stem), layout.name, norm(layout.name || "")]) {
        if (key && !table.has(key)) table.set(key, layout);
      }
    }
    return table;
  }

  function placeholderTable(layout) {
    const byType = new Map(), table = new Map();
    for (const ph of layout.placeholders || []) {
      for (const key of [ph.name, norm(ph.name || "")]) {
        if (key && !table.has(key)) table.set(key, ph);
      }
      if (ph.idx != null && !table.has(String(ph.idx))) table.set(String(ph.idx), ph);
      if (ph.type && !byType.has(String(ph.type))) byType.set(String(ph.type), ph);
    }
    for (const [k, ph] of byType) if (!table.has(k)) table.set(k, ph);
    return table;
  }

  function buildSteps(plan, profile) {
    const layouts = layoutLookup(profile);
    const steps = [], errors = [];
    let slideNo = 0;
    const sections = [...(plan.sections || [])].sort((a, b) => (a.order || 0) - (b.order || 0));

    for (const section of sections) {
      for (const slide of section.slides || []) {
        slideNo += 1;
        const ref = String(slide.layout);
        const layout = layouts.get(ref) || layouts.get(norm(ref));
        if (!layout) {
          const available = (profile.layouts || []).map(l => l.name || l.part).join(", ");
          errors.push(`${slide.slide_id}: layout '${ref}' is not in the template. Available: ${available}`);
          continue;
        }
        const table = placeholderTable(layout);
        const fills = [];
        for (const block of slide.blocks || []) {
          const key = String(block.placeholder);
          const target = table.get(key) || table.get(norm(key));
          if (!target) {
            const available = (layout.placeholders || []).map(p => p.name || p.type).join(", ");
            errors.push(`${slide.slide_id}: placeholder '${key}' not on layout '${layout.name || ref}'. Available: ${available}`);
            continue;
          }
          const isGap = !!block.gap;
          fills.push({
            placeholder: key, resolved: target, kind: block.kind,
            content: isGap ? "[GAP] " + (block.gap_note || "") : block.content,
            gap: isGap, gap_note: isGap ? block.gap_note : null,
            sources: block.sources || []
          });
        }
        steps.push({
          position: slideNo, slide_id: slide.slide_id, section_id: section.section_id,
          layout_part: layout.part, layout_name: layout.name, title: slide.title,
          fills, speaker_notes: slide.speaker_notes
        });
      }
    }
    return { steps, errors };
  }

  /* --- text fitting ------------------------------------------------ */

  const textLines = (paras, perLine) =>
    paras.reduce((n, p) => n + Math.max(1, Math.ceil(String(p).length / perLine)), 0);

  function fitRatio(paras, geometry, fontPt) {
    if (!geometry || !fontPt) return null;
    const perLine = Math.max(1, Math.floor((geometry.w_in * 72) / (fontPt * 0.5)));
    const capacity = Math.max(1, (geometry.h_in * 72) / (fontPt * 1.25));
    return textLines(paras, perLine) / capacity;
  }

  /* --- blocks ------------------------------------------------------ */

  function blockParagraphs(fill) {
    const { kind, content } = fill;
    if (kind === "bullets") {
      const items = Array.isArray(content) ? content : [content];
      return items.map(i => [String(i), 0, true]);
    }
    if (kind === "paragraph") {
      const paras = Array.isArray(content) ? content : [content];
      return paras.map(p => [String(p), 0, false]);
    }
    return [[String(content), 0, false]];
  }

  const colourFill = c => /^[0-9A-F]{6}$/.test(c)
    ? `<a:srgbClr val="${c}"/>` : `<a:schemeClr val="${c}"/>`;

  function paraXml(text, level = 0, o = {}) {
    const { bullet = true, sizePt, colour, font, bold = false, caps = false, spaceAfter } = o;
    const props = [];
    let attrs = "";
    if (!bullet) { attrs = ' marL="0" indent="0"'; props.push("<a:buNone/>"); }
    if (spaceAfter != null) props.push(`<a:spcAft><a:spcPts val="${Math.round(spaceAfter)}"/></a:spcAft>`);

    const rpr = ['lang="en-GB"'];
    if (sizePt) rpr.push(`sz="${Math.round(sizePt * 100)}"`);
    if (bold) rpr.push('b="1"');
    if (caps) rpr.push('cap="all"');
    let children = "";
    if (colour) children += `<a:solidFill>${colourFill(colour)}</a:solidFill>`;
    if (font) children += `<a:latin typeface="${font}"/>`;
    const rprXml = children
      ? `<a:rPr ${rpr.join(" ")}>${children}</a:rPr>` : `<a:rPr ${rpr.join(" ")}/>`;
    const lvl = level ? ` lvl="${level}"` : "";
    const ppr = (props.length || lvl || attrs) ? `<a:pPr${lvl}${attrs}>${props.join("")}</a:pPr>` : "";
    return `<a:p>${ppr}<a:r>${rprXml}<a:t>${esc(text)}</a:t></a:r></a:p>`;
  }

  function placeholderSp(id, ph, paragraphs, fontScale, geometryOverride) {
    let phAttrs = `type="${ph.type || "body"}"`;
    if (ph.idx != null) phAttrs += ` idx="${ph.idx}"`;
    let autofit = "<a:normAutofit/>";
    if (fontScale != null && fontScale < 1) {
      autofit = `<a:normAutofit fontScale="${Math.round(fontScale * 100000)}"` +
                ` lnSpcReduction="${Math.round((1 - fontScale) * 50000)}"/>`;
    }
    const spPr = geometryOverride
      ? `<p:spPr>${xfrm(...geometryOverride)}</p:spPr>` : "<p:spPr/>";
    const body = paragraphs.map(([t, l, b]) => paraXml(t, l, { bullet: b })).join("")
      || '<a:p><a:endParaRPr lang="en-GB"/></a:p>';
    return `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="${esc(ph.name || "Content")}"/>` +
      `<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>` +
      `<p:nvPr><p:ph ${phAttrs}/></p:nvPr></p:nvSpPr>${spPr}` +
      `<p:txBody><a:bodyPr>${autofit}</a:bodyPr><a:lstStyle/>${body}</p:txBody></p:sp>`;
  }

  function textBox(id, name, geom, paragraphs, o = {}) {
    const { fillScheme, lineScheme, anchor = "t", rounded = false, fillHex, lineHex } = o;
    let fill = "<a:noFill/>";
    if (fillHex) fill = `<a:solidFill><a:srgbClr val="${fillHex}"/></a:solidFill>`;
    else if (fillScheme) fill = `<a:solidFill><a:schemeClr val="${fillScheme}"/></a:solidFill>`;
    let line = "<a:ln><a:noFill/></a:ln>";
    if (lineHex) line = `<a:ln w="28575"><a:solidFill><a:srgbClr val="${lineHex}"/></a:solidFill></a:ln>`;
    else if (lineScheme) line = `<a:ln w="9525"><a:solidFill><a:schemeClr val="${lineScheme}"/></a:solidFill></a:ln>`;
    const geometry = rounded ? "roundRect" : "rect";
    const avLst = rounded ? '<a:gd name="adj" fmla="val 6000"/>' : "";
    return `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="${esc(name)}"/>` +
      `<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>` +
      `<p:spPr>${xfrm(...geom)}<a:prstGeom prst="${geometry}"><a:avLst>${avLst}</a:avLst>` +
      `</a:prstGeom>${fill}${line}</p:spPr>` +
      `<p:txBody><a:bodyPr anchor="${anchor}" wrap="square" lIns="91440" tIns="54864" ` +
      `rIns="91440" bIns="54864"><a:normAutofit/></a:bodyPr><a:lstStyle/>` +
      `${paragraphs.join("")}</p:txBody></p:sp>`;
  }

  const ruleShape = (id, name, x, y, w, colour, width = 28575) =>
    `<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="${id}" name="${esc(name)}"/>` +
    `<p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>` +
    `<p:spPr>${xfrm(x, y, w, 0)}<a:prstGeom prst="line"><a:avLst/></a:prstGeom>` +
    `<a:ln w="${width}"><a:solidFill>${colourFill(colour)}</a:solidFill></a:ln>` +
    `</p:spPr></p:cxnSp>`;

  function renderTable(id, geom, content, fontPt) {
    const headers = (content && content.headers) || [];
    const rows = (content && content.rows) || [];
    const cols = Math.max(headers.length, ...rows.map(r => r.length), 1);
    const [x, y, w, h] = geom;
    const colW = emu(w / cols);
    const rowCount = rows.length + (headers.length ? 1 : 0);
    const rowH = emu(Math.min(0.42, h / Math.max(rowCount, 1)));

    const cell = (text, header) => {
      const para = paraXml(text, 0, {
        bullet: false, sizePt: fontPt * (header ? 0.92 : 1),
        colour: header ? "bg1" : "tx2", font: "+mn-lt",
        bold: header, caps: header, spaceAfter: 0
      });
      return `<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>${para}</a:txBody>` +
        `<a:tcPr marL="68580" marR="68580" marT="45720" marB="45720" anchor="t"/></a:tc>`;
    };
    const trs = [];
    if (headers.length) {
      trs.push(`<a:tr h="${rowH}">` + headers.map(c => cell(c, true)).join("") +
        Array(cols - headers.length).fill(cell("", true)).join("") + "</a:tr>");
    }
    for (const row of rows) {
      trs.push(`<a:tr h="${rowH}">` + row.map(c => cell(c, false)).join("") +
        Array(cols - row.length).fill(cell("", false)).join("") + "</a:tr>");
    }
    const grid = Array(cols).fill(`<a:gridCol w="${colW}"/>`).join("");
    return `<p:graphicFrame><p:nvGraphicFramePr>` +
      `<p:cNvPr id="${id}" name="Table ${id}"/>` +
      `<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>` +
      `<p:nvPr/></p:nvGraphicFramePr>${xfrm(x, y, w, h, "p")}` +
      `<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">` +
      `<a:tbl><a:tblPr firstRow="1" bandRow="1"><a:tableStyleId>${TABLE_STYLE_ID}` +
      `</a:tableStyleId></a:tblPr><a:tblGrid>${grid}</a:tblGrid>${trs.join("")}` +
      `</a:tbl></a:graphicData></a:graphic></p:graphicFrame>`;
  }

  function renderMetrics(id, geom, content, fontPt) {
    const tiles = Array.isArray(content) ? content : [content];
    const [x, y, w, h] = geom;
    const gap = 0.18;
    const tileW = (w - gap * (tiles.length - 1)) / Math.max(tiles.length, 1);
    return tiles.map((tile, i) => textBox(id + i, `Metric ${i + 1}`,
      [x + i * (tileW + gap), y, tileW, h], [
        paraXml(tile.value || "", 0, { bullet: false, sizePt: fontPt * 1.9,
          colour: "tx1", font: "+mj-lt", bold: true, spaceAfter: 200 }),
        paraXml(tile.label || "", 0, { bullet: false, sizePt: fontPt * 0.62,
          colour: "tx2", font: "+mn-lt", spaceAfter: 0 })
      ], { fillScheme: "accent6", anchor: "ctr", rounded: true }));
  }

  function renderPhases(startId, geom, content, fontPt) {
    const phases = Array.isArray(content) ? content : [content];
    const [x, y, w, h] = geom;
    const gap = 0.22;
    const colW = (w - gap * (phases.length - 1)) / Math.max(phases.length, 1);
    const shapes = [];
    let id = startId;
    phases.forEach((phase, i) => {
      const cx = x + i * (colW + gap);
      shapes.push(ruleShape(id++, `Phase rule ${i + 1}`, cx, y, colW, "accent1"));
      const paras = [
        paraXml(phase.label || `Phase ${i + 1}`, 0, { bullet: false, sizePt: fontPt * 0.7,
          colour: "accent1", font: "+mn-lt", bold: true, caps: true, spaceAfter: 120 }),
        paraXml(phase.name || "", 0, { bullet: false, sizePt: fontPt * 1.05,
          colour: "tx1", font: "+mj-lt", bold: true, spaceAfter: 200 })
      ];
      const detail = phase.detail;
      const lines = Array.isArray(detail) ? detail : (detail ? [detail] : []);
      for (const line of lines) {
        paras.push(paraXml(`— ${line}`, 0, { bullet: false, sizePt: fontPt * 0.78,
          colour: "tx2", font: "+mn-lt", spaceAfter: 140 }));
      }
      shapes.push(textBox(id++, `Phase ${i + 1}`, [cx, y + 0.08, colW, h - 0.08], paras));
    });
    return shapes;
  }

  function renderMembers(startId, geom, content, fontPt) {
    const members = Array.isArray(content) ? content : [content];
    const [x, y, w, h] = geom;
    const cols = Math.min(4, Math.max(members.length, 1));
    const rows = Math.ceil(members.length / cols);
    const gapX = 0.24, gapY = 0.22;
    const cardW = (w - gapX * (cols - 1)) / cols;
    const cardH = (h - gapY * (rows - 1)) / rows;
    const shapes = [];
    let id = startId;
    members.forEach((member, i) => {
      const cx = x + (i % cols) * (cardW + gapX);
      const cy = y + Math.floor(i / cols) * (cardH + gapY);
      const name = String(member.name || "");
      const isGap = name.startsWith("[GAP]");
      const label = isGap ? `${GAP_PREFIX}member-${i + 1}` : `Member ${i + 1}`;
      shapes.push(ruleShape(id++, `${label} rule`, cx, cy, cardW,
        isGap ? GAP_LINE : "accent3"));
      shapes.push(textBox(id++, label, [cx, cy + 0.06, cardW, cardH - 0.06], [
        paraXml(name, 0, { bullet: false, sizePt: fontPt * 1.05,
          colour: isGap ? GAP_LINE : "tx1", font: "+mj-lt", bold: true, spaceAfter: 100 }),
        paraXml(member.role || "", 0, { bullet: false, sizePt: fontPt * 0.7,
          colour: "accent1", font: "+mn-lt", bold: true, spaceAfter: 180 }),
        paraXml(member.bio || "", 0, { bullet: false, sizePt: fontPt * 0.78,
          colour: "tx2", font: "+mn-lt", spaceAfter: 0 })
      ]));
    });
    return shapes;
  }

  const renderGap = (id, geom, note) => textBox(id, `${GAP_PREFIX}${id}`, geom, [
    paraXml("[GAP]", 0, { bullet: false, sizePt: 11, colour: GAP_LINE, font: "+mn-lt",
      bold: true, caps: true, spaceAfter: 140 }),
    paraXml(note || "Not covered by the knowledge bank.", 0, { bullet: false, sizePt: 13,
      colour: GAP_TEXT, font: "+mn-lt", spaceAfter: 0 })
  ], { fillHex: GAP_FILL, lineHex: GAP_LINE, rounded: true });

  /* --- layout ------------------------------------------------------ */

  const geomOf = (ph, fallback) => ph.geometry
    ? [ph.geometry.x_in, ph.geometry.y_in, ph.geometry.w_in, ph.geometry.h_in] : fallback;

  function desiredHeight(fill, widthIn, fontPt) {
    if (fill.gap) {
      const note = fill.gap_note || "";
      const perLine = Math.max(1, Math.floor((widthIn * 72) / (13 * 0.5)));
      return Math.min(2.6, 0.55 + Math.max(1, Math.ceil(note.length / perLine)) * 13 * 1.35 / 72);
    }
    const { kind, content } = fill;
    if (kind === "table") {
      const rows = (content && content.rows ? content.rows.length : 0) +
        (content && content.headers ? 1 : 0);
      return Math.max(0.6, rows * Math.max(0.34, fontPt * 0.7 * 2.6 / 72));
    }
    if (kind === "metric") return 1.5;
    if (kind === "phases") {
      const phases = Array.isArray(content) ? content : [content];
      const deepest = Math.max(...phases.map(p =>
        Array.isArray(p.detail) ? p.detail.length : 1), 1);
      return 0.75 + deepest * 0.26;
    }
    if (kind === "members") {
      const members = Array.isArray(content) ? content : [content];
      return Math.ceil(members.length / Math.min(4, Math.max(members.length, 1))) * 1.6;
    }
    if (kind === "image") return 2.5;
    const paras = blockParagraphs(fill).map(p => p[0]);
    const perLine = Math.max(1, Math.floor((widthIn * 72) / (fontPt * 0.5)));
    return textLines(paras, perLine) * fontPt * 1.35 / 72;
  }

  function stack(units, box, fontPt) {
    const [x, y, w, h] = box;
    let wants = units.map(([kind, payload]) => {
      const fills = kind === "text" ? payload : [payload];
      return fills.reduce((n, f) => n + desiredHeight(f, w, fontPt), 0);
    });
    const slack = STACK_GAP * (units.length - 1);
    const total = wants.reduce((a, b) => a + b, 0);
    if (total + slack > h) {
      const scale = (h - slack) / Math.max(total, 0.01);
      wants = wants.map(v => Math.max(0.3, v * scale));
    }
    const boxes = [];
    let cursor = y;
    for (const want of wants) { boxes.push([x, cursor, w, want]); cursor += want + STACK_GAP; }
    return boxes;
  }

  function slideFooter(step, plan, mode, position, total) {
    if (mode === "hidden") return null;
    const sources = [...new Set(step.fills.flatMap(f => f.sources || []))].sort();
    const gaps = step.fills.filter(f => f.gap).length;
    let left = sources.length ? "Sources: " + sources.join(", ") : "";
    if (gaps) {
      const marker = `${gaps} open gap${gaps > 1 ? "s" : ""}`;
      left = left ? `${left} · ${marker}` : marker;
    }
    const right = `${plan.client || ""} · ${position} / ${total}`.replace(/^ · /, "");
    return `${left || "No sources recorded"}    |    ${right}`;
  }

  function buildSlide(step, plan, options, position, total) {
    const shapes = [], warnings = [];
    let shapeId = 2;
    const fallback = [0.62, 1.68, 12.09, 4.98];

    const grouped = new Map();
    for (const fill of step.fills) {
      const key = fill.resolved.name || fill.placeholder;
      if (!grouped.has(key)) grouped.set(key, { ph: fill.resolved, fills: [] });
      grouped.get(key).fills.push(fill);
    }

    const titlePh = options.titles[step.layout_part];
    if (titlePh && step.title) {
      const claimed = [...grouped.values()].some(g =>
        g.ph === titlePh || (g.ph.name || "").toLowerCase() === "title");
      if (!claimed) {
        grouped.set("title", { ph: titlePh,
          fills: [{ kind: "text", content: step.title, sources: [], gap: false }] });
      }
    }

    for (const [key, group] of grouped) {
      const ph = group.ph;
      const geom = geomOf(ph, fallback);
      const fontPt = ph.font_size_pt ||
        (String(ph.type || "").endsWith("itle") ? DEFAULT_TITLE_PT : DEFAULT_BODY_PT);

      const units = [];
      let run = [];
      for (const fill of group.fills) {
        if (!fill.gap && TEXT_KINDS.has(fill.kind)) run.push(fill);
        else { if (run.length) { units.push(["text", run]); run = []; } units.push(["shape", fill]); }
      }
      if (run.length) units.push(["text", run]);

      const single = units.length === 1;
      const boxes = single ? [geom] : stack(units, geom, fontPt);

      units.forEach(([unitKind, payload], i) => {
        const box = boxes[i];
        if (unitKind === "text") {
          const paragraphs = payload.flatMap(blockParagraphs);
          const ratio = fitRatio(paragraphs.map(p => p[0]),
            { w_in: box[2], h_in: box[3] }, fontPt);
          let scale = null;
          if (ratio && ratio > 1) {
            scale = Math.max(MIN_FONT_SCALE, 1 / ratio);
            warnings.push(`${step.slide_id}/${key}: text is ~${Math.round(ratio * 100)}% of the ` +
              `space at ${Math.round(fontPt)}pt — autofit set to ${Math.round(scale * 100)}%` +
              (1 / ratio < MIN_FONT_SCALE ? "; still over, cut content" : ""));
          }
          shapes.push(placeholderSp(shapeId++, ph, paragraphs, scale, single ? null : box));
          return;
        }
        const fill = payload;
        if (fill.gap) { shapes.push(renderGap(shapeId++, box, fill.gap_note)); return; }
        const { kind, content } = fill;
        if (kind === "table") { shapes.push(renderTable(shapeId++, box, content, fontPt * 0.7)); }
        else if (kind === "metric") {
          const made = renderMetrics(shapeId, box, content, fontPt);
          shapes.push(...made); shapeId += made.length;
        } else if (kind === "phases") {
          const made = renderPhases(shapeId, box, content, fontPt);
          shapes.push(...made); shapeId += made.length;
        } else if (kind === "members") {
          const made = renderMembers(shapeId, box, content, fontPt);
          shapes.push(...made); shapeId += made.length;
        } else if (kind === "image") {
          // Embedding a picture needs a media part and a content-type override. The
          // Python renderer does it; this one says so rather than dropping the block.
          warnings.push(`${step.slide_id}/${key}: image blocks are not supported in the ` +
            `browser build — use render_pptx.py for this deck`);
          shapes.push(renderGap(shapeId++, box,
            "Image block: build this deck with render_pptx.py, which embeds pictures."));
        }
      });
    }

    const footerPh = options.footers[step.layout_part];
    const footer = slideFooter(step, plan, options.sources, position, total);
    if (footerPh && footer) shapes.push(placeholderSp(shapeId++, footerPh, [[footer, 0, false]]));

    const xml = XML_DECL +
      `<p:sld ${NS_P}><p:cSld><p:spTree>` +
      `<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>` +
      `<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>` +
      `<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>` +
      `${shapes.join("")}</p:spTree></p:cSld>` +
      `<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`;
    return { xml, warnings };
  }

  const notesSlide = text => XML_DECL +
    `<p:notes ${NS_P}><p:cSld><p:spTree>` +
    `<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>` +
    `<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>` +
    `<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>` +
    `<p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes Placeholder 1"/>` +
    `<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>` +
    `<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/>` +
    `<p:txBody><a:bodyPr/><a:lstStyle/>` +
    String(text).split("\n").filter(l => l.trim())
      .map(l => paraXml(l, 0, { bullet: false })).join("") +
    `</p:txBody></p:sp></p:spTree></p:cSld>` +
    `<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>`;

  const relsXml = pairs => XML_DECL +
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
    pairs.map(([id, type, target]) =>
      `<Relationship Id="${id}" Type="${type}" Target="${target}"/>`).join("") +
    "</Relationships>";

  /* --- the build --------------------------------------------------- */

  async function render(plan, profile, templateBytes, options = {}) {
    const sources = options.sources || "footer";
    const { steps, errors } = buildSteps(plan, profile);
    if (errors.length) return { errors, warnings: [], blob: null, parts: null, steps: [] };

    const template = await unzip(templateBytes);
    const parts = new Map(template);
    const hasNotesMaster = [...parts.keys()].some(n => n.startsWith("ppt/notesMasters/notesMaster"));
    for (const name of [...parts.keys()]) {
      if (name.startsWith("ppt/slides/") || name.startsWith("ppt/notesSlides/")) parts.delete(name);
    }

    const footers = {}, titles = {};
    for (const layout of profile.layouts || []) {
      for (const ph of layout.placeholders || []) {
        const name = (ph.name || "").toLowerCase();
        if (name === "footer" && !footers[layout.part]) footers[layout.part] = ph;
        if ((name === "title" || ["title", "ctrTitle"].includes(ph.type)) && !titles[layout.part])
          titles[layout.part] = ph;
      }
    }

    let presRels = dec.decode(parts.get("ppt/_rels/presentation.xml.rels"));
    presRels = presRels.replace(/<Relationship[^>]*Type="[^"]*\/slide"[^>]*\/>/g, "");
    let rid = Math.max(0, ...[...presRels.matchAll(/Id="rId(\d+)"/g)].map(m => +m[1])) + 1;

    const allWarnings = [], slideEntries = [];
    let notesCount = 0;
    const total = steps.length;

    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      const { xml, warnings } = buildSlide(step, plan,
        { sources, footers, titles }, i + 1, total);
      allWarnings.push(...warnings);
      const slidePart = `ppt/slides/slide${i + 1}.xml`;
      parts.set(slidePart, enc.encode(xml));

      const slideRels = [["rId1", `${REL}/slideLayout`,
        "../slideLayouts/" + step.layout_part.split("/").pop()]];
      if (step.speaker_notes && hasNotesMaster) {
        notesCount += 1;
        parts.set(`ppt/notesSlides/notesSlide${notesCount}.xml`,
          enc.encode(notesSlide(step.speaker_notes)));
        parts.set(`ppt/notesSlides/_rels/notesSlide${notesCount}.xml.rels`, enc.encode(relsXml([
          ["rId1", `${REL}/notesMaster`, "../notesMasters/notesMaster1.xml"],
          ["rId2", `${REL}/slide`, `../slides/slide${i + 1}.xml`]
        ])));
        slideRels.push([`rId${slideRels.length + 1}`, `${REL}/notesSlide`,
          `../notesSlides/notesSlide${notesCount}.xml`]);
      }
      parts.set(`ppt/slides/_rels/slide${i + 1}.xml.rels`, enc.encode(relsXml(slideRels)));
      slideEntries.push([`rId${rid++}`, slidePart]);
    }

    presRels = presRels.replace("</Relationships>",
      slideEntries.map(([r, p]) =>
        `<Relationship Id="${r}" Type="${REL}/slide" Target="${p.slice(4)}"/>`).join("") +
      "</Relationships>");
    parts.set("ppt/_rels/presentation.xml.rels", enc.encode(presRels));

    let pres = dec.decode(parts.get("ppt/presentation.xml"));
    pres = pres.replace(/<p:sldIdLst>[\s\S]*?<\/p:sldIdLst>/, "");
    const sldIdLst = "<p:sldIdLst>" + slideEntries.map(([r], i) =>
      `<p:sldId id="${256 + i}" r:id="${r}"/>`).join("") + "</p:sldIdLst>";
    pres = pres.replace("<p:sldSz", sldIdLst + "<p:sldSz");
    parts.set("ppt/presentation.xml", enc.encode(pres));

    let ct = dec.decode(parts.get("[Content_Types].xml"));
    ct = ct.replace(/<Override PartName="\/ppt\/(slides|notesSlides)\/[^"]*"[^>]*\/>/g, "");
    ct = ct.replace(
      "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml",
      CT_PRESENTATION);
    ct = ct.replace("</Types>",
      slideEntries.map(([, p]) => `<Override PartName="/${p}" ContentType="${CT_SLIDE}"/>`).join("") +
      Array.from({ length: notesCount }, (_, n) =>
        `<Override PartName="/ppt/notesSlides/notesSlide${n + 1}.xml" ContentType="${CT_NOTES}"/>`).join("") +
      "</Types>");
    parts.set("[Content_Types].xml", enc.encode(ct));

    if (parts.has("docProps/app.xml")) {
      let app = dec.decode(parts.get("docProps/app.xml"));
      app = app.replace(/<Slides>\d+<\/Slides>/, `<Slides>${total}</Slides>`)
               .replace(/<Notes>\d+<\/Notes>/, `<Notes>${notesCount}</Notes>`);
      parts.set("docProps/app.xml", enc.encode(app));
    }

    const ordered = new Map([...parts.entries()].sort((a, b) => a[0].localeCompare(b[0])));
    return {
      errors: [], warnings: allWarnings, steps, notesCount,
      gaps: steps.reduce((n, s) => n + s.fills.filter(f => f.gap).length, 0),
      blob: await zip(ordered), parts: ordered, template
    };
  }

  /* --- QA (port of qa_pptx.py's mechanical checks) ------------------ */

  const SCAFFOLDING = [
    [/\blorem\b/i, "lorem ipsum"], [/\[insert/i, "[insert …"], [/\bTODO\b/, "TODO"],
    [/\bTBC\b|\bTBD\b/, "TBC/TBD"], [/\bxxx+\b/i, "xxx"],
    [/click to edit/i, "template prompt text"], [/\bplaceholder\b/i, "the word 'placeholder'"]
  ];

  function audit(result) {
    const fidelity = [], scaffolding = [];
    const parser = new DOMParser();

    // Template parts must survive byte-for-byte: that is what makes "built on the
    // approved template" a fact rather than a resemblance.
    const TEMPLATE_PARTS = ["ppt/slideMasters/", "ppt/slideLayouts/", "ppt/theme/",
                            "ppt/tableStyles.xml"];
    for (const [name, data] of result.template) {
      if (!TEMPLATE_PARTS.some(p => name.startsWith(p))) continue;
      const ours = result.parts.get(name);
      if (!ours) fidelity.push(`${name}: present in the template, missing from the deck`);
      else if (ours.length !== data.length || !ours.every((b, i) => b === data[i]))
        fidelity.push(`${name}: edited — the deck has drifted off the template`);
    }

    for (const [name, data] of result.parts) {
      if (!/^ppt\/slides\/slide\d+\.xml$/.test(name)) continue;
      const doc = parser.parseFromString(dec.decode(data), "application/xml");
      if (doc.querySelector("parsererror")) { fidelity.push(`${name}: malformed XML`); continue; }
      const tree = doc.getElementsByTagNameNS("*", "spTree")[0];
      for (const shape of tree ? Array.from(tree.children) : []) {
        const labelEl = shape.getElementsByTagNameNS("*", "cNvPr")[0];
        const label = labelEl ? labelEl.getAttribute("name") || "" : "";
        const text = Array.from(shape.getElementsByTagNameNS("*", "t"))
          .map(t => t.textContent).join(" ");
        for (const [pattern, what] of SCAFFOLDING) {
          if (pattern.test(text)) scaffolding.push(`${name} / ${label}: ${what}`);
        }
        if (label.startsWith(GAP_PREFIX)) continue;   // annotations name colours on purpose
        for (const el of shape.getElementsByTagNameNS("*", "latin")) {
          const face = el.getAttribute("typeface");
          if (face && !face.startsWith("+"))
            fidelity.push(`${name} / ${label}: sets font '${face}'`);
        }
        for (const el of shape.getElementsByTagNameNS("*", "srgbClr")) {
          fidelity.push(`${name} / ${label}: sets literal colour '${el.getAttribute("val")}'`);
        }
      }
    }
    return { fidelity, scaffolding, overflow: result.warnings };
  }

  /* --- plan-level QA (port of qa_deck.py) --------------------------- */

  const SLIDE_KINDS = new Set(["proposal-content", "delivery-obligation", "commercial-constraint"]);

  function auditPlan(plan, brief) {
    const covered = new Map(), gaps = [], unattributed = [];
    for (const section of plan.sections || []) {
      for (const rid of section.requirement_ids || []) {
        if (!covered.has(rid)) covered.set(rid, []);
        covered.get(rid).push(section.section_id);
      }
      for (const slide of section.slides || []) {
        (slide.blocks || []).forEach((block, i) => {
          const where = `${section.section_id} / ${slide.slide_id} / block ${i}`;
          if (block.gap) gaps.push({ where, note: block.gap_note || "(no gap_note recorded)",
                                     requirement_ids: section.requirement_ids || [] });
          else if (!(block.sources || []).length) unattributed.push(where);
        });
      }
    }
    if (!brief) return { covered, gaps, unattributed, needsSlide: [], uncovered: [], documentRules: [] };

    const reqs = new Map((brief.requirements || []).map(r => [r.id, r]));
    const needsSlide = [...reqs.entries()]
      .filter(([, r]) => SLIDE_KINDS.has(r.kind || "proposal-content")).map(([id]) => id);
    const documentRules = [...reqs.keys()].filter(id => !needsSlide.includes(id));
    const uncovered = needsSlide.filter(id => !covered.has(id));
    return { covered, gaps, unattributed, needsSlide, uncovered, documentRules, reqs };
  }

  return { render, audit, auditPlan, buildSteps, unzip };
})();
