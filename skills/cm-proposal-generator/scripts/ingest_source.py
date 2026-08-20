#!/usr/bin/env python3
"""Draft a knowledge-bank entry from a past deck, tender response, or method document.

    python ingest_source.py past-bids/healthcare-erp-2025.pptx \\
        -o proposal-assets/knowledge-bank/methodology/healthcare-phasing.md
    python ingest_source.py methodology/adoption-approach.docx --tags erp,public-sector

Reads .pptx, .docx, .md and .txt and writes a Markdown entry with frontmatter filled in
as far as it honestly can. It is an **extractor and a scaffold, not an author**: it never
summarises, never rewrites, and never fills in a field it cannot know.

## The three fields it deliberately gets wrong on purpose

`clearance` defaults to **internal-only**, so a freshly ingested past bid cannot be
retrieved into a live proposal until somebody decides it may be. An entry that arrives
retrievable is an entry that reaches a client before anyone has checked whether the last
client agreed to be named.

`metrics_verified` is always **false** on ingest. The numbers in a past deck were true of
that engagement on the day it was written; carrying them into a new bid is a claim, and
claims get checked by the person making them, not by a text extractor.

`bid.outcome` is left as **unknown** unless told. A past proposal's language is worth
reusing only alongside whether it won — and the file itself never says.

## After running it

The knowledge-bank guide asks for one idea per entry, because Stage 4 retrieves entries
whole. A whole past deck is many ideas, so the draft this writes is usually a *source to
split*, not a finished entry: cut it into a methodology entry, a case study, a set of
credentials. The script says so on every run rather than pretending otherwise.

Stdlib only — .pptx and .docx are both ZIPs of XML, so neither needs a library to read.
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from triage_rfp import LEXICON  # noqa: E402  (shared CM vocabulary)

A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P_NS = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

# Where extracted content can be filed. Past tenders and past decks are not among them:
# those are documents and live in Airtable. What comes *out* of one is filed by what it
# is — a phase model is methodology, an outcome story is a case study.
SECTIONS = ("methodology", "case-studies", "credentials", "team", "commercials",
            "boilerplate")

# Placeholder types that hold slide furniture rather than anything worth reusing.
FURNITURE = {"ftr", "sldNum", "dt"}


def slug(value):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(value).lower())).strip("-")


# --- extraction ------------------------------------------------------------


def slide_order(zf):
    """Slide parts in presentation order, not zip order (which is alphabetical:
    slide10 sorts before slide2, and the entry comes out shuffled)."""
    try:
        rels = ET.fromstring(zf.read("ppt/_rels/presentation.xml.rels"))
        pres = ET.fromstring(zf.read("ppt/presentation.xml"))
    except KeyError:
        return sorted(n for n in zf.namelist() if n.startswith("ppt/slides/slide"))

    targets = {rel.get("Id"): rel.get("Target") for rel in rels}
    order = []
    for sld in pres.iter(f"{P_NS}sldId"):
        target = targets.get(sld.get(f"{R_NS}id"))
        if target:
            order.append("ppt/" + target.lstrip("/").replace("../", ""))
    return order or sorted(n for n in zf.namelist() if n.startswith("ppt/slides/slide"))


def shape_lines(shape):
    """Each paragraph of a shape as one line, preserving the author's line breaks."""
    out = []
    for para in shape.iter(f"{A_NS}p"):
        text = "".join(t.text or "" for t in para.iter(f"{A_NS}t")).strip()
        if text:
            out.append(text)
    return out


def read_pptx(path):
    """A deck as [(slide number, title, [lines], notes)]."""
    slides = []
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        for i, part in enumerate(slide_order(zf), 1):
            if part not in names:
                continue
            root = ET.fromstring(zf.read(part))
            title, lines = None, []
            for shape in root.iter(f"{P_NS}sp"):
                ph = shape.find(f".//{P_NS}nvSpPr/{P_NS}nvPr/{P_NS}ph")
                # Footers, slide numbers and dates are furniture, not content. Every slide
                # carries them, so extracting them puts "Commercial in confidence · 7" in
                # the body of every entry a deck produces.
                if ph is not None and (ph.get("type") or "") in FURNITURE:
                    continue
                text = shape_lines(shape)
                if not text:
                    continue
                if title is None and ph is not None and \
                        (ph.get("type") or "").endswith(("title", "Title")):
                    title = text[0]
                    lines += text[1:]
                else:
                    lines += text
            for frame in root.iter(f"{P_NS}graphicFrame"):
                for row in frame.iter(f"{A_NS}tr"):
                    cells = [" ".join(t.text or "" for t in cell.iter(f"{A_NS}t")).strip()
                             for cell in row.iter(f"{A_NS}tc")]
                    if any(cells):
                        lines.append(" | ".join(cells))

            notes_part = part.replace("ppt/slides/", "ppt/notesSlides/notesSlide")
            notes_part = re.sub(r"notesSlideslide", "notesSlide", notes_part)
            notes = ""
            if notes_part in names:
                # Per paragraph, not per run: the author's line breaks are the structure a
                # tag block is written in, and joining runs with spaces destroys them.
                notes = "\n".join(
                    line for line in shape_lines(ET.fromstring(zf.read(notes_part)))
                ).strip()
            slides.append((i, title, lines, notes))
    return slides


