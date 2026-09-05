#!/usr/bin/env python3
"""Build a small synthetic .docx exercising map_source.py and extract_assets.py.

    python make_docx_fixture.py -o /tmp/sample-fsd.docx

Contents, by design:

  * A heading tree with a clause-numbered procedure section (4.2.1, with two numbered
    steps and a real screenshot) and a reference section (4.2.2, with a table and a
    letterhead-style image repeated 3 times).
  * One 800x600 "screenshot"-sized image, captioned by the paragraph that follows it
    (Figure 1) — extract_assets.py should keep this one and match its caption.
  * One 300x300 image repeated 3 times — extract_assets.py should drop it as noise
    (repeat_count > 2).
  * One 200x150 image, single occurrence — kept, but flagged `low_res`.

Stdlib only (uses zlib for PNG compression, no Pillow).
"""

import argparse
import struct
import sys
import zipfile
import zlib
from pathlib import Path

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"

CONTENT_TYPES = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

PKG_RELS = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

DOC_RELS = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image2.png"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image3.png"/>
</Relationships>'''


def make_png(w, h, color=(200, 200, 200)):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    row = bytes(color) * w
    raw = (b"\x00" + row) * h
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def para_heading(level, text):
    return f'<w:p><w:pPr><w:pStyle w:val="Heading{level}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'


def para_text(text):
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def para_step(text):
    return (
        '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
        f"<w:r><w:t>{text}</w:t></w:r></w:p>"
    )


def para_image(rid, alt):
    return f'''<w:p><w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
<wp:docPr id="1" name="Picture 1" descr="{alt}"/>
<a:graphic><a:graphicData><pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:blipFill><a:blip r:embed="{rid}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></pic:blipFill>
</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''


def table():
    return (
        "<w:tbl>"
        "<w:tr><w:tc><w:p><w:r><w:t>Field</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>Description</w:t></w:r></w:p></w:tc></w:tr>"
        "<w:tr><w:tc><w:p><w:r><w:t>PO Amount</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>Mandatory field, numeric</w:t></w:r></w:p></w:tc></w:tr>"
        "</w:tbl>"
    )


def build(out_path):
    body = [
        para_heading(1, "4. Purchase Orders"),
        para_text("This chapter describes the purchase order process."),
        para_heading(2, "4.1 Overview"),
        para_text("The PO module lets users create purchase orders."),
        para_heading(2, "4.2 Approval"),
        para_heading(3, "4.2.1 Approval Steps"),
        para_step("Step 1. Click Submit for Approval."),
        para_step("Step 2. Select the approver from the dropdown."),
        para_image("rId1", "Approval screen"),
        para_text("Figure 1: The approval screen."),
        para_heading(3, "4.2.2 Field Reference"),
        para_text("The following fields are mandatory on the PO form."),
        para_image("rId2", "Small icon"),
        para_image("rId2", "Small icon"),
        para_image("rId2", "Small icon"),
        para_image("rId3", "Low res screenshot"),
        table(),
    ]
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}" xmlns:a="{A}">
<w:body>
{''.join(body)}
<w:sectPr/>
</w:body>
</w:document>'''.encode("utf-8")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w") as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", PKG_RELS)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/_rels/document.xml.rels", DOC_RELS)
        zf.writestr("word/media/image1.png", make_png(800, 600, (100, 150, 200)))
        zf.writestr("word/media/image2.png", make_png(300, 300, (10, 10, 10)))
        zf.writestr("word/media/image3.png", make_png(200, 150, (250, 250, 250)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path, default=Path("sample-fsd.docx"))
    args = ap.parse_args()
    build(args.out)
    print(f"built {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
