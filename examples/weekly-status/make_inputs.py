#!/usr/bin/env python3
"""Builds the fictional week-01 / week-02 input documents for the worked example.

    python examples/weekly-status/make_inputs.py

Writes a real .xlsx (training completion), .docx (CM plan) and .pptx (RICEFWA status)
for each week, using zipfile + string templates so the repo needs no Office libraries.
The generated files are committed, so this only needs re-running when the example data
changes. Client, programme and people are all invented.
"""

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
ODR = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def write(path, parts):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in parts.items():
            zf.writestr(name, data.strip())


def types(defaults, overrides):
    d = "".join(f'<Default Extension="{e}" ContentType="{c}"/>' for e, c in defaults)
    o = "".join(f'<Override PartName="{p}" ContentType="{c}"/>' for p, c in overrides)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="{CT}">{d}{o}</Types>'


def rels(entries):
    body = "".join(
        f'<Relationship Id="{i}" Type="{t}" Target="{tg}"/>' for i, t, tg in entries
    )
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL}">{body}</Relationships>'


# ------------------------------------------------------------------ xlsx


def make_xlsx(path, sheet_name, rows):
    strings, index = [], {}

    def sid(text):
        if text not in index:
            index[text] = len(strings)
            strings.append(text)
        return index[text]

    xml_rows = []
    for r, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{chr(65 + c)}{r}" t="s"><v>{sid(str(v))}</v></c>'
            for c, v in enumerate(row)
            if str(v) != ""
        )
        xml_rows.append(f'<row r="{r}">{cells}</row>')

    shared = "".join(f"<si><t>{escape(s)}</t></si>" for s in strings)
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    write(
        path,
        {
            "[Content_Types].xml": types(
                [("rels", f"application/vnd.openxmlformats-package.relationships+xml"), ("xml", "application/xml")],
                [
                    ("/xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
                    ("/xl/worksheets/sheet1.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
                    ("/xl/sharedStrings.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"),
                    ("/xl/styles.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"),
                ],
            ),
            "_rels/.rels": rels([("rId1", f"{ODR}/officeDocument", "xl/workbook.xml")]),
            "xl/_rels/workbook.xml.rels": rels(
                [
                    ("rId1", f"{ODR}/worksheet", "worksheets/sheet1.xml"),
                    ("rId2", f"{ODR}/sharedStrings", "sharedStrings.xml"),
                    ("rId3", f"{ODR}/styles", "styles.xml"),
                ]
            ),
            "xl/workbook.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook {ns} xmlns:r="{ODR}"><sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets></workbook>',
            "xl/styles.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet {ns}><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="1"><xf xfId="0"/></cellXfs></styleSheet>',
            "xl/sharedStrings.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst {ns} count="{len(strings)}" uniqueCount="{len(strings)}">{shared}</sst>',
            "xl/worksheets/sheet1.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet {ns}><sheetData>{"".join(xml_rows)}</sheetData></worksheet>',
        },
    )


# ------------------------------------------------------------------ docx


def make_docx(path, blocks):
    """blocks: ('h', text) | ('p', text) | ('table', [[...], ...])"""
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

    def para(text, style=None):
        pr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        return f"<w:p>{pr}<w:r><w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"

    body = []
    for kind, payload in blocks:
        if kind == "h":
            body.append(para(payload, "Heading1"))
        elif kind == "p":
            body.append(para(payload))
        else:
            rows = "".join(
                "<w:tr>"
                + "".join(
                    f'<w:tc><w:tcPr><w:tcW w:w="2000" w:type="dxa"/></w:tcPr>{para(str(c))}</w:tc>'
                    for c in row
                )
                + "</w:tr>"
                for row in payload
            )
            body.append(f"<w:tbl><w:tblPr><w:tblW w:w=\"0\" w:type=\"auto\"/></w:tblPr>{rows}</w:tbl>")

    styles = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {ns}>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style></w:styles>'
    )
    write(
        path,
        {
            "[Content_Types].xml": types(
                [("rels", "application/vnd.openxmlformats-package.relationships+xml"), ("xml", "application/xml")],
                [
                    ("/word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"),
                    ("/word/styles.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"),
                ],
            ),
            "_rels/.rels": rels([("rId1", f"{ODR}/officeDocument", "word/document.xml")]),
            "word/_rels/document.xml.rels": rels([("rId1", f"{ODR}/styles", "styles.xml")]),
            "word/styles.xml": styles,
            "word/document.xml": f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {ns}><w:body>{"".join(body)}</w:body></w:document>',
        },
    )


# ------------------------------------------------------------------ pptx

A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _sp(idx, name, ph_type, x, y, cx, cy, paras):
    ph = f'<p:ph type="{ph_type}"/>' if ph_type else "<p:ph/>"
    text = "".join(
        f'<a:p><a:r><a:rPr lang="en-GB"/><a:t>{escape(t)}</a:t></a:r></a:p>' for t in paras
    ) or "<a:p/>"
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{idx}" name="{name}"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        f"<p:nvPr>{ph}</p:nvPr></p:nvSpPr>"
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        f"<p:txBody><a:bodyPr/><a:lstStyle/>{text}</p:txBody></p:sp>"
    )


