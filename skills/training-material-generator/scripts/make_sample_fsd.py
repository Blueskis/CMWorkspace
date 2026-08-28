#!/usr/bin/env python3
"""Write the worked example's source documents: a short invented Purchase Order FSD.

    python make_sample_fsd.py -o examples/po-training/inputs/

Produces `PO-FSD.docx` (headings, numbered clauses, two embedded screenshots with figure
captions, a repeated header logo, and field-rule tables) and `PO-Status-Matrix.xlsx`.

It exists because Stage 1 is the riskiest code in this skill and nobody should have to
supply a client document to exercise it. Everything here is invented — no real system, no
real client, no real screenshots. The images are generated rectangles that carry the right
*shape* for the classifier to work on: a wide screen-sized capture, and a small logo that
repeats in every section so de-duplication has something to do.

Stdlib only: a .docx and a .xlsx are ZIPs of XML, and a PNG is a zlib stream with a few
framing chunks, so all three are written here without a dependency.
"""

import argparse
import struct
import sys
import zipfile
import zlib
from pathlib import Path

CT = "http://schemas.openxmlformats.org/package/2006/content-types"


# --- PNG -------------------------------------------------------------------


def png(width, height, rgb, bars=0):
    """A solid PNG, optionally striped, standing in for a UI capture."""
    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b""
    for y in range(height):
        colour = bytes(rgb)
        if bars and y % max(1, height // (bars * 2)) < max(1, height // (bars * 4)):
            colour = bytes(min(255, c + 40) for c in rgb)
        rows += b"\x00" + colour * width

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 6))
        + chunk(b"IEND", b"")
    )


# --- docx ------------------------------------------------------------------

XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

