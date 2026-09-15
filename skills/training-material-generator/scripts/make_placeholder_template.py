#!/usr/bin/env python3
"""Build a plain, undecorated .pptx template to build a first draft on when no approved
client template is available yet.

    python make_placeholder_template.py -o training/<run>/template/placeholder.pptx

**This is a stand-in, not the client's approved template.** SKILL.md is explicit that the
skill should stop and ask for the real template rather than build a lookalike — use this
only when the practitioner has explicitly accepted a placeholder for a first pass, and say
so plainly at handover. Swapping in the real template later changes nothing upstream of
Stage 4: same deck_plan.json, same layout keys, just re-profile and rebuild against it.

Six layouts, chosen to cover every block kind the module library and diagram/screenshot
pipeline need: title-slide, section-header, title-and-content, two-content,
picture-with-caption (a real picture placeholder, so screenshot placement doesn't need
the free-floating fallback), and diagram-full (one large content placeholder sized for a
native diagram). A neutral grey/blue palette on white, Calibri throughout (a pptx-skill
"safe" font — see that skill's Typography section) — deliberately undecorated, since the
whole point of a placeholder is that it doesn't pretend to be a finished brand.

Stdlib only. Hand-authors the OOXML package directly (no pptxgenjs — pptxgenjs makes
slides, not the slideLayout/slideMaster/theme structure a template needs).
"""

import argparse
import sys
import zipfile
from pathlib import Path

EMU_PER_INCH = 914400
SLIDE_W_IN, SLIDE_H_IN = 13.333, 7.5  # widescreen 16:9, matches pptxgenjs's LAYOUT_WIDE

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


def emu(inches):
    return int(round(inches * EMU_PER_INCH))


def xfrm(x, y, w, h):
    return f'<a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/>'


# ---------------------------------------------------------------------------
# Layout definitions: (part_stem, name, type_attr, [placeholders])
# Each placeholder: (ph_type, idx_or_None, name, x, y, w, h, prompt)
# ---------------------------------------------------------------------------

M = 0.6  # standard margin, inches
TITLE_H = 1.1

LAYOUTS = [
    ("slideLayout1", "Title Slide", "title", [
        ("ctrTitle", None, "Title", M, 2.6, SLIDE_W_IN - 2 * M, 1.3, "Click to add title"),
        ("subTitle", "1", "Subtitle", M, 4.0, SLIDE_W_IN - 2 * M, 1.0, "Click to add subtitle"),
    ]),
    ("slideLayout2", "Section Header", "secHead", [
        ("title", None, "Title", M, 2.9, SLIDE_W_IN - 2 * M, 1.4, "Click to add section title"),
        ("body", "1", "Text", M, 4.5, SLIDE_W_IN - 2 * M, 1.0, "Click to add text"),
    ]),
    ("slideLayout3", "Title and Content", "obj", [
        ("title", None, "Title", M, M, SLIDE_W_IN - 2 * M, TITLE_H, "Click to add title"),
        ("body", "1", "Content", M, M + TITLE_H + 0.2, SLIDE_W_IN - 2 * M, SLIDE_H_IN - M - TITLE_H - 0.2 - M, "Click to add text"),
    ]),
    ("slideLayout4", "Two Content", "twoObj", [
        ("title", None, "Title", M, M, SLIDE_W_IN - 2 * M, TITLE_H, "Click to add title"),
        ("body", "1", "Left Content", M, M + TITLE_H + 0.2, (SLIDE_W_IN - 2 * M - 0.4) / 2, SLIDE_H_IN - M - TITLE_H - 0.2 - M, "Click to add text"),
        ("body", "2", "Right Content", M + (SLIDE_W_IN - 2 * M - 0.4) / 2 + 0.4, M + TITLE_H + 0.2, (SLIDE_W_IN - 2 * M - 0.4) / 2, SLIDE_H_IN - M - TITLE_H - 0.2 - M, "Click to add text"),
    ]),
    ("slideLayout5", "Picture with Caption", "picTx", [
        ("title", None, "Title", M, M, SLIDE_W_IN - 2 * M, 0.7, "Click to add title"),
        ("pic", "1", "Picture Placeholder", M, M + 0.9, SLIDE_W_IN - 2 * M, SLIDE_H_IN - M - 0.9 - M - 0.7, "Click icon to add picture"),
        ("body", "2", "Caption", M, SLIDE_H_IN - M - 0.6, SLIDE_W_IN - 2 * M, 0.6, "Click to add caption"),
    ]),
    ("slideLayout6", "Diagram Full", "obj", [
        ("title", None, "Title", M, M, SLIDE_W_IN - 2 * M, 0.9, "Click to add title"),
        ("body", "1", "Diagram Area", M, M + 1.1, SLIDE_W_IN - 2 * M, SLIDE_H_IN - M - 1.1 - M, "Diagram placeholder"),
    ]),
]

