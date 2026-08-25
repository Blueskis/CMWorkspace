#!/usr/bin/env python3
"""Turn a comms plan into a Word document (Stage 3b, email and article channels).

    python build_docx.py comms_plan.json --brand brand_profile.json -o comms/<run>
    NODE_PATH="$(npm root -g)" node comms/<run>/build.js

Emits `build.js`, a standalone Node script against docx-js, rather than assembling OOXML
here. Two reasons: the script is inspectable before it runs, and the `docx` skill's
documented footguns get encoded once in a generator instead of re-derived every run —
dual DXA table widths, ShadingType.CLEAR (SOLID renders black), bullets via a numbering
config rather than literal characters, and separate Paragraphs instead of "\\n".

The brand profile drives page setup, fonts and heading colour. A `[GAP]` block renders as
visible highlighted text, exactly as it does in the Markdown draft — never as substitute
prose, and never silently dropped.

STATUS (v0.2): this generates and checks; it does not run node itself, so a failed build
leaves an inspectable script rather than a half-written .docx. It does not apply a client
.dotx letterhead — when `channel_specs.docx.dotx_path` is set the script reports that the
document must be built onto that template through the `docx` skill's edit path instead,
because docx-js cannot open an existing file.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_markdown import ordered_parts, all_words  # noqa: E402

EMAIL_HEADERS = ("subject", "preheader")
ARTICLE_HEADERS = ("headline", "standfirst")

PAGE_SIZES = {  # DXA, 1440 = 1 inch
    "A4": {"width": 11906, "height": 16838},
    "Letter": {"width": 12240, "height": 15840},
}


def js(value):
    """JSON is a valid JS literal subset — safe for embedding strings and structures."""
    return json.dumps(value, ensure_ascii=False)


def hex_of(brand, role, default):
    entry = ((brand.get("palette") or {}).get(role) or {})
    value = entry.get("hex", default)
    return str(value).lstrip("#").upper()


def docx_check():
    """Is docx-js resolvable? Returns (ok, node_path, remedy)."""
    if not shutil.which("node"):
        return False, "", "node is not on PATH"
    root = ""
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    import os
    env = dict(os.environ)
    if root:
        env["NODE_PATH"] = root
    probe = subprocess.run(["node", "-e", "require.resolve('docx')"],
                           capture_output=True, text=True, timeout=30, env=env)
    if probe.returncode != 0:
        return False, root, ("the docx package is not resolvable — run `npm install -g docx`, "
                             "then build with NODE_PATH=\"$(npm root -g)\"")
    return True, root, ""


# --- block -> docx-js children ---------------------------------------------


def block_children(block, style):
    """One plan block -> a JS array expression of docx elements."""
    if block.get("gap"):
        note = block.get("gap_note") or "Not covered by the knowledge bank or the brief."
        return (f'gapPara({js("[GAP] " + note)})')

    kind, content = block["kind"], block["content"]

    if kind in ("text", "paragraph"):
        items = content if isinstance(content, list) else [content]
        # docx-js ignores "\n" inside a TextRun — a newline must become its own
        # Paragraph or the line break silently disappears from the document.
        parts = []
        for item in items:
            for line in str(item).split("\n"):
                if line.strip():
                    parts.append(f'body({js(line.strip())})')
        return "[" + ", ".join(parts) + "]"

    if kind == "heading":
        return f'[h3({js(str(content))})]'

    if kind == "bullets":
        items = content if isinstance(content, list) else [content]
        return "[" + ", ".join(f'bullet({js(str(i))})' for i in items) + "]"

    if kind == "table":
        headers = content.get("headers", [])
        rows = content.get("rows", [])
        return f'[buildTable({js(headers)}, {js(rows)})]'

    if kind == "phases":
        items = content if isinstance(content, list) else [content]
        rows = []
        for p in items:
            when = str(p.get("when") or p.get("date") or "")
            name = str(p.get("name") or p.get("label") or "")
            detail = str(p.get("detail") or p.get("description") or "")
            rows.append([when, name, detail] if detail else [when, name])
        headers = ["When", "What", "Detail"] if any(len(r) == 3 for r in rows) else ["When", "What"]
        rows = [r + [""] * (len(headers) - len(r)) for r in rows]
        return f'[buildTable({js(headers)}, {js(rows)})]'

    if kind == "metric":
        items = content if isinstance(content, list) else [content]
        return "[" + ", ".join(
            f'bullet({js(str(m.get("value", "")) + " — " + str(m.get("label", "")))})'
            for m in items) + "]"

    if kind == "members":
        items = content if isinstance(content, list) else [content]
        parts = []
        for m in items:
            line = f'{m.get("name", "")}, {m.get("role", "")} — {m.get("bio", "")}'
            parts.append(f'bullet({js(line)})')
        return "[" + ", ".join(parts) + "]"

    if kind == "notes":
        return "[]"

    return f'[body({js(str(content))})]'


def build_js(plan, brand, channel, out_dir):
    specs = (brand.get("channel_specs") or {})
    page_cfg = specs.get("docx", {})
    size = PAGE_SIZES.get(page_cfg.get("page_size", "A4"), PAGE_SIZES["A4"])
    margin = int(round(float(page_cfg.get("margins_mm", 25)) * 1440 / 25.4))

    typo = brand.get("typography", {})
    heading_font = (typo.get("heading") or {}).get("family", "Calibri")
    body_font = (typo.get("body") or {}).get("family", "Calibri")
    ink = hex_of(brand, "ink", "#14432A")
    ink_soft = hex_of(brand, "ink_soft", "#3F4A52")
    accent = hex_of(brand, "accent", "#1A7A45")

    headers = EMAIL_HEADERS if channel == "email" else ARTICLE_HEADERS
    head_parts, body_parts = [], []
    for _, part in ordered_parts(plan):
        (head_parts if part.get("part_kind") in headers else body_parts).append(part)

    lines = [
        "// Generated by build_docx.py — inspect before running.",
        "// Build with:  NODE_PATH=\"$(npm root -g)\" node build.js",
        "const {",
        "  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,",
        "  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,",
        "  LevelFormat, PageOrientation,",
        "} = require('docx');",
        "const fs = require('fs');",
        "",
        f"const INK = {js(ink)}, INK_SOFT = {js(ink_soft)}, ACCENT = {js(accent)};",
        f"const HEADING_FONT = {js(heading_font)}, BODY_FONT = {js(body_font)};",
        "",
        "const body = (t) => new Paragraph({ spacing: { after: 160 },",
        "  children: [new TextRun({ text: t, font: BODY_FONT, size: 22, color: INK_SOFT })] });",
        "",
        "const h1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1,",
        "  spacing: { after: 240 },",
        "  children: [new TextRun({ text: t, font: HEADING_FONT, size: 36, bold: true, color: INK })] });",
        "",
        "const h2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2,",
        "  spacing: { before: 280, after: 140 },",
        "  children: [new TextRun({ text: t, font: HEADING_FONT, size: 26, bold: true, color: INK })] });",
        "",
        "const h3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3,",
        "  spacing: { before: 200, after: 120 },",
        "  children: [new TextRun({ text: t, font: HEADING_FONT, size: 23, bold: true, color: INK })] });",
        "",
        "const label = (k, v) => new Paragraph({ spacing: { after: 120 }, children: [",
        "  new TextRun({ text: k + ': ', font: HEADING_FONT, size: 22, bold: true, color: INK }),",
        "  new TextRun({ text: v, font: BODY_FONT, size: 22, color: INK_SOFT })] });",
        "",
        "// Bullets come from a numbering config — never a literal '•'.",
        "const bullet = (t) => new Paragraph({ numbering: { reference: 'bullets', level: 0 },",
        "  spacing: { after: 80 },",
        "  children: [new TextRun({ text: t, font: BODY_FONT, size: 22, color: INK_SOFT })] });",
        "",
        "const quote = (t) => new Paragraph({ spacing: { before: 200, after: 200 },",
        "  indent: { left: 480 },",
        "  border: { left: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 12 } },",
        "  children: [new TextRun({ text: t, font: HEADING_FONT, size: 26, italics: true, color: INK })] });",
        "",
        "// A gap stays visible in the document, exactly as in the Markdown draft.",
        "const gapPara = (t) => [new Paragraph({ spacing: { before: 160, after: 160 },",
        "  shading: { type: ShadingType.CLEAR, fill: 'FEF3C7' },",
        "  children: [new TextRun({ text: t, font: BODY_FONT, size: 22, bold: true, color: 'B45309' })] })];",
        "",
        "// Tables need dual widths: columnWidths on the table AND width on every cell.",
        "function buildTable(headers, rows) {",
        "  const total = 9000;",
        "  const w = Math.floor(total / headers.length);",
        "  const widths = headers.map(() => w);",
        "  const cell = (text, isHead) => new TableCell({",
        "    width: { size: w, type: WidthType.DXA },",
        "    shading: isHead ? { type: ShadingType.CLEAR, fill: 'F4F1EA' } : undefined,",
        "    children: [new Paragraph({ children: [new TextRun({",
        "      text: String(text), font: BODY_FONT, size: 20,",
        "      bold: !!isHead, color: isHead ? INK : INK_SOFT })] })] });",
        "  return new Table({ columnWidths: widths, width: { size: total, type: WidthType.DXA },",
        "    rows: [ new TableRow({ tableHeader: true, children: headers.map(h => cell(h, true)) },),",
        "      ...rows.map(r => new TableRow({ children: r.map(c => cell(c, false)) })) ] });",
        "}",
        "",
        "const children = [];",
    ]

    title = plan.get("engagement_title") or plan.get("run_id", "")
    if channel == "email":
        lines.append(f"children.push(h1({js(title)}));")
        for part in head_parts:
            kind = part.get("part_kind", "")
            text = " ".join(
                b["content"] if isinstance(b.get("content"), str) else ""
                for b in part["blocks"] if not b.get("gap")).strip()
            lines.append(f"children.push(label({js(kind.capitalize())}, {js(text)}));")
    else:
        for part in head_parts:
            kind = part.get("part_kind")
            text = " ".join(
                b["content"] if isinstance(b.get("content"), str) else ""
                for b in part["blocks"] if not b.get("gap")).strip()
            if kind == "headline":
                lines.append(f"children.push(h1({js(text)}));")
            else:
                lines.append(f"children.push(quote({js(text)}));")

    for part in body_parts:
        if part.get("part_kind") == "pull-quote":
            text = " ".join(
                b["content"] if isinstance(b.get("content"), str) else ""
                for b in part["blocks"] if not b.get("gap")).strip()
            lines.append(f"children.push(quote({js(text)}));")
            continue
        if part.get("title"):
            lines.append(f"children.push(h2({js(part['title'])}));")
        for block in part["blocks"]:
            expr = block_children(block, None)
            lines.append(f"children.push(...{expr});")

    lines += [
        "",
        "const doc = new Document({",
        "  numbering: { config: [{ reference: 'bullets', levels: [{ level: 0,",
        "    format: LevelFormat.BULLET, text: '\\u2022', alignment: AlignmentType.LEFT,",
        "    style: { paragraph: { indent: { left: 460, hanging: 260 } } } }] }] },",
        "  sections: [{ properties: { page: { size: "
        f"{{ width: {size['width']}, height: {size['height']} }}, "
        f"margin: {{ top: {margin}, right: {margin}, bottom: {margin}, left: {margin} }} }} }},",
        "    children }],",
        "});",
        "",
        f"Packer.toBuffer(doc).then(b => {{ fs.writeFileSync(__dirname + '/draft.docx', b);",
        "  console.log('Wrote ' + __dirname + '/draft.docx'); });",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path)
    ap.add_argument("--brand", type=Path, required=True)
    ap.add_argument("-o", "--out", type=Path, required=True, help="Output directory")
    args = ap.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    brand = json.loads(args.brand.read_text(encoding="utf-8"))

    channel = plan.get("channel")
    if channel not in ("email", "article"):
        sys.exit(f"build_docx.py handles the email and article channels; got '{channel}'")

    if not (brand.get("approval") or {}).get("approved_by"):
        sys.exit("brand profile has no recorded approval — stop and ask before producing")

    args.out.mkdir(parents=True, exist_ok=True)
    script = args.out / "build.js"
    script.write_text(build_js(plan, brand, channel, args.out), encoding="utf-8")

    words = sum(all_words(p) for _, p in ordered_parts(plan))
    gaps = sum(1 for _, p in ordered_parts(plan) for b in p["blocks"] if b.get("gap"))
    print(f"Wrote {script}  [{channel}]  {words} words, {gaps} gap(s)")

    ok, root, remedy = docx_check()
    if ok:
        print(f'  build with:  NODE_PATH="{root}" node {script}')
    else:
        print(f"  NOT BUILDABLE YET: {remedy}", file=sys.stderr)

    dotx = ((brand.get("channel_specs") or {}).get("docx") or {}).get("dotx_path")
    if dotx:
        print(f"  NOTE: the brand names a client template ({dotx}). docx-js cannot open an "
              f"existing file — to build ON that letterhead, use the `docx` skill's edit "
              f"path (unzip -> edit word/document.xml -> zip) instead of this script.")
    else:
        print("  no client .dotx — this builds from scratch on the brand palette, which is "
              "NOT the client's approved template. Say so at handover.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