def read_docx(path):
    """A Word document as [(heading level or None, text)]."""
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    blocks = []
    for para in root.iter(f"{W_NS}p"):
        text = "".join(t.text or "" for t in para.iter(f"{W_NS}t")).strip()
        if not text:
            continue
        style_el = para.find(f".//{W_NS}pPr/{W_NS}pStyle")
        style = (style_el.get(f"{W_NS}val") if style_el is not None else "") or ""
        match = re.fullmatch(r"[Hh]eading(\d)", style)
        blocks.append((int(match.group(1)) if match else None, text))
    return blocks


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


# --- entry drafting --------------------------------------------------------


def suggest_tags(text, limit=10):
    """Tags from the CM vocabulary actually present in the source.

    A suggestion, not a decision: retrieval matches tags literally, so the practitioner
    still has to align these with the vocabulary the rest of the bank already uses.
    """
    lowered = text.lower()
    found = []
    for weight in sorted(LEXICON, reverse=True):
        for term in LEXICON[weight]:
            if weight >= 3 and term in lowered:
                found.append(slug(term))
    return sorted(dict.fromkeys(found))[:limit]


def body_from_pptx(slides):
    lines = []
    for number, title, content, notes in slides:
        lines.append(f"## Slide {number}" + (f" — {title}" if title else ""))
        lines.append("")
        lines += [f"- {line}" for line in content] or ["_(no text on this slide)_"]
        if notes:
            lines += ["", f"> Speaker notes: {notes}"]
        lines.append("")
    return "\n".join(lines)


def body_from_docx(blocks):
    lines = []
    for level, text in blocks:
        if level:
            lines += ["", "#" * min(level + 1, 6) + f" {text}", ""]
        else:
            lines.append(text)
            lines.append("")
    return "\n".join(lines).strip()


def frontmatter(entry_id, title, tags, section, source, args):
    fields = [
        f"id: {entry_id}",
        f"title: {title}",
        f"tags: [{', '.join(tags) if tags else 'REVIEW-add-tags'}]",
        # Deliberately the most restrictive value — see the module docstring.
        f"clearance: {args.clearance}",
        f"last_reviewed: {date.today().isoformat()}",
        "metrics_verified: false",
        f"source_document: {source}",
    ]
    if args.owner:
        fields.append(f"owner: {args.owner}")
    if args.outcome != "unknown" or args.client_ref:
        fields += [
            "bid:",
            f"  client_ref: {args.client_ref or 'REVIEW-set-client-or-anonymised-handle'}",
            f"  outcome: {args.outcome}",
        ]
    return "---\n" + "\n".join(fields) + "\n---\n"


# --- golden deck -----------------------------------------------------------

NOTE_KEYS = "section|tags|clearance|metrics|outcome|client|title"
TAG_LINE = re.compile(rf"^\s*({NOTE_KEYS})\s*:\s*(.+)$", re.I)
NEXT_KEY = re.compile(rf"\s+(?:{NOTE_KEYS})\s*:", re.I)
VERIFIED = {"verified", "true", "yes", "checked"}


def parse_note_tags(notes):
    """The `key: value` block a curator leaves in a slide's speaker notes.

    Notes are the right place for this: invisible when presenting, per-slide, and already
    extracted. Lines that are not recognised keys are left alone, so a curator can keep
    writing ordinary speaker notes around the block.
    """
    found = {}
    for line in str(notes or "").replace("\r", "\n").split("\n"):
        match = TAG_LINE.match(line)
        if not match:
            continue
        value = match.group(2)
        cut = NEXT_KEY.search(value)
        found[match.group(1).lower()] = value[:cut.start()].strip() if cut else value.strip()
    return found