THEME_COLORS = {
    "dk1": "000000", "lt1": "FFFFFF", "dk2": "2B2E33", "lt2": "EDEFF2",
    "accent1": "355C7D", "accent2": "6C8EBF", "accent3": "8CA0B3",
    "accent4": "C9AE5D", "accent5": "5E8C6A", "accent6": "9B6A6C",
    "hlink": "355C7D", "folHlink": "6C8EBF",
}
FONT = "Calibri"


def content_types_xml(n_layouts):
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for i in range(1, n_layouts + 1):
        overrides.append(
            f'<Override PartName="/ppt/slideLayouts/slideLayout{i}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        )
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Types xmlns="{CT_NS}">'
        f'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        f'<Default Extension="xml" ContentType="application/xml"/>'
        f'<Default Extension="png" ContentType="image/png"/>'
        f'<Default Extension="jpeg" ContentType="image/jpeg"/>'
        f'{"".join(overrides)}</Types>'
    )


def pkg_rels_xml():
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NS}">'
        f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
        f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        f'<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        f'</Relationships>'
    )


def core_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<dc:title>Training Deck Placeholder Template</dc:title>'
        '<dc:creator>training-material-generator</dc:creator>'
        '</cp:coreProperties>'
    )


def app_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>training-material-generator</Application></Properties>'
    )


def presentation_xml(n_layouts):
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:presentation xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">'
        f'<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rIdMaster1"/></p:sldMasterIdLst>'
        f'<p:sldIdLst><p:sldId id="256" r:id="rIdSlide1"/></p:sldIdLst>'
        f'<p:sldSz cx="{emu(SLIDE_W_IN)}" cy="{emu(SLIDE_H_IN)}" type="screen16x9"/>'
        f'<p:notesSz cx="{emu(SLIDE_H_IN)}" cy="{emu(SLIDE_W_IN)}"/>'
        f'</p:presentation>'
    )


def presentation_rels_xml(n_layouts):
    rels = [
        f'<Relationship Id="rIdMaster1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
        f'<Relationship Id="rIdSlide1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>',
        f'<Relationship Id="rIdTheme1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>',
    ]
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL_NS}">{"".join(rels)}</Relationships>'


def theme_xml():
    def clr(slot):
        val = THEME_COLORS[slot]
        if slot in ("dk1", "lt1"):
            sysval = "windowText" if slot == "dk1" else "window"
            return f'<a:{slot}><a:sysClr val="{sysval}" lastClr="{val}"/></a:{slot}>'
        return f'<a:{slot}><a:srgbClr val="{val}"/></a:{slot}>'

    scheme_slots = ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6", "hlink", "folHlink"]
    clr_scheme = "".join(clr(s) for s in scheme_slots)
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="{A_NS}" name="Placeholder Theme">
  <a:themeElements>
    <a:clrScheme name="Placeholder">{clr_scheme}</a:clrScheme>
    <a:fontScheme name="Placeholder">
      <a:majorFont><a:latin typeface="{FONT}"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
      <a:minorFont><a:latin typeface="{FONT}"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Placeholder">
      <a:fillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
      </a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
        <a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
        <a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
      </a:effectStyleLst>
      <a:bgFillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
      </a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
</a:theme>'''


def placeholder_sp(idx_counter, ph_type, ph_idx, name, x, y, w, h, prompt, body_style=False):
    sid = next(idx_counter)
    idx_attr = f' idx="{ph_idx}"' if ph_idx is not None else ""
    type_attr = f' type="{ph_type}"'
    align = ' algn="ctr"' if ph_type in ("ctrTitle", "title") else ""
    return f'''<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{sid}" name="{name}"/>
    <p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
    <p:nvPr><p:ph{type_attr}{idx_attr}/></p:nvPr>
  </p:nvSpPr>
  <p:spPr><a:xfrm>{xfrm(x, y, w, h)}</a:xfrm></p:spPr>
  <p:txBody>
    <a:bodyPr/>
    <a:lstStyle/>
    <a:p><a:pPr{align}/><a:r><a:rPr lang="en-US"/><a:t>{prompt}</a:t></a:r></a:p>
  </p:txBody>
