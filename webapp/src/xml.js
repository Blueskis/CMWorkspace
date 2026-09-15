/**
 * Small XML / OOXML helpers shared by the parsers and the assembler.
 *
 * Reading goes through @xmldom/xmldom (see env.js for why one parser is used in both
 * environments). Writing is plain string construction — the same approach the Python
 * pipeline takes, and the reason it never had to round-trip OOXML through a serializer
 * (which is what corrupts namespace prefixes; see the pptx skill's warning).
 */

export const NS = {
  W: "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
  A: "http://schemas.openxmlformats.org/drawingml/2006/main",
  P: "http://schemas.openxmlformats.org/presentationml/2006/main",
  R: "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
  REL: "http://schemas.openxmlformats.org/package/2006/relationships",
  CT: "http://schemas.openxmlformats.org/package/2006/content-types",
};

export const EMU_PER_INCH = 914400;

export function emu(inches) {
  return Math.round(inches * EMU_PER_INCH);
}

/** Escape text for insertion into an XML text node or attribute value. */
export function xmlEscape(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * Elements by local name, ignoring namespace prefix.
 *
 * Real-world OOXML does not agree on prefixes — one template writes <p:sp>, another
 * binds the same namespace to a different prefix — so matching on the prefix (which the
 * Python version could get away with because it used namespace-aware ElementTree
 * lookups) would silently return nothing on a perfectly valid client template.
 */
export function findAll(node, localName) {
  const out = [];
  const walk = (n) => {
    if (!n) return;
    if (n.nodeType === 1) {
      const local = n.tagName.includes(":") ? n.tagName.split(":").pop() : n.tagName;
      if (local === localName) out.push(n);
      for (let c = n.firstChild; c; c = c.nextSibling) walk(c);
    }
  };
  for (let c = node.firstChild; c; c = c.nextSibling) walk(c);
  if (node.nodeType === 1) {
    const local = node.tagName.includes(":") ? node.tagName.split(":").pop() : node.tagName;
    if (local === localName) out.unshift(node);
  }
  return out;
}

export function findFirst(node, localName) {
  return findAll(node, localName)[0] ?? null;
}

/** Direct element children of `node`, optionally filtered by local name. */
export function children(node, localName = null) {
  const out = [];
  for (let c = node.firstChild; c; c = c.nextSibling) {
    if (c.nodeType !== 1) continue;
    if (localName) {
      const local = c.tagName.includes(":") ? c.tagName.split(":").pop() : c.tagName;
      if (local !== localName) continue;
    }
    out.push(c);
  }
  return out;
}

/** An attribute by local name, ignoring prefix (r:embed, r:id, w:val, ...). */
export function attr(node, localName) {
  if (!node || !node.attributes) return null;
  for (let i = 0; i < node.attributes.length; i++) {
    const a = node.attributes[i];
    const local = a.name.includes(":") ? a.name.split(":").pop() : a.name;
    if (local === localName) return a.value;
  }
  return null;
}

/** Concatenated text of every <a:t> / <w:t> descendant. */
export function textOf(node, localName = "t") {
  return findAll(node, localName)
    .map((t) => (t.textContent ?? ""))
    .join("");
}

/** Parse an OOXML .rels part into { rId: {target, type} }. */
export function parseRels(doc) {
  const rels = {};
  for (const rel of findAll(doc, "Relationship")) {
    const id = attr(rel, "Id");
    if (!id) continue;
    rels[id] = { target: attr(rel, "Target"), type: attr(rel, "Type") || "" };
  }
  return rels;
}

/**
 * Resolve a relationship target to a package part path.
 * e.g. ("../media/image1.png", "ppt/slides/slide1.xml") -> "ppt/media/image1.png"
 */
export function resolveTarget(target, sourcePart) {
  if (!target) return null;
  if (target.startsWith("/")) return target.slice(1);
  const dir = sourcePart.split("/").slice(0, -1);
  const parts = target.split("/");
  for (const p of parts) {
    if (p === "." || p === "") continue;
    if (p === "..") dir.pop();
    else dir.push(p);
  }
  return dir.join("/");
}

/** Read <a:off>/<a:ext> under a shape into inches, or null when absent. */
export function geometryOf(shape) {
  const xfrm = findFirst(shape, "xfrm");
  if (!xfrm) return null;
  const off = findFirst(xfrm, "off");
  const ext = findFirst(xfrm, "ext");
  if (!off || !ext) return null;
  const round2 = (v) => Math.round((v / EMU_PER_INCH) * 100) / 100;
  return {
    x_in: round2(parseInt(attr(off, "x") || "0", 10)),
    y_in: round2(parseInt(attr(off, "y") || "0", 10)),
    w_in: round2(parseInt(attr(ext, "cx") || "0", 10)),
    h_in: round2(parseInt(attr(ext, "cy") || "0", 10)),
  };
}
