#!/usr/bin/env python3
"""Build a small synthetic .pptx *source document* (not a template) exercising
map_source.py's and extract_assets.py's pptx paths.

    python make_pptx_fixture.py -o /tmp/sample-source.pptx

Two slides: a title slide with no image, and a slide with a numbered-step body plus one
embedded 640x480 screenshot resolved through a real slide relationship — this is the path
that most differs from the .docx path (per-slide rels rather than one document-wide rels
part), so it needs its own fixture rather than reusing the docx one.

Stdlib only.
"""

import argparse
import struct
import sys
import zipfile
import zlib
from pathlib import Path

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"

CONTENT_TYPES = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
</Types>'''


def make_png(w, h, color=(50, 60, 70)):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    row = bytes(color) * w
    raw = (b"\x00" + row) * h
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def slide_plain(title, body):
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="{P}" xmlns:a="{A}">
<p:cSld><p:spTree>
<p:sp><p:nvSpPr><p:cNvPr id="1" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
<p:txBody><a:p><a:r><a:t>{title}</a:t></a:r></a:p></p:txBody></p:sp>
<p:sp><p:nvSpPr><p:cNvPr id="2" name="Body"/><p:cNvSpPr/><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr>
<p:txBody><a:p><a:r><a:t>{body}</a:t></a:r></a:p></p:txBody></p:sp>
</p:spTree></p:cSld></p:sld>'''.encode("utf-8")


def slide_with_pic(title, rid):
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<p:cSld><p:spTree>
<p:sp><p:nvSpPr><p:cNvPr id="1" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
<p:txBody><a:p><a:r><a:t>{title}</a:t></a:r></a:p></p:txBody></p:sp>
<p:pic><p:nvPicPr><p:cNvPr id="2" name="Screenshot" descr="Approval dialog"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
<p:blipFill><a:blip r:embed="{rid}"/></p:blipFill>
<p:spPr/></p:pic>
</p:spTree></p:cSld></p:sld>'''.encode("utf-8")


SLIDE2_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>'''.encode("utf-8")


def build(out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w") as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("ppt/slides/slide1.xml", slide_plain("Welcome", "This deck covers PO approval."))
        zf.writestr("ppt/slides/slide2.xml", slide_with_pic("Approval Steps", "rId1"))
        zf.writestr("ppt/slides/_rels/slide2.xml.rels", SLIDE2_RELS)
        zf.writestr("ppt/media/image1.png", make_png(640, 480))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path, default=Path("sample-source.pptx"))
    args = ap.parse_args()
    build(args.out)
    print(f"built {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
