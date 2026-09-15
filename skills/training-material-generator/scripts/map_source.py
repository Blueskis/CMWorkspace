#!/usr/bin/env python3
"""Build the complete outline of every input document (Stage 0).

    python map_source.py training/<run>/inputs/ -o training/<run>/source_map.json
    python map_source.py fsd.docx addendum.pdf -o source_map.json

This is the inventory Stage 2 plans modules against and Stage 5 audits coverage
against — NOT a retrieval index. Retrieval (index_chunks.py / retrieve_chunks.py)
answers questions you thought to ask; this answers "what does the document actually
contain", so a section nobody thought to search for still shows up and has to be
either taught or explicitly marked training_brief.out_of_scope. Never let top-k
decide what a course covers.

Three input formats, one output schema:

  * .docx — reads word/document.xml, tracking w:pStyle "HeadingN" into a heading
    stack. Tables and figures are attributed to the section they fall under.
  * .pptx (as a *source* document, not a template) — one section per slide, titled
    from its title placeholder.
  * .pdf — needs pre-extracted text. If `<stem>.txt` sits next to the .pdf (the
    pattern the cm-proposal-generator skill's examples/cfs-ch8/ already uses), that
    is read directly. Otherwise this shells out to `pdftotext -layout`; if that
    binary is missing, it prints the pdf skill's own extraction command and exits
    non-zero rather than guessing at layout. Headings are then inferred from clause
    numbering (`5.1.11`) and short, terminal-punctuation-free lines — this is a
    heuristic, and a mis-split PDF section is the first thing to check by hand.

The `classifier` on each section (procedure / reference / narrative / config /
non-functional) is also a heuristic — cheap keyword and structure cues, not a
model call. 'procedure' is the one Stage 5 enforces coverage on, so when in doubt
this errs toward calling a section procedure rather than narrative.

Stdlib only.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from section_walk import (  # noqa: E402
    A_NS, CLAUSE_RE, P_NS, PNS, W_NS, WNS,
    HeadingStack, docx_heading_from_paragraph, docx_paragraph_text,
)

STEP_CUE_RE = re.compile(r"\bstep\s+\d+\b|\b(?:click|select|enter|navigate|choose|submit|approve|reject)\b", re.IGNORECASE)
REFERENCE_CUE_RE = re.compile(r"\bfield\b|\battribute\b|\bcolumn\b|\bdata\s+element\b|\bmandatory\b|\boptional\b", re.IGNORECASE)
CONFIG_CUE_RE = re.compile(r"\bconfigur\w*\b|\bsetting\b|\bparameter\b|\bdefault\s+value\b", re.IGNORECASE)
NONFUNC_CUE_RE = re.compile(r"\bperformance\b|\bavailability\b|\bsecurity\b|\bSLA\b|\bresponse\s+time\b|\baudit\s+log\b", re.IGNORECASE)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "doc"


def classify(title, text, has_numbered_steps):
    """Cheap heuristic. See module docstring — errs toward 'procedure' when ambiguous."""
    probe = f"{title}\n{text[:1500]}"
    if has_numbered_steps or STEP_CUE_RE.search(probe):
        return "procedure"
    if NONFUNC_CUE_RE.search(probe):
        return "non-functional"
    if CONFIG_CUE_RE.search(probe):
        return "config"
    if REFERENCE_CUE_RE.search(probe):
        return "reference"
    return "narrative"


class SectionBuilder:
    """Accumulates section metadata in document order. Wraps the shared HeadingStack
    (lib/section_walk.py) for section_id assignment, so map_source.py and
    extract_assets.py land on identical IDs for the same document position."""

    def __init__(self, document_id):
        self.document_id = document_id
        self.headings = HeadingStack(document_id)
        self.sections = []
        self._by_id = {}
        self._cur = None

    def open_heading(self, level, title, clause_number=None, page=None):
        section_id = self.headings.open_heading(level, title, clause_number=clause_number)
        section = {
            "section_id": section_id,
            "document_id": self.document_id,
            "section_path": self.headings.current_section_path,
            "title": title,
            "level": level,
            "clause_number": clause_number,
            "page_start": page,
            "page_end": page,
            "char_count": 0,
            "figure_count": 0,
            "table_count": 0,
            "_text": "",
            "_has_numbered_steps": False,
        }
        self.sections.append(section)
        self._by_id[section_id] = section
        self._cur = section
        return section

    def ensure_root(self, title="(document start)"):
        if self._cur is None:
            self.open_heading(1, title)

    def add_text(self, text, page=None):
        self.ensure_root()
        self._cur["_text"] += text + "\n"
        self._cur["char_count"] += len(text)
        if page is not None:
            self._cur["page_end"] = page

    def add_figure(self, n=1):
        self.ensure_root()
        self._cur["figure_count"] += n

    def add_table(self, n=1):
        self.ensure_root()
        self._cur["table_count"] += n

    def mark_numbered_step(self):
        self.ensure_root()
        self._cur["_has_numbered_steps"] = True

    def finish(self):
        out = []
        for s in self.sections:
            classifier = classify(s["title"], s["_text"], s["_has_numbered_steps"])
            text = s["_text"].strip()
            s = {k: v for k, v in s.items() if not k.startswith("_")}
            s["classifier"] = classifier
            s["text"] = text
            out.append(s)
        return out


# ---------------------------------------------------------------------------
# .docx
# ---------------------------------------------------------------------------

def parse_docx(path, document_id):
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))

    body = root.find("w:body", WNS)
    if body is None:
        sys.exit(f"{path}: no <w:body> found — is this a valid .docx?")

    sb = SectionBuilder(document_id)

    for child in body:
        tag = child.tag.split("}", 1)[-1]
        if tag == "p":
            heading = docx_heading_from_paragraph(child)
            if heading:
                level, title, clause = heading
                sb.open_heading(level, title, clause_number=clause)
                continue
            numPr = child.find(".//w:numPr", WNS)
            if numPr is not None:
                sb.mark_numbered_step()
            blip_count = len(child.findall(".//a:blip", WNS))
            if blip_count:
                sb.add_figure(blip_count)
            text = docx_paragraph_text(child)
            if text:
                sb.add_text(text)
        elif tag == "tbl":
            sb.add_table(1)
            # Table cell text still counts toward the section's content.
            cell_text = "".join(t.text or "" for t in child.iterfind(".//w:t", WNS))
            if cell_text.strip():
                sb.add_text(cell_text.strip())

    return sb.finish()


# ---------------------------------------------------------------------------
# .pptx (as a source document)
# ---------------------------------------------------------------------------

def parse_pptx(path, document_id):
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(path) as zf:
        names = sorted(
            (n for n in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
            key=lambda n: int(re.search(r"\d+", Path(n).stem).group()),
        )
        sb = SectionBuilder(document_id)
        for i, name in enumerate(names, start=1):
            root = ET.fromstring(zf.read(name))
            title = None
            for sp in root.iterfind(".//p:sp", PNS):
                ph = sp.find(".//p:nvSpPr/p:nvPr/p:ph", PNS)
                if ph is not None and ph.get("type") in ("title", "ctrTitle"):
                    title = "".join(t.text or "" for t in sp.iterfind(".//a:t", PNS)).strip()
                    break
            title = title or f"Slide {i}"
            sb.open_heading(1, title, clause_number=f"slide{i}", page=i)
            body_text = "".join(t.text or "" for t in root.iterfind(".//a:t", PNS))
            if title in body_text:
                body_text = body_text.replace(title, "", 1)
            if body_text.strip():
                sb.add_text(body_text.strip(), page=i)
            fig_count = len(root.findall(".//p:pic", PNS))
            if fig_count:
                sb.add_figure(fig_count)
            table_count = len(root.findall(".//a:tbl", PNS))
            if table_count:
                sb.add_table(table_count)

    return sb.finish()


# ---------------------------------------------------------------------------
# .pdf
# ---------------------------------------------------------------------------

def _pdf_text(path):
    sidecar = path.with_suffix(".txt")
    if sidecar.is_file():
        return sidecar.read_text(encoding="utf-8", errors="replace")
    if shutil.which("pdftotext"):
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            return result.stdout
    sys.exit(
        f"{path}: no pre-extracted text available. Either place a '{sidecar.name}' "
        f"sidecar next to it (the pdf skill's own text extraction, saved to a file), "
        f"or install poppler so 'pdftotext -layout {path} -' works."
    )


def parse_pdf(path, document_id):
    text = _pdf_text(path)
    sb = SectionBuilder(document_id)
    page = 1
    for raw_line in text.splitlines():
        if "\f" in raw_line:
            page += 1
            raw_line = raw_line.replace("\f", "")
        line = raw_line.strip()
        if not line:
            continue
        cm = CLAUSE_RE.match(line)
        is_heading_like = bool(cm) and len(line) < 120 and not line.endswith((".", ",", ";", ":"))
        if is_heading_like:
            clause = cm.group(1)
            level = clause.count(".") + 1
            sb.open_heading(level, cm.group(2).strip(), clause_number=clause, page=page)
            continue
        if re.match(r"^\d+[.)]\s+\S", line):
            sb.mark_numbered_step()
        if re.search(r"\bfigure\s+\d+\b", line, re.IGNORECASE):
            sb.add_figure(1)
        sb.add_text(line, page=page)
    return sb.finish()


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

PARSERS = {".docx": parse_docx, ".pptx": parse_pptx, ".pdf": parse_pdf}


def discover_inputs(paths):
    files = []
    for p in paths:
        if p.is_dir():
            for ext in PARSERS:
                files.extend(sorted(p.glob(f"*{ext}")))
        elif p.suffix.lower() in PARSERS:
            files.append(p)
        else:
            print(f"skipping (unrecognized extension): {p}", file=sys.stderr)
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path, help="Input files and/or a directory containing them")
    ap.add_argument("-o", "--out", type=Path, default=Path("source_map.json"))
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    files = discover_inputs(args.inputs)
    if not files:
        sys.exit("no .docx/.pptx/.pdf inputs found")

    used_ids = set()
    documents, sections = [], []
    for f in files:
        base = slugify(f.stem)
        document_id = base
        n = 2
        while document_id in used_ids:
            document_id = f"{base}-{n}"
            n += 1
        used_ids.add(document_id)

        ext = f.suffix.lower()
        parser = PARSERS[ext]
        print(f"parsing {f} as {document_id} ({ext[1:]})")
        secs = parser(f, document_id)
        sections.extend(secs)
        page_count = max((s["page_end"] or 0) for s in secs) if secs else None
        documents.append({
            "document_id": document_id,
            "filename": f.name,
            "format": ext[1:],
            "page_count": page_count,
        })

    run_id = args.run_id or slugify(documents[0]["filename"].rsplit(".", 1)[0])
    source_map = {"run_id": run_id, "documents": documents, "sections": sections}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(source_map, indent=2), encoding="utf-8")

    by_class = {}
    for s in sections:
        by_class[s["classifier"]] = by_class.get(s["classifier"], 0) + 1
    print(f"\n{len(sections)} sections across {len(documents)} document(s) -> {args.out}")
    for cls, n in sorted(by_class.items()):
        print(f"  {cls:<14} {n}")
    procedure_n = by_class.get("procedure", 0)
    if procedure_n:
        print(f"\n{procedure_n} 'procedure' section(s) — each needs a module or an "
              f"out_of_scope entry in training_brief.json, or Stage 5 will fail the run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