def _slide_xml(title, bullets):
    shapes = _sp(2, "Title", "title", 838200, 365125, 10515600, 1325563, [title]) + _sp(
        3, "Body", "body", 838200, 1825625, 10515600, 4351338, bullets
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:sld xmlns:a="{A_NS}" xmlns:r="{ODR}" xmlns:p="{P_NS}"><p:cSld><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        "<p:grpSpPr><a:xfrm/></p:grpSpPr>"
        f"{shapes}</p:spTree></p:cSld><p:clrMapOvr><a:overrideClrMapping bg1=\"lt1\" tx1=\"dk1\" bg2=\"lt2\" tx2=\"dk2\" accent1=\"accent1\" accent2=\"accent2\" accent3=\"accent3\" accent4=\"accent4\" accent5=\"accent5\" accent6=\"accent6\" hlink=\"hlink\" folHlink=\"folHlink\"/></p:clrMapOvr></p:sld>"
    )


def _theme():
    scheme = "".join(
        f'<a:{n}><a:srgbClr val="{v}"/></a:{n}>'
        for n, v in [
            ("dk1", "000000"), ("lt1", "FFFFFF"), ("dk2", "1F3864"), ("lt2", "EEECE1"),
            ("accent1", "4472C4"), ("accent2", "ED7D31"), ("accent3", "A5A5A5"),
            ("accent4", "FFC000"), ("accent5", "5B9BD5"), ("accent6", "70AD47"),
            ("hlink", "0563C1"), ("folHlink", "954F72"),
        ]
    )
    fonts = (
        '<a:majorFont><a:latin typeface="Calibri Light"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
        '<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
    )
    fill = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    line = f'<a:ln w="9525" cap="flat"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>'
    fmt = (
        f"<a:fillStyleLst>{fill}{fill}{fill}</a:fillStyleLst>"
        f"<a:lnStyleLst>{line}{line}{line}</a:lnStyleLst>"
        "<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>"
        f"<a:bgFillStyleLst>{fill}{fill}{fill}</a:bgFillStyleLst>"
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<a:theme xmlns:a="{A_NS}" name="Office"><a:themeElements>'
        f'<a:clrScheme name="Office">{scheme}</a:clrScheme>'
        f'<a:fontScheme name="Office">{fonts}</a:fontScheme>'
        f'<a:fmtScheme name="Office">{fmt}</a:fmtScheme>'
        "</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>"
    )