def slide_entry(number, title, lines, notes, args):
    """One curated slide as one entry, or a reason it cannot be.

    The curator supplies what extraction cannot know. Where they said nothing, the
    restrictive default stands rather than a guess — an entry that reaches a client deck
    because a field was left blank is the failure these defaults exist to prevent.
    """
    meta = parse_note_tags(notes)
    body = "\n\n".join(lines).strip()
    title = meta.get("title") or title or f"Slide {number}"

    section = (meta.get("section") or "").strip().lower()
    if section not in SECTIONS:
        return None, (f"slide {number} ({title[:40]}): "
                      + (f"section '{section}' is not one of {', '.join(SECTIONS)}"
                         if section else "no `section:` in its speaker notes"))
    if not body:
        return None, f"slide {number} ({title[:40]}): no body text to put on a slide"

    tags = [t.strip().lower() for t in (meta.get("tags") or "").replace(";", ",").split(",")
            if t.strip()]
    if not tags:
        tags = suggest_tags(f"{title} {body}")
    clearance = (meta.get("clearance") or "").strip().lower()
    outcome = (meta.get("outcome") or "").strip().lower()

    return {
        "id": slug(title)[:48] or f"slide-{number}",
        "title": title,
        "section": section,
        "tags": tags,
        "clearance": clearance if clearance in ("named", "anonymised", "internal-only")
                     else args.clearance,
        "metrics_verified": (meta.get("metrics") or "").strip().lower() in VERIFIED,
        "outcome": outcome if outcome in ("won", "lost", "no-bid", "withdrawn", "pending",
                                          "unknown") else args.outcome,
        "client_ref": meta.get("client") or args.client_ref,
        "body": body,
    }, None


def write_slide_entry(entry, bank_root, source, owner):
    lines = [
        f"id: {entry['id']}",
        f"title: {entry['title']}",
        f"tags: [{', '.join(entry['tags']) if entry['tags'] else 'REVIEW-add-tags'}]",
        f"clearance: {entry['clearance']}",
        f"last_reviewed: {date.today().isoformat()}",
        f"metrics_verified: {'true' if entry['metrics_verified'] else 'false'}",
        f"source_document: {source}",
    ]
    if owner:
        lines.append(f"owner: {owner}")
    if entry["outcome"] != "unknown" or entry["client_ref"]:
        lines += ["bid:",
                  f"  client_ref: {entry['client_ref'] or 'REVIEW-set-client-or-anonymised-handle'}",
                  f"  outcome: {entry['outcome']}"]

    out = bank_root / entry["section"] / f"{entry['id']}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("---\n" + "\n".join(lines) + "\n---\n\n" + entry["body"] + "\n",
                   encoding="utf-8")
    return out