CONTENT_TYPES_DOCX = XML_DECL + f'''<Types xmlns="{CT}">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

ROOT_RELS = XML_DECL + '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

STYLES = XML_DECL + '''<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/></w:style>
</w:styles>'''


def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def w_para(text, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>'


def w_image(rid, name, descr, cx_in, cy_in):
    cx, cy = int(cx_in * 914400), int(cy_in * 914400)
    return (
        '<w:p><w:r><w:drawing>'
        f'<wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">'
        f'<wp:extent cx="{cx}" cy="{cy}"/>'
        f'<wp:docPr id="{rid[3:]}" name="{esc(name)}" descr="{esc(descr)}"/>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="{rid[3:]}" name="{esc(name)}" descr="{esc(descr)}"/>'
        '<pic:cNvPicPr/></pic:nvPicPr>'
        '<pic:blipFill><a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        f'r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
    )


def w_table(header, rows):
    def cell(text):
        return f'<w:tc><w:tcPr/>{w_para(text)}</w:tc>'
    out = ['<w:tbl><w:tblPr/>']
    out.append("<w:tr>" + "".join(cell(h) for h in header) + "</w:tr>")
    for row in rows:
        out.append("<w:tr>" + "".join(cell(c) for c in row) + "</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def page_break():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def build_docx(path):
    logo = png(120, 40, (30, 60, 120))
    create_screen = png(900, 520, (238, 240, 244), bars=6)
    approve_screen = png(880, 460, (240, 238, 236), bars=5)
    flow_image = png(700, 300, (250, 250, 250), bars=3)

    body = []

    def logo_para():
        return w_image("rId10", "header-logo", "Company logo", 1.2, 0.4)

    body.append(logo_para())
    body.append(w_para("Purchase Order Module — Functional Specification", "Heading1"))
    body.append(w_para(
        "This specification describes the Purchase Order (PO) module of the Procure-to-Pay "
        "system for Release R3. It is the source of record for PO creation, approval "
        "routing and downstream posting."))

    body.append(w_para("1. Introduction", "Heading1"))
    body.append(w_para("1.1 Purpose", "Heading2"))
    body.append(w_para(
        "The PO module allows a requisitioner to raise a purchase order against an approved "
        "supplier, route it for approval according to value thresholds, and transmit the "
        "approved order to the supplier. It replaces the spreadsheet-based ordering process "
        "used in Release R2 and earlier."))
    body.append(w_para("1.2 Document Control", "Heading2"))
    body.append(w_para("Owner: Procurement Systems. Reviewed quarterly."))

    body.append(page_break())
    body.append(logo_para())
    body.append(w_para("2. Process Overview", "Heading1"))
    body.append(w_para(
        "A purchase order moves through five states. A requisitioner creates the order in "
        "Draft. Submitting it runs a budget check; if the budget check passes the order "
        "moves to Pending Approval, and if it fails the order returns to Draft with a "
        "validation message. An approver either approves the order, moving it to Approved, "
        "or rejects it, returning it to Draft with mandatory rejection comments. An "
        "Approved order is transmitted to the supplier overnight and moves to Issued. "
        "An order may be cancelled from any state before Issued."))
    body.append(w_image("rId13", "process-flow", "Purchase order process flow", 5.0, 2.1))
    body.append(w_para("Figure 1: End-to-end purchase order process flow.", "Caption"))

    body.append(w_para("3. Roles and Responsibilities", "Heading1"))
    body.append(w_para(
        "Three roles operate the module. Role assignment is managed in the identity system "
        "and is not maintained within the PO module itself."))
    body.append(w_table(
        ["Role", "Can do", "Cannot do"],
        [
            ["PO Creator", "Create, edit and submit a draft order; cancel own draft",
             "Approve any order, including own"],
            ["PO Approver", "Approve or reject orders within their threshold; add comments",
             "Edit the line items of an order under approval"],
            ["Procurement Admin", "Maintain supplier records; reopen an Issued order",
             "Change approval thresholds"],
        ]))

    body.append(page_break())
    body.append(logo_para())
    body.append(w_para("4. Purchase Order Creation", "Heading1"))
    body.append(w_para("4.1 Create Purchase Order screen", "Heading2"))
    body.append(w_para(
        "The Create Purchase Order screen is reached from Procurement > Orders > New. The "
        "header captures supplier, delivery date and cost centre; the lines grid captures "
        "one row per item ordered. The order total is calculated from the lines and cannot "
        "be typed directly."))
    body.append(w_image("rId11", "create-po-screen", "Create Purchase Order screen", 6.0, 3.4))
    body.append(w_para("Figure 2: The Create Purchase Order screen, header and lines grid.", "Caption"))

    body.append(w_para("4.2 Field rules", "Heading2"))
    body.append(w_para("The following rules apply to the header fields."))
    body.append(w_table(
        ["Field", "Mandatory", "Rule"],
        [
            ["Supplier", "Yes", "Must be an active supplier; blocked suppliers are not selectable"],
            ["Delivery Date", "Yes", "Must be today or later; back-dating is rejected"],
            ["Cost Centre", "Yes", "Defaults from the requisitioner's profile; may be overridden"],
            ["Internal Reference", "No", "Free text, 30 characters"],
            ["Order Total", "No", "Calculated from the lines; read-only"],
        ]))

    body.append(w_para("4.3 Business rules", "Heading2"))
    body.append(w_para(
        "A purchase order must contain at least one line before it can be submitted. "
        "A line quantity must be greater than zero. The system runs a budget check on "
        "submission, not on save, so a draft may be saved that would fail the budget "
        "check. An order that fails the budget check returns to Draft and the "
        "requisitioner is shown the shortfall amount."))

    body.append(page_break())
    body.append(logo_para())
    body.append(w_para("5. Purchase Order Approval", "Heading1"))
    body.append(w_para("5.1 Approval thresholds", "Heading2"))
    body.append(w_para(
        "Approval routing is determined by the order total. Where an order exceeds the "
        "approver's threshold it routes to the next level; it is never split."))
    body.append(w_table(
        ["Order total", "Approver level", "Service level"],
        [
            ["Up to 5,000", "Line Manager", "2 working days"],
            ["5,001 to 50,000", "Department Head", "3 working days"],
            ["Above 50,000", "Finance Director", "5 working days"],
        ]))

    body.append(w_para("5.2 Approve Purchase Order screen", "Heading2"))
    body.append(w_para(
        "The approver opens the order from their approval queue. The screen shows the "
        "order header, the lines, and the budget check result. Approve and Reject are both "
        "available; Reject requires a comment of at least ten characters."))
    body.append(w_image("rId12", "approve-po-screen", "Approve Purchase Order screen", 5.9, 3.1))
    body.append(w_para("Figure 3: The Approve Purchase Order screen with the approval queue.", "Caption"))

    body.append(w_para("5.3 Exceptions and error handling", "Heading2"))
    body.append(w_para(
        "If an approver is absent, an order remains in their queue until reassigned by a "
        "Procurement Admin; there is no automatic escalation in Release R3. If the supplier "
        "is blocked after the order was created but before approval, approval is refused "
        "with the message 'Supplier is blocked'. If transmission to the supplier fails, the "
        "order stays in Approved and appears on the overnight exception report."))

    body.append(w_para("6. Integrations", "Heading1"))
    body.append(w_para(
        "On reaching Issued, the order is posted to the finance ledger as a commitment. "
        "Goods receipt is recorded in the warehouse system and matched back to the order "
        "line. A cancelled order releases its commitment on the next ledger run."))

    body.append(w_para("7. Revision History", "Heading1"))
    body.append(w_table(["Version", "Date", "Change"],
                        [["1.0", "2026-02-11", "Initial issue"],
                         ["1.1", "2026-05-03", "Approval thresholds updated for R3"]]))

    document = XML_DECL + (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>" + "".join(body) + "</w:body></w:document>"
    )

    doc_rels = XML_DECL + '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId10" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/logo.png"/>
<Relationship Id="rId11" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/create-po.png"/>
<Relationship Id="rId12" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/approve-po.png"/>
<Relationship Id="rId13" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/process-flow.png"/>
</Relationships>'''

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES_DOCX)
        zf.writestr("_rels/.rels", ROOT_RELS)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/styles.xml", STYLES)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
        zf.writestr("word/media/logo.png", logo)
        zf.writestr("word/media/create-po.png", create_screen)
        zf.writestr("word/media/approve-po.png", approve_screen)
        zf.writestr("word/media/process-flow.png", flow_image)
    return path


