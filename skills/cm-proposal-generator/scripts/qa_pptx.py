#!/usr/bin/env python3
"""Audit a built .pptx against the template it claims to be built on (Stage 6).

    python qa_pptx.py proposals/<run>/proposal.pptx \\
        --original proposal-assets/templates/pptx-generic/pptx-generic.potx \\
        -o proposals/<run>/qa_pptx.md

`qa_deck.py` audits the plan — coverage and provenance. This audits the *file*, and it
checks the things that are mechanical and therefore should never be done by eye:

1. **Package integrity** — every part is well-formed XML, every relationship resolves to
   a part that exists, every slide is declared in `[Content_Types].xml` and listed in
   `presentation.xml`. A deck that opens on this machine and not on the evaluator's is
   usually a dangling relationship.

2. **Template fidelity** — the master, layouts, theme and fonts are byte-identical to the
   original, and no slide sets a font or a literal colour of its own. This is the check
   that makes "built on the approved template" a fact rather than an intention. It needs
   `--original`; without it the drift scan still runs, but nothing can confirm the
   template parts were not edited.

3. **Overflow** — text measured against the box it sits in. The defect this catches is
   the one nobody sees: PowerPoint clips an overfull placeholder rather than spilling it,
   so a slide loses its last bullet silently.

4. **Leftover scaffolding** — prompt text, `lorem`, `[insert`, `TODO`, `xxx`, and empty
   placeholders that made it into the deck.

Exits non-zero on a fidelity failure or a broken package. Overflow and scaffolding are
reported as warnings — they need a human decision about what to cut.

Stdlib only.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_template import profile_layout  # noqa: E402
from render_pptx import fit_ratio  # noqa: E402

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
PLACEHOLDER_PATTERNS = [
    (re.compile(r"\blorem\b", re.I), "lorem ipsum"),
    (re.compile(r"\[insert", re.I), "[insert …"),
    (re.compile(r"\bTODO\b"), "TODO"),
    (re.compile(r"\bTBC\b|\bTBD\b"), "TBC/TBD"),
    (re.compile(r"\bxxx+\b", re.I), "xxx"),
    (re.compile(r"click to edit", re.I), "template prompt text"),
    (re.compile(r"\bplaceholder\b", re.I), "the word 'placeholder'"),
]
# Gap panels deliberately carry fixed colours — they are review annotations that must
# stay legible on any template. Anything else naming a colour is drift.
GAP_PREFIX = "GAP-marker-"

TEMPLATE_PARTS = ("ppt/slideMasters/", "ppt/slideLayouts/", "ppt/theme/",
                  "ppt/tableStyles.xml")


def load(path):
    with zipfile.ZipFile(path) as zf:
        return {n: zf.read(n) for n in zf.namelist()}


def check_package(parts):
    """Well-formedness, content types, and relationship targets."""
    problems = []

    for name, data in parts.items():
        if name.endswith((".xml", ".rels")):
            try:
                ET.fromstring(data)
            except ET.ParseError as exc:
                problems.append(f"{name}: malformed XML — {exc}")

    ct = parts.get("[Content_Types].xml", b"").decode("utf-8", "replace")
    slides = sorted(n for n in parts if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
    for slide in slides:
        if f'PartName="/{slide}"' not in ct:
            problems.append(f"{slide}: not declared in [Content_Types].xml")

    for name, data in parts.items():
        if not name.endswith(".rels"):
            continue
        base = Path(name).parent.parent
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            continue
        for rel in root:
            target, mode = rel.get("Target", ""), rel.get("TargetMode")
            if mode == "External" or target.startswith(("http", "mailto", "../media")):
                continue
            resolved = str((base / target).as_posix()).replace("/./", "/")
            while "/../" in resolved:
                resolved = re.sub(r"[^/]+/\.\./", "", resolved, count=1)
            if resolved not in parts:
                problems.append(f"{name}: relationship {rel.get('Id')} points at "
                                f"missing part {target}")

    pres = parts.get("ppt/presentation.xml", b"").decode("utf-8", "replace")
    listed = len(re.findall(r"<p:sldId ", pres))
    if listed != len(slides):
        problems.append(f"presentation.xml lists {listed} slide(s) but the package "
                        f"holds {len(slides)}")
    return problems, slides


def check_fidelity(parts, original_parts):
    """Template parts unchanged, and no slide overriding fonts or colours."""
    failures, notes = [], []

    if original_parts is not None:
        theirs = {n: d for n, d in original_parts.items() if n.startswith(TEMPLATE_PARTS)}
        ours = {n: d for n, d in parts.items() if n.startswith(TEMPLATE_PARTS)}
        for name, data in theirs.items():
            if name not in ours:
                failures.append(f"{name}: present in the template, missing from the deck")
            elif ours[name] != data:
                failures.append(f"{name}: edited — the deck has drifted off the template")
        for name in ours.keys() - theirs.keys():
            failures.append(f"{name}: added to the deck, not in the template")
        if not failures:
            notes.append(f"{len(theirs)} master/layout/theme part(s) byte-identical to "
                         f"the template.")
    else:
        notes.append("No --original given: the drift scan below ran, but nothing "
                     "confirms the template's own parts were left alone.")

    for name in sorted(n for n in parts if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)):
        try:
            root = ET.fromstring(parts[name])
        except ET.ParseError:
            continue  # already reported by the package check
        for shape in root.iterfind(".//p:cSld/p:spTree/*", NS):
            label_el = shape.find(".//p:cNvPr", NS)
            label = (label_el.get("name") if label_el is not None else "") or ""
            if label.startswith(GAP_PREFIX):
                continue  # gap markers name their colours on purpose
            for typeface in {el.get("typeface") for el in shape.iterfind(".//a:latin", NS)}:
                if typeface and not typeface.startswith("+"):
                    failures.append(f"{name} / {label}: sets font '{typeface}' — slides "
                                    f"must inherit from the layout and theme")
            for colour in {el.get("val") for el in shape.iterfind(".//a:srgbClr", NS)}:
                failures.append(f"{name} / {label}: sets literal colour '{colour}' — "
                                f"slides must inherit from the layout and theme")
    return failures, notes


def check_content(parts, slides, profile_layouts):
    """Overflow against placeholder geometry, plus leftover scaffolding."""
    overflow, scaffolding, empties = [], [], []
    layouts_by_part = {lay["part"]: lay for lay in profile_layouts}

    for slide in slides:
        rels_name = f"ppt/slides/_rels/{Path(slide).name}.rels"
        layout_part = None
        if rels_name in parts:
            match = re.search(r'Target="\.\./slideLayouts/([^"]+)"',
                              parts[rels_name].decode("utf-8", "replace"))
            if match:
                layout_part = f"ppt/slideLayouts/{match.group(1)}"
        layout = layouts_by_part.get(layout_part, {})
        geoms = {(ph.get("name") or "").lower(): ph for ph in layout.get("placeholders", [])}

        root = ET.fromstring(parts[slide])
        n = Path(slide).stem.replace("slide", "")
        for shape in root.iterfind(".//p:sp", NS):
            name_el = shape.find(".//p:nvSpPr/p:cNvPr", NS)
            shape_name = (name_el.get("name") if name_el is not None else "") or ""
            paragraphs = [
                " ".join(t.text or "" for t in para.iterfind(".//a:t", NS)).strip()
                for para in shape.iterfind(".//a:p", NS)
            ]
            text = " ".join(paragraphs).strip()

            if shape.find(".//p:nvPr/p:ph", NS) is not None and not text:
                empties.append(f"slide {n}: placeholder '{shape_name}' is empty")

            for pattern, what in PLACEHOLDER_PATTERNS:
                if pattern.search(text):
                    scaffolding.append(f"slide {n} / {shape_name}: {what}")

            ph = geoms.get(shape_name.lower())
            if ph and text and not shape_name.startswith(GAP_PREFIX):
                size = ph.get("font_size_pt")
                geometry = ph.get("geometry")
                # An autofit shrink already applied by the renderer buys real room.
                autofit = shape.find(".//a:normAutofit", NS)
                scale = 1.0
                if autofit is not None and autofit.get("fontScale"):
                    scale = int(autofit.get("fontScale")) / 100000
                if size and geometry:
                    ratio = fit_ratio(paragraphs, geometry, size * scale)
                    if ratio and ratio > 1.0:
                        overflow.append(
                            f"slide {n} / {shape_name}: ~{ratio:.0%} of the box at "
                            f"{size * scale:.0f}pt — content will clip, cut it")
    return overflow, scaffolding, empties


def render_report(deck, original, package, fidelity, notes, overflow, scaffolding,
                  empties, slide_count):
    hard_fail = bool(package or fidelity)
    lines = [
        f"# Deck QA — {Path(deck).name}",
        "",
        f"**Status:** {'FAIL — must fix before handover' if hard_fail else 'PASS (mechanical checks)'}",
        "",
        f"{slide_count} slide(s). Template: `{original or '(not supplied)'}`.",
        "",
        "## 1. Package integrity",
        "",
    ]
    lines += ([f"- {p}" for p in package] if package
              else ["Well-formed throughout; every relationship resolves; slide count "
                    "agrees with `presentation.xml`."])

    lines += ["", "## 2. Template fidelity", ""]
    if fidelity:
        lines += ["A deck that has drifted off the approved template fails the "
                  "requirement it was built to meet, however similar it looks:", ""]
        lines += [f"- {f}" for f in fidelity]
    else:
        lines.append("No slide sets its own fonts or colours; everything inherits from "
                     "the layout and theme.")
    lines += [""] + [f"> {n}" for n in notes] + [""]

    lines += ["## 3. Text overflow", ""]
    if overflow:
        lines += ["PowerPoint clips an overfull placeholder rather than spilling it, so "
                  "these lose content silently. Cut the content or move it to another "
                  "slide — do not shrink the type further:", ""]
        lines += [f"- {o}" for o in overflow]
    else:
        lines.append("Every text placeholder fits its box at the layout's own size.")

    lines += ["", "## 4. Leftover scaffolding", ""]
    if scaffolding or empties:
        lines += [f"- {s}" for s in scaffolding] + [f"- {e}" for e in empties]
    else:
        lines.append("No prompt text, no placeholder markers, no empty placeholders.")

    lines += [
        "",
        "## Still to do by eye",
        "",
        "- [ ] open the deck and step through every slide at full size",
        "- [ ] check every `[GAP]` panel reads as an action for the practitioner, not as content",
        "- [ ] confirm the RFP's file format, naming convention and slide limit",
        "- [ ] before sending to a client: re-render with `--sources hidden`",
        "",
        "This is a **first draft for practitioner review**, not a submission-ready document.",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", type=Path, help="the built .pptx")
    ap.add_argument("--original", type=Path,
                    help="the approved template it was built on — always pass this for "
                         "a template-derived deck; without it fidelity cannot be proven")
    ap.add_argument("--profile", type=Path,
                    help="template_profile.json (default: profiled from the deck itself)")
    ap.add_argument("-o", "--out", type=Path, default=Path("qa_pptx.md"))
    args = ap.parse_args()

    if not args.deck.is_file():
        sys.exit(f"deck not found: {args.deck}")
    parts = load(args.deck)
    original_parts = load(args.original) if args.original else None

    if args.profile and args.profile.is_file():
        layouts = json.loads(args.profile.read_text(encoding="utf-8")).get("layouts", [])
    else:
        layouts = [profile_layout(parts[n], n) for n in sorted(parts)
                   if n.startswith("ppt/slideLayouts/slideLayout")]

    package, slides = check_package(parts)
    fidelity, notes = check_fidelity(parts, original_parts)
    overflow, scaffolding, empties = check_content(parts, slides, layouts)

    report = render_report(args.deck, args.original, package, fidelity, notes, overflow,
                           scaffolding, empties, len(slides))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")

    print(f"{len(slides)} slide(s) checked -> {args.out}")
    print(f"  package problems: {len(package)}   fidelity failures: {len(fidelity)}")
    print(f"  overflow: {len(overflow)}   scaffolding: {len(scaffolding) + len(empties)}")
    for problem in package + fidelity:
        print(f"  FAIL {problem}", file=sys.stderr)
    for warning in overflow:
        print(f"  OVERFLOW {warning}", file=sys.stderr)
    return 1 if (package or fidelity) else 0


if __name__ == "__main__":
    sys.exit(main())
