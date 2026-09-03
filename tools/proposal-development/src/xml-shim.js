"use strict";

/* =================================================================
   A minimal XML DOM, for Node's test environment only.

   The browser artifact always uses the real DOMParser; this module
   exists purely so the same ooxml-read.js can run under `node:test`
   without an npm dependency. It implements just enough of the DOM
   surface ooxml-read.js actually calls: getElementsByTagNameNS (by
   local name only — OOXML parts use consistent, undisputed prefixes,
   so tracking full namespace URIs adds complexity without adding
   correctness here), getAttribute, textContent, localName, tagName,
   childNodes, and documentElement.
   ================================================================= */

function decodeEntities(s) {
  return s
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'")
    .replace(/&amp;/g, "&");
}

class ShimElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.localName = tagName.includes(":") ? tagName.split(":").pop() : tagName;
    this.attrs = new Map();
    this.childNodes = [];
    this.nodeType = 1;
  }
  getAttribute(name) {
    if (this.attrs.has(name)) return this.attrs.get(name);
    const local = name.includes(":") ? name.split(":").pop() : name;
    for (const [k, v] of this.attrs) {
      if (k === local || k.endsWith(":" + local)) return v;
    }
    return null;
  }
  get textContent() {
    let out = "";
    for (const child of this.childNodes) {
      out += child.nodeType === 3 ? child.data : child.textContent;
    }
    return out;
  }
  getElementsByTagNameNS(_ns, localName) {
    const out = [];
    const walk = node => {
      for (const child of node.childNodes) {
        if (child.nodeType === 1) {
          if (child.localName === localName) out.push(child);
          walk(child);
        }
      }
    };
    walk(this);
    return out;
  }
  getElementsByTagName(name) {
    const local = name.includes(":") ? name.split(":").pop() : name;
    return this.getElementsByTagNameNS(null, local);
  }
}

class ShimText {
  constructor(data) {
    this.data = data;
    this.nodeType = 3;
  }
}

class ShimDocument {
  constructor() {
    this.documentElement = null;
    this.childNodes = [];
  }
  getElementsByTagNameNS(ns, localName) {
    return this.documentElement
      ? [this.documentElement, ...this.documentElement.getElementsByTagNameNS(ns, localName)]
        .filter(el => el.localName === localName)
      : [];
  }
  getElementsByTagName(name) {
    const local = name.includes(":") ? name.split(":").pop() : name;
    return this.getElementsByTagNameNS(null, local);
  }
}

const ATTR_RE = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*"([^"]*)"|([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*'([^']*)'/g;

function parseAttrs(el, attrString) {
  ATTR_RE.lastIndex = 0;
  let m;
  while ((m = ATTR_RE.exec(attrString))) {
    const name = m[1] || m[3];
    const value = decodeEntities(m[2] !== undefined ? m[2] : m[4]);
    el.attrs.set(name, value);
  }
}

/* Tokenizing recursive-descent parser: strips the XML declaration,
   comments, and CDATA are not expected in OOXML parts (none used
   here), then walks tags with a stack. */
function parseFromString(xmlText) {
  const doc = new ShimDocument();
  const stack = [doc];
  let i = 0;
  const len = xmlText.length;

  while (i < len) {
    const lt = xmlText.indexOf("<", i);
    if (lt < 0) break;

    if (lt > i) {
      const text = xmlText.slice(i, lt);
      if (text.trim()) stack[stack.length - 1].childNodes.push(new ShimText(decodeEntities(text)));
    }

    if (xmlText.startsWith("<?", lt)) {
      i = xmlText.indexOf("?>", lt) + 2;
      continue;
    }
    if (xmlText.startsWith("<!--", lt)) {
      i = xmlText.indexOf("-->", lt) + 3;
      continue;
    }
    if (xmlText.startsWith("<![CDATA[", lt)) {
      const end = xmlText.indexOf("]]>", lt);
      const data = xmlText.slice(lt + 9, end);
      stack[stack.length - 1].childNodes.push(new ShimText(data));
      i = end + 3;
      continue;
    }
    if (xmlText.startsWith("</", lt)) {
      const end = xmlText.indexOf(">", lt);
      stack.pop();
      i = end + 1;
      continue;
    }

    const end = xmlText.indexOf(">", lt);
    if (end < 0) break;
    let tagBody = xmlText.slice(lt + 1, end);
    const selfClosing = tagBody.endsWith("/");
    if (selfClosing) tagBody = tagBody.slice(0, -1);

    const spaceAt = tagBody.search(/\s/);
    const tagName = spaceAt < 0 ? tagBody : tagBody.slice(0, spaceAt);
    const attrString = spaceAt < 0 ? "" : tagBody.slice(spaceAt + 1);

    const el = new ShimElement(tagName);
    parseAttrs(el, attrString);
    stack[stack.length - 1].childNodes.push(el);
    if (!doc.documentElement) doc.documentElement = el;
    if (!selfClosing) stack.push(el);

    i = end + 1;
  }

  return doc;
}

class DOMParser {
  parseFromString(text) {
    return parseFromString(text);
  }
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { DOMParser, parseFromString };
}