# --- xlsx ------------------------------------------------------------------


CONTENT_TYPES_XLSX = XML_DECL + f'''<Types xmlns="{CT}">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>'''

XLSX_ROOT_RELS = XML_DECL + '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''


def col_name(index):
    name = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def build_xlsx(path, sheet_name, rows):
    strings, lookup = [], {}
    for row in rows:
        for value in row:
            if value not in lookup:
                lookup[value] = len(strings)
                strings.append(value)

    sheet_rows = []
    for r, row in enumerate(rows, 1):
        cells = "".join(
            f'<c r="{col_name(c)}{r}" t="s"><v>{lookup[value]}</v></c>'
            for c, value in enumerate(row) if value
        )
        sheet_rows.append(f'<row r="{r}">{cells}</row>')

    sheet = XML_DECL + (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(sheet_rows) + "</sheetData></worksheet>"
    )
    shared = XML_DECL + (
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(strings)}" uniqueCount="{len(strings)}">'
        + "".join(f"<si><t>{esc(s)}</t></si>" for s in strings) + "</sst>"
    )
    workbook = XML_DECL + (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{esc(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    wb_rels = XML_DECL + '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>'''

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES_XLSX)
        zf.writestr("_rels/.rels", XLSX_ROOT_RELS)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
        zf.writestr("xl/sharedStrings.xml", shared)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path, default=Path("."), help="Output directory")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    docx = build_docx(args.out / "PO-FSD.docx")
    xlsx = build_xlsx(
        args.out / "PO-Status-Matrix.xlsx", "PO Statuses",
        [["Status", "Set by", "Next states", "Editable"],
         ["Draft", "PO Creator", "Pending Approval, Cancelled", "Yes"],
         ["Pending Approval", "System on submit", "Approved, Draft, Cancelled", "No"],
         ["Approved", "PO Approver", "Issued, Cancelled", "No"],
         ["Issued", "Overnight transmission", "Closed", "No"],
         ["Cancelled", "PO Creator or Admin", "None", "No"]],
    )
    for path in (docx, xlsx):
        print(f"Wrote {path} ({path.stat().st_size:,} bytes)")
    print("Invented content — no real system, client or screenshots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