def make_pptx(path, slides):
    n = len(slides)
    parts = {
        "_rels/.rels": rels([("rId1", f"{ODR}/officeDocument", "ppt/presentation.xml")]),
        "ppt/theme/theme1.xml": _theme(),
    }
    placeholders = _sp(2, "Title Placeholder", "title", 838200, 365125, 10515600, 1325563, []) + _sp(
        3, "Body Placeholder", "body", 838200, 1825625, 10515600, 4351338, []
    )
    tree = (
        '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        f"<p:grpSpPr><a:xfrm/></p:grpSpPr>{placeholders}</p:spTree></p:cSld>"
    )
    clrmap = '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
    parts["ppt/slideMasters/slideMaster1.xml"] = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="{A_NS}" xmlns:r="{ODR}" xmlns:p="{P_NS}">'
        f'{tree}{clrmap}<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst></p:sldMaster>'
    )
    parts["ppt/slideMasters/_rels/slideMaster1.xml.rels"] = rels(
        [
            ("rId1", f"{ODR}/slideLayout", "../slideLayouts/slideLayout1.xml"),
            ("rId2", f"{ODR}/theme", "../theme/theme1.xml"),
        ]
    )
    parts["ppt/slideLayouts/slideLayout1.xml"] = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="{A_NS}" xmlns:r="{ODR}" xmlns:p="{P_NS}" type="obj" preserve="1">'
        f"{tree}<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
    )
    parts["ppt/slideLayouts/_rels/slideLayout1.xml.rels"] = rels(
        [("rId1", f"{ODR}/slideMaster", "../slideMasters/slideMaster1.xml")]
    )

    for i, (title, bullets) in enumerate(slides, start=1):
        parts[f"ppt/slides/slide{i}.xml"] = _slide_xml(title, bullets)
        parts[f"ppt/slides/_rels/slide{i}.xml.rels"] = rels(
            [("rId1", f"{ODR}/slideLayout", "../slideLayouts/slideLayout1.xml")]
        )

    sld_ids = "".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, n + 1)
    )
    parts["ppt/presentation.xml"] = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:a="{A_NS}" xmlns:r="{ODR}" xmlns:p="{P_NS}">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{sld_ids}</p:sldIdLst>"
        '<p:sldSz cx="12192000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'
    )
    parts["ppt/_rels/presentation.xml.rels"] = rels(
        [("rId1", f"{ODR}/slideMaster", "slideMasters/slideMaster1.xml")]
        + [(f"rId{i + 1}", f"{ODR}/slide", f"slides/slide{i}.xml") for i in range(1, n + 1)]
        + [(f"rId{n + 2}", f"{ODR}/theme", "theme/theme1.xml")]
    )
    parts["[Content_Types].xml"] = types(
        [("rels", "application/vnd.openxmlformats-package.relationships+xml"), ("xml", "application/xml")],
        [
            ("/ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
            ("/ppt/slideMasters/slideMaster1.xml", "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"),
            ("/ppt/slideLayouts/slideLayout1.xml", "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"),
            ("/ppt/theme/theme1.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
        ]
        + [
            (f"/ppt/slides/slide{i}.xml", "application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
            for i in range(1, n + 1)
        ],
    )
    write(path, parts)


# ------------------------------------------------------------------ the data

TRAINING_HEADER = ["Employee", "Role", "Course", "Status", "Completion %", "Due Date"]

TRAINING = {
    1: [
        ["A. Okafor", "AP Clerk", "S4 Finance Core", "In Progress", "40", "2026-09-04"],
        ["B. Lindqvist", "AP Clerk", "S4 Finance Core", "Not Started", "0", "2026-09-04"],
        ["C. Moreau", "Buyer", "S4 Procurement", "Completed", "100", "2026-08-28"],
        ["D. Ferreira", "Buyer", "S4 Procurement", "In Progress", "60", "2026-08-28"],
        ["E. Tanaka", "Warehouse Lead", "S4 Logistics", "Not Started", "0", "2026-09-11"],
        ["F. Adeyemi", "Warehouse Lead", "S4 Logistics", "Not Started", "0", "2026-09-11"],
        ["G. Novak", "Master Data", "Data Stewardship", "In Progress", "75", "2026-08-21"],
    ],
    2: [
        ["A. Okafor", "AP Clerk", "S4 Finance Core", "Completed", "100", "2026-09-04"],
        ["B. Lindqvist", "AP Clerk", "S4 Finance Core", "In Progress", "25", "2026-09-04"],
        ["C. Moreau", "Buyer", "S4 Procurement", "Completed", "100", "2026-08-28"],
        ["D. Ferreira", "Buyer", "S4 Procurement", "Completed", "100", "2026-08-28"],
        ["E. Tanaka", "Warehouse Lead", "S4 Logistics", "Not Started", "0", "2026-09-25"],
        ["F. Adeyemi", "Warehouse Lead", "S4 Logistics", "In Progress", "30", "2026-09-25"],
        ["G. Novak", "Master Data", "Data Stewardship", "Completed", "100", "2026-08-21"],
        ["H. Silva", "Master Data", "Data Stewardship", "Not Started", "0", "2026-09-18"],
    ],
}

PLAN_TABLE_HEADER = ["Activity ID", "Activity", "Owner", "Status", "Due Date"]

PLAN = {
    1: {
        "intro": "This plan covers change management for the Meridian S/4HANA rollout across Finance, Procurement and Logistics. It is reviewed weekly at the Thursday cadence.",
        "engagement": "Change network stands at 14 named champions across 6 sites. Site 6 (Porto) has no champion and recruitment is with the site lead.",
        "comms": "Wave 1 go-live comms drafted and with the sponsor for review. Intranet hub is live.",
        "risks": "Top risk remains Logistics super-user availability during peak season; mitigation under discussion with the Ops director.",
        "rows": [
            ["CM-01", "Change impact assessment - Finance", "R. Iyer", "Complete", "2026-07-31"],
            ["CM-02", "Change impact assessment - Logistics", "R. Iyer", "In Progress", "2026-08-21"],
            ["CM-03", "Champion network stand-up", "S. Brandt", "In Progress", "2026-08-28"],
            ["CM-04", "Go-live comms pack", "S. Brandt", "In Progress", "2026-09-04"],
            ["CM-05", "Training needs analysis - Wave 2", "R. Iyer", "Not Started", "2026-09-18"],
        ],
    },
    2: {
        "intro": "This plan covers change management for the Meridian S/4HANA rollout across Finance, Procurement and Logistics. It is reviewed weekly at the Thursday cadence.",
        "engagement": "Change network stands at 16 named champions across 6 sites. Porto has appointed a champion; all sites are now covered.",
        "comms": "Wave 1 go-live comms approved by the sponsor. Intranet hub is live. First countdown mailer scheduled for 1 September.",
        "risks": "Logistics super-user availability is now escalated to the steering committee after the Ops director declined to backfill during peak season. A second risk has opened on master data readiness following the Week 12 data audit.",
        "rows": [
            ["CM-01", "Change impact assessment - Finance", "R. Iyer", "Complete", "2026-07-31"],
            ["CM-02", "Change impact assessment - Logistics", "R. Iyer", "Complete", "2026-08-21"],
            ["CM-03", "Champion network stand-up", "S. Brandt", "Complete", "2026-08-28"],
            ["CM-04", "Go-live comms pack", "L. Haddad", "In Progress", "2026-09-11"],
            ["CM-05", "Training needs analysis - Wave 2", "R. Iyer", "In Progress", "2026-09-18"],
            ["CM-06", "Master data readiness remediation", "G. Novak", "Not Started", "2026-09-25"],
        ],
    },
}

RICEFWA = {
    1: [
        ("RICEFWA Status - Week 11", [
            "Total objects: 42", "Build complete: 18", "In test: 9", "At risk: 3",
        ]),
        ("Finance Objects", [
            "FI-R-014 Payment run report - In Build - amber",
            "FI-I-002 Bank statement interface - In Test - green",
            "FI-E-007 Vendor master extract - Not Started - green",
        ]),
        ("Logistics Objects", [
            "LO-W-011 Goods receipt workflow - In Build - red",
            "LO-F-003 Pick list form - In Build - amber",
        ]),
        ("Decisions Needed", [
            "Confirm owner for FI-E-007 vendor master extract",
        ]),
    ],
    2: [
        ("RICEFWA Status - Week 12", [
            "Total objects: 43", "Build complete: 24", "In test: 12", "At risk: 2",
        ]),
        ("Finance Objects", [
            "FI-R-014 Payment run report - In Test - green",
            "FI-I-002 Bank statement interface - Signed Off - green",
            "FI-E-007 Vendor master extract - In Build - green",
            "FI-A-021 Period close automation - Not Started - amber",
        ]),
        ("Logistics Objects", [
            "LO-W-011 Goods receipt workflow - In Test - amber",
            "LO-F-003 Pick list form - In Build - amber",
        ]),
        ("Decisions Needed", [
            "Approve additional test window for LO-W-011 goods receipt workflow",
        ]),
    ],
}


def build_week(week, folder):
    make_xlsx(
        folder / "training-completion.xlsx",
        "Wave 1 Completion",
        [TRAINING_HEADER] + TRAINING[week],
    )
    plan = PLAN[week]
    make_docx(
        folder / "cm-plan.docx",
        [
            ("h", "Purpose and Scope"),
            ("p", plan["intro"]),
            ("h", "Stakeholder Engagement"),
            ("p", plan["engagement"]),
            ("h", "Communications"),
            ("p", plan["comms"]),
            ("h", "Risks and Issues"),
            ("p", plan["risks"]),
            ("h", "Activity Schedule"),
            ("table", [PLAN_TABLE_HEADER] + plan["rows"]),
        ],
    )
    make_pptx(folder / "ricefwa-status.pptx", RICEFWA[week])


def main():
    for week in (1, 2):  # the example runs as Week 11 -> Week 12
        folder = HERE / "inputs" / f"week-{week + 10}"
        build_week(week, folder)
        print(f"wrote {folder}")


if __name__ == "__main__":
    main()
