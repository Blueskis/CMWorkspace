"""Shared document-order heading-stack walker for .docx and .pptx source documents.

Both map_source.py (source_map.json) and extract_assets.py (asset_index.json) walk the
same document and need to land on the *same* section_id at the same position — an image
between two headings has to resolve to the section that map_source.py already gave that
span. Two independent heading-stack implementations could drift silently; this is the one
both import.

Stdlib only.
"""

import re

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
WNS = {"w": W_NS, "a": A_NS}
PNS = {"p": P_NS, "a": A_NS}

HEADING_STYLE_RE = re.compile(r"^Heading\s*([0-9]+)$", re.IGNORECASE)
CLAUSE_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")


class HeadingStack:
    """Tracks the current heading path and assigns the same section_id scheme
    map_source.py uses: the clause number when the heading states one (stable across
    runs and across scripts), otherwise a per-document sequential '#sN'."""

    def __init__(self, document_id):
        self.document_id = document_id
        self._stack = []  # list of (level, title, section_id)
        self._counter = 0
        self._opened = False

    def _new_section_id(self, clause_number):
        if clause_number:
            return f"{self.document_id}#{clause_number}"
        self._counter += 1
        return f"{self.document_id}#s{self._counter}"

    def open_heading(self, level, title, clause_number=None):
        while self._stack and self._stack[-1][0] >= level:
            self._stack.pop()
        section_id = self._new_section_id(clause_number)
        self._stack.append((level, title, section_id))
        self._opened = True
        return section_id

    def ensure_root(self, title="(document start)"):
        if not self._opened:
            self.open_heading(1, title)

    @property
    def current_section_id(self):
        self.ensure_root()
        return self._stack[-1][2]

    @property
    def current_title(self):
        self.ensure_root()
        return self._stack[-1][1]

    @property
    def current_section_path(self):
        self.ensure_root()
        return " > ".join(t for _, t, _ in self._stack)


def docx_heading_from_paragraph(p_elem):
    """Return (level, title, clause_number) if p_elem is a heading paragraph, else None."""
    pStyle = p_elem.find(".//w:pStyle", WNS)
    style_val = pStyle.get(f"{{{W_NS}}}val") if pStyle is not None else None
    text = "".join(t.text or "" for t in p_elem.iterfind(".//w:t", WNS)).strip()
    if style_val == "Title":
        return (1, text or "(untitled)", None)
    m = HEADING_STYLE_RE.match(style_val or "")
    if not m:
        return None
    clause = None
    cm = CLAUSE_RE.match(text)
    if cm:
        clause = cm.group(1)
    return (int(m.group(1)), text or "(untitled)", clause)


def docx_paragraph_text(p_elem):
    return "".join(t.text or "" for t in p_elem.iterfind(".//w:t", WNS)).strip()
