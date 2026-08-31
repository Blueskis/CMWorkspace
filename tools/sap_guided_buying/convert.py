"""Turn SAP DITA-generated topic HTML into an ordered list of simple blocks.

The blocks are deliberately dumb so that build_docx.py stays readable:

  {"kind": "heading",  "level": int, "text": str}
  {"kind": "para",     "runs": [...], "style": str, "indent": int}
  {"kind": "list_item","runs": [...], "ordered": bool, "indent": int, "number": int|None}
  {"kind": "table",    "rows": [[cell_text, ...]], "has_header": bool}
  {"kind": "caption",  "text": str}

A run is {"text": str, "bold": bool, "italic": bool, "code": bool}.
"""

import html
import re
from html.parser import HTMLParser

VOID = {"br", "img", "meta", "link", "col", "hr", "input"}
SKIP = {"script", "style", "head", "title"}

BOLD_TAGS = {"strong", "b", "th"}
ITALIC_TAGS = {"em", "i", "dfn", "var", "cite"}
CODE_TAGS = {"kbd", "samp", "code", "tt", "pre"}

BOLD_CLASSES = ("uicontrol", "menucascade", "wintitle", "parmname")
ITALIC_CLASSES = ("emphasis", "varname")
CODE_CLASSES = ("filepath", "userinput", "systemoutput", "codeph", "apiname")

BLOCK_TAGS = {"p", "div", "section", "aside", "ul", "ol", "li", "table", "tr",
              "h1", "h2", "h3", "h4", "h5", "h6", "dl", "dt", "dd", "figure"}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []
        self.parent = parent

    @property
    def cls(self):
        return self.attrs.get("class", "")

    def find_first(self, tag, cls_contains=None):
        for node in self.walk():
            if isinstance(node, Node) and node.tag == tag:
                if cls_contains is None or cls_contains in node.cls:
                    return node
        return None

    def walk(self):
        for child in self.children:
            yield child
            if isinstance(child, Node):
                yield from child.walk()


class DomBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skipping += 1
            return
        if self.skipping:
            return
        node = Node(tag, dict(attrs), self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        if self.skipping or tag in SKIP:
            return
        self.cur.children.append(Node(tag, dict(attrs), self.cur))

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skipping = max(0, self.skipping - 1)
            return
        if self.skipping or tag in VOID:
            return
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        if not self.skipping and data:
            self.cur.children.append(data)


def parse(body_html):
    builder = DomBuilder()
    builder.feed(body_html)
    page = builder.root.find_first("div", "page ") or builder.root.find_first("body")
    return page or builder.root


# --- inline text ------------------------------------------------------------

def _style_for(node, style):
    bold, italic, code = style
    cls = node.cls
    bold = bold or node.tag in BOLD_TAGS or any(c in cls for c in BOLD_CLASSES)
    italic = italic or node.tag in ITALIC_TAGS or any(c in cls for c in ITALIC_CLASSES)
    code = code or node.tag in CODE_TAGS or any(c in cls for c in CODE_CLASSES)
    return bold, italic, code


def collect_runs(node, style=(False, False, False), out=None, resolve_link=None):
    """Flatten a subtree into styled runs, ignoring block structure."""
    out = [] if out is None else out
    for child in node.children:
        if isinstance(child, str):
            text = re.sub(r"\s+", " ", child)
            if text:
                out.append({"text": text, "bold": style[0], "italic": style[1], "code": style[2]})
            continue
        if child.tag == "br":
            out.append({"text": " ", "bold": False, "italic": False, "code": False})
            continue
        if child.tag == "img":
            continue
        if "SAP-icons" in child.cls:
            continue  # icon glyphs from a private font render as tofu
        collect_runs(child, _style_for(child, style), out, resolve_link)
        if child.tag == "a" and resolve_link:
            suffix = resolve_link(child)
            if suffix:
                out.append({"text": suffix, "bold": False, "italic": False, "code": False})
    return out


def runs_text(runs):
    return "".join(r["text"] for r in runs)


def tidy(runs):
    """Merge adjacent same-styled runs and trim the ends."""
    merged = []
    for run in runs:
        if merged and all(merged[-1][k] == run[k] for k in ("bold", "italic", "code")):
            merged[-1]["text"] += run["text"]
        else:
            merged.append(dict(run))
    while merged and not merged[0]["text"].strip():
        merged.pop(0)
    while merged and not merged[-1]["text"].strip():
        merged.pop()
    if merged:
        merged[0]["text"] = merged[0]["text"].lstrip()
        merged[-1]["text"] = merged[-1]["text"].rstrip()
    for run in merged:
        # icon glyphs were dropped above; clear the empty brackets they leave behind
        run["text"] = re.sub(r"\(\s*\)|\[\s*\]", "", run["text"])
        run["text"] = re.sub(r" {2,}", " ", run["text"])
    for prev, run in zip(merged, merged[1:]):
        # runs carry their own styling, so a doubled space can straddle two of them
        if prev["text"].endswith(" "):
            run["text"] = run["text"].lstrip(" ")
    return [r for r in merged if r["text"]]


# --- block walking ----------------------------------------------------------

NOTE_CLASSES = ("note", "caution", "warning", "tip", "important", "restriction", "remember")


class Converter:
    def __init__(self, resolve_link=None):
        self.resolve_link = resolve_link
        self.blocks = []

    def emit_para(self, runs, style="body", indent=0):
        runs = tidy(runs)
        if runs:
            self.blocks.append({"kind": "para", "runs": runs, "style": style, "indent": indent})

    def convert(self, node):
        self._walk(node, indent=0)
        return self.blocks

    def _walk(self, node, indent):
        """Walk children, gathering runs of inline siblings into single paragraphs.

        SAP's generated HTML often leaves a sentence as bare text and inline spans
        between two block elements; emitting each piece separately would shred it.
        """
        buffer = []

        def flush():
            if not buffer:
                return
            holder = Node("div")
            holder.children = list(buffer)
            self.emit_para(collect_runs(holder, resolve_link=self.resolve_link), indent=indent)
            buffer.clear()

        for child in node.children:
            if isinstance(child, str):
                if child.strip():
                    buffer.append(child)
                continue
            if child.tag not in BLOCK_TAGS and child.tag != "img":
                buffer.append(child)
                continue
            flush()
            self._node(child, indent)
        flush()

    def _node(self, node, indent):
        tag, cls = node.tag, node.cls

        if tag == "img":
            alt = (node.attrs.get("alt") or "").strip()
            if alt:
                self.blocks.append({"kind": "caption", "text": alt})
            return

        if tag == "h1":
            return  # the topic title is supplied by the TOC, not the body

        if tag in ("h2", "h3", "h4"):
            text = runs_text(collect_runs(node)).strip()
            if text:
                self.emit_para([{"text": text, "bold": True, "italic": False, "code": False}],
                               style="label", indent=indent)
            return

        if tag == "aside" or (tag == "div" and any(f"note {c}" == cls or cls == c
                                                   for c in NOTE_CLASSES)):
            self._note(node, indent)
            return

        if tag == "table":
            self._table(node)
            return

        if tag in ("ul", "ol"):
            self._list(node, ordered=(tag == "ol"), indent=indent)
            return

        if tag == "dl":
            for item in node.children:
                if not isinstance(item, Node):
                    continue
                if item.tag == "dt":
                    self.emit_para(
                        [dict(r, bold=True) for r in collect_runs(item, resolve_link=self.resolve_link)],
                        indent=indent)
                elif item.tag == "dd":
                    self._walk(item, indent + 1)
            return

        if tag == "pre":
            text = runs_text(collect_runs(node)).strip()
            if text:
                self.emit_para([{"text": text, "bold": False, "italic": False, "code": True}],
                               style="code", indent=indent)
            return

        if tag == "p" or (tag in ("div", "span") and not self._has_block_child(node)):
            style = "shortdesc" if "shortdesc" in cls else "body"
            self.emit_para(collect_runs(node, resolve_link=self.resolve_link), style, indent)
            return

        # container: recurse, but keep "related-links" grouped under a label
        if "related-links" in cls:
            self.emit_para([{"text": "Related Information", "bold": True,
                             "italic": False, "code": False}], style="label", indent=indent)
        self._walk(node, indent)

    @staticmethod
    def _has_block_child(node):
        return any(isinstance(c, Node) and c.tag in BLOCK_TAGS for c in node.children)

    def _note(self, node, indent):
        title_node = node.find_first("div", "title")
        label = runs_text(collect_runs(title_node)).strip() if title_node else "Note"
        parts = []
        for child in node.children:
            if child is title_node:
                continue
            if isinstance(child, Node) and "title" in child.cls and not parts:
                continue
            parts.append(child)
        holder = Node("div")
        holder.children = parts
        body = tidy(collect_runs(holder, resolve_link=self.resolve_link))
        if not body:
            return
        runs = [{"text": f"{label}: ", "bold": True, "italic": False, "code": False}] + body
        self.emit_para(runs, style="note", indent=indent)

    def _list(self, node, ordered, indent):
        number = 0
        for item in node.children:
            if not isinstance(item, Node) or item.tag != "li":
                continue
            number += 1
            lead, rest = [], []
            for child in item.children:
                if isinstance(child, Node) and (
                    child.tag in ("ul", "ol", "table")
                    or "itemgroup" in child.cls
                    or child.tag == "aside"
                    or (child.tag in ("div", "section") and self._has_block_child(child))
                ):
                    rest.append(child)
                else:
                    lead.append(child)
            holder = Node("div")
            holder.children = lead
            runs = tidy(collect_runs(holder, resolve_link=self.resolve_link))
            self.blocks.append({
                "kind": "list_item", "runs": runs, "ordered": ordered,
                "indent": indent, "number": number if ordered else None,
            })
            for child in rest:
                self._node(child, indent + 1)

    def _table(self, node):
        rows, has_header = [], False
        for tr in node.walk():
            if not isinstance(tr, Node) or tr.tag != "tr":
                continue
            cells = [c for c in tr.children if isinstance(c, Node) and c.tag in ("td", "th")]
            if not cells:
                continue
            if any(c.tag == "th" for c in cells) and not rows:
                has_header = True
            rows.append([runs_text(tidy(collect_runs(c, resolve_link=self.resolve_link))).strip()
                         for c in cells])
        if not rows:
            return
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        self.blocks.append({"kind": "table", "rows": rows, "has_header": has_header})


def convert_topic(body_html, resolve_link=None):
    return Converter(resolve_link).convert(parse(body_html))


def blocks_to_text(blocks):
    """Plain-text rendering, used by the verification pass."""
    lines = []
    for b in blocks:
        if b["kind"] == "table":
            lines += [" | ".join(r) for r in b["rows"]]
        elif b["kind"] == "caption":
            lines.append(b["text"])
        else:
            prefix = "  " * b.get("indent", 0)
            if b["kind"] == "list_item":
                prefix += f"{b['number']}. " if b["ordered"] else "- "
            lines.append(prefix + runs_text(b["runs"]))
    return "\n".join(lines)