</p:sp>'''


def layout_xml(part_stem, name, type_attr, placeholders):
    idx_counter = iter(range(2, 2 + len(placeholders) + 1))
    shapes = "\n".join(
        placeholder_sp(idx_counter, ph_type, ph_idx, nm, x, y, w, h, prompt)
        for ph_type, ph_idx, nm, x, y, w, h, prompt in placeholders
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}" type="{type_attr}" preserve="1">
  <p:cSld name="{name}">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      {shapes}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>'''


def layout_rels_xml():
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NS}">'
        f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
        f'</Relationships>'
    )


def slide_master_xml(n_layouts):
    layout_ids = "".join(
        f'<p:sldLayoutId id="{2147483649 + i}" r:id="rIdLayout{i + 1}"/>' for i in range(n_layouts)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:schemeClr val="bg1"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="Title Placeholder"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
        <p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
        <p:spPr><a:xfrm>{xfrm(M, M, SLIDE_W_IN - 2 * M, TITLE_H)}</a:xfrm></p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US"/><a:t>Master title</a:t></a:r></a:p></p:txBody>
      </p:sp>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="3" name="Body Placeholder"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
        <p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr>
        <p:spPr><a:xfrm>{xfrm(M, M + TITLE_H + 0.2, SLIDE_W_IN - 2 * M, SLIDE_H_IN - M - TITLE_H - 0.2 - M)}</a:xfrm></p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US"/><a:t>Master body</a:t></a:r></a:p></p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst>{layout_ids}</p:sldLayoutIdLst>
</p:sldMaster>'''


def slide_master_rels_xml(n_layouts):
    rels = [f'<Relationship Id="rIdTheme1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>']
    for i in range(n_layouts):
        rels.append(
            f'<Relationship Id="rIdLayout{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
            f'Target="../slideLayouts/slideLayout{i + 1}.xml"/>'
        )
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL_NS}">{"".join(rels)}</Relationships>'


def cover_slide_xml():
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="Title 1"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
        <p:nvPr><p:ph type="ctrTitle"/></p:nvPr></p:nvSpPr>
        <p:spPr/>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="ctr"/><a:r><a:rPr lang="en-US"/><a:t>Training Deck — Placeholder Template</a:t></a:r></a:p></p:txBody>
      </p:sp>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="3" name="Subtitle 2"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>
        <p:nvPr><p:ph type="subTitle" idx="1"/></p:nvPr></p:nvSpPr>
        <p:spPr/>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="ctr"/><a:r><a:rPr lang="en-US"/><a:t>Not the client's approved template — swap this out before final delivery</a:t></a:r></a:p></p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>'''


def slide_rels_xml():
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NS}">'
        f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        f'</Relationships>'
    )


def build(out_path):
    n_layouts = len(LAYOUTS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml(n_layouts))
        zf.writestr("_rels/.rels", pkg_rels_xml())
        zf.writestr("docProps/core.xml", core_xml())
        zf.writestr("docProps/app.xml", app_xml())
        zf.writestr("ppt/presentation.xml", presentation_xml(n_layouts))
        zf.writestr("ppt/_rels/presentation.xml.rels", presentation_rels_xml(n_layouts))
        zf.writestr("ppt/theme/theme1.xml", theme_xml())
        zf.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml(n_layouts))
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels_xml(n_layouts))
        for part_stem, name, type_attr, placeholders in LAYOUTS:
            zf.writestr(f"ppt/slideLayouts/{part_stem}.xml", layout_xml(part_stem, name, type_attr, placeholders))
            zf.writestr(f"ppt/slideLayouts/_rels/{part_stem}.xml.rels", layout_rels_xml())
        zf.writestr("ppt/slides/slide1.xml", cover_slide_xml())
        zf.writestr("ppt/slides/_rels/slide1.xml.rels", slide_rels_xml())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path, default=Path("placeholder.pptx"))
    args = ap.parse_args()
    build(args.out)
    print(f"built {len(LAYOUTS)}-layout placeholder template -> {args.out}")
    print("NOT an approved client template — say so at handover.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