def ingest_golden_deck(args):
    """A curated deck, one entry per slide.

    Splitting is the part extraction cannot do — a case study spanning three slides needs
    merging and nothing mechanical can tell. A deck whose slides were chosen one by one has
    already had that done by the person who chose them, so here one slide really is one
    entry.
    """
    slides = read_pptx(args.source)
    if not slides:
        sys.exit(f"no slides found in {args.source}")

    written, skipped, seen = [], [], set()
    for number, title, lines, notes in slides:
        entry, problem = slide_entry(number, title, lines, notes, args)
        if problem:
            skipped.append(problem)
            continue
        while entry["id"] in seen:
            entry["id"] += "-2"
        seen.add(entry["id"])
        written.append((entry, write_slide_entry(entry, args.out, args.source, args.owner)))

    print(f"{len(written)} entr{'y' if len(written) == 1 else 'ies'} written from "
          f"{len(slides)} slide(s) in {args.source.name}")
    for entry, path in written:
        flags = [] if entry["clearance"] != "internal-only" else ["internal-only"]
        if not entry["metrics_verified"]:
            flags.append("metrics unverified")
        print(f"  {entry['section']:<12} {path.name}"
              + (f"   [{', '.join(flags)}]" if flags else ""))
    for problem in skipped:
        print(f"  SKIPPED {problem}", file=sys.stderr)

    restricted = sum(1 for e, _ in written if e["clearance"] == "internal-only")
    if restricted:
        print(f"\n{restricted} of {len(written)} are internal-only and excluded from "
              f"retrieval.\nAdd `clearance:` to those slides' notes, or set it in the "
              f"frontmatter once someone has decided.")
    print("Then: python index_kb.py proposal-assets/knowledge-bank -o kb_index.json, "
          "and rebuild\nthe intake page so the entries reach a deck.")
    return 1 if skipped else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path, help=".pptx, .docx, .md or .txt")
    ap.add_argument("-o", "--out", type=Path,
                    help="destination .md (default: alongside, named from the source)")
    ap.add_argument("--id", help="entry id (default: slug of the filename)")
    ap.add_argument("--title", help="entry title (default: the filename, humanised)")
    ap.add_argument("--tags", default="", help="comma-separated tags; merged with the "
                                               "vocabulary found in the source")
    ap.add_argument("--section", choices=SECTIONS,
                    help="knowledge-bank section (default: inferred from --out's folder)")
    ap.add_argument("--clearance", choices=["named", "anonymised", "internal-only"],
                    default="internal-only",
                    help="default internal-only — an ingested source is not cleared for "
                         "a client-facing deck until somebody says it is")
    ap.add_argument("--outcome",
                    choices=["won", "lost", "no-bid", "withdrawn", "pending", "unknown"],
                    default="unknown",
                    help="how the bid this came from went — carry it across from the "
                         "Airtable record rather than losing it in extraction")
    ap.add_argument("--client-ref", help="client name or anonymised handle")
    ap.add_argument("--owner", help="who maintains this entry")
    ap.add_argument("--golden-deck", action="store_true",
                    help="a curated deck: write one entry per slide into the bank, taking "
                         "section, tags, clearance, metrics and outcome from each slide's "
                         "speaker notes. -o is the bank root, not a file.")
    args = ap.parse_args()

    if args.golden_deck:
        if args.source.suffix.lower() != ".pptx":
            sys.exit("--golden-deck reads a .pptx")
        args.out = args.out or Path("proposal-assets/knowledge-bank")
        return ingest_golden_deck(args)

    if not args.source.is_file():
        sys.exit(f"source not found: {args.source}")

    suffix = args.source.suffix.lower()
    if suffix == ".pptx":
        slides = read_pptx(args.source)
        if not slides:
            sys.exit(f"no slides found in {args.source}")
        body = body_from_pptx(slides)
        detail = f"{len(slides)} slide(s)"
    elif suffix == ".docx":
        blocks = read_docx(args.source)
        if not blocks:
            sys.exit(f"no text found in {args.source}")
        body = body_from_docx(blocks)
        detail = f"{len(blocks)} paragraph(s)"
    elif suffix in (".md", ".txt"):
        body = read_text(args.source).strip()
        detail = f"{len(body.split())} word(s)"
    elif suffix == ".pdf":
        sys.exit("PDF text extraction needs the `pdf` skill — extract to .txt first, "
                 "then run this on the .txt.")
    else:
        sys.exit(f"unsupported source type '{suffix}' — use .pptx, .docx, .md or .txt")

    out = args.out or args.source.with_suffix(".md")
    section = args.section or (out.parent.name if out.parent.name in SECTIONS else None)
    entry_id = args.id or slug(args.source.stem)
    title = args.title or args.source.stem.replace("-", " ").replace("_", " ").strip()

    manual = [t.strip().lower() for t in args.tags.split(",") if t.strip()]
    tags = sorted(dict.fromkeys(manual + suggest_tags(body)))

    header = frontmatter(entry_id, title, tags, section, args.source, args)
    banner = (
        "<!-- DRAFT — extracted, not written. Before this entry can be used:\n"
        "     1. Split it. The knowledge-bank guide asks for one idea per entry;\n"
        "        a whole deck is several. Retrieval pulls entries whole.\n"
        "     2. Rewrite it as substance, not as pitch copy for the last client.\n"
        "     3. Check every number, then set metrics_verified: true.\n"
        "     4. Decide clearance. It ships as internal-only, which means it is\n"
        "        excluded from retrieval until somebody changes it.\n"
        "     Delete this comment when the entry is genuinely ready. -->\n\n"
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + "\n" + banner + body + "\n", encoding="utf-8")

    print(f"Drafted {out}  ({detail} from {args.source.name})")
    print(f"  section: {section or 'UNSET — move it into a knowledge-bank folder'}"
          f"   clearance: {args.clearance}")
    print(f"  suggested tags: {', '.join(tags) if tags else '(none found — add your own)'}")
    if args.outcome == "unknown":
        print("  bid outcome is 'unknown' — pass --outcome from the Airtable record. "
              "Reusing language from a bid without knowing whether it won is the failure "
              "that field exists to prevent.")
    print("  This is a DRAFT: split it into single-idea entries, verify the numbers, "
          "then re-run index_kb.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
