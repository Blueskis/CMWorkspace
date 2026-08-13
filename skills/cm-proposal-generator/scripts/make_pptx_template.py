#!/usr/bin/env python3
"""Generate the generic PowerPoint template (the .potx stand-in for the firm's own).

    python make_pptx_template.py -o proposal-assets/templates/pptx-generic/pptx-generic.potx

The template it writes is the PowerPoint sibling of `templates/html-generic`: the same
nine layouts, the same palette, and — the point of the exercise — **the same placeholder
names**. A `proposal_plan.json` that renders to HTML renders to .pptx unchanged, because
both templates answer to `title`, `kicker`, `body`, `left`, `situation`, `metrics` and so
on. Nothing upstream of Stage 5 knows which target it is aimed at.

This exists so the pipeline can produce a real .pptx before the firm's approved template
is available. It is **not** the firm's template and must never be presented as one: it is
deliberately plain, and `render_pptx.py` works against any approved .potx the moment there
is one (see `template_map.json` for retargeting a plan onto its layout names).

Why generate it rather than commit a binary someone once made in PowerPoint: a generated
template is auditable. Every colour, font size and placeholder position is a line of
Python here rather than an opaque blob, so changing the house look is an edit, not a
redesign in another application. Re-run this script, then re-run `profile_template.py`.

Stdlib only — a .potx is a ZIP of XML.
"""

import argparse
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

EMU_PER_INCH = 914400
SLIDE_W_IN = 13.333
SLIDE_H_IN = 7.5

# Palette mirrors templates/html-generic/theme.css. The mapping into theme slots is what
# lets render_pptx.py stay template-relative: it asks for `accent1`, never for #1f6feb.
PALETTE = {
    "dk1": "14213D",  # --ink        headings, primary text
    "lt1": "FFFFFF",  # --canvas
    "dk2": "4A5568",  # --ink-soft   body text
    "lt2": "F6F8FB",  # --panel
    "accent1": "1F6FEB",  # --accent
    "accent2": "8A94A6",  # --muted
    "accent3": "DDE3EC",  # --rule
    "accent4": "B45309",  # --gap-amber
    "accent5": "FEF3C7",  # --gap-bg
    "accent6": "E8F0FE",  # --accent-dim
    "hlink": "1F6FEB",
    "folHlink": "8A94A6",
}

# Cambria/Calibri rather than the CSS's Segoe UI stack: both ship with Office on every
# platform, so the deck renders the same on the reviewer's machine as on ours.
MAJOR_FONT = "Cambria"
MINOR_FONT = "Calibri"

MARGIN = 0.62
CONTENT_W = SLIDE_W_IN - 2 * MARGIN

NS_P = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" ' \
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ' \
       'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'

XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def emu(inches):
    return int(round(inches * EMU_PER_INCH))


def xfrm(x, y, w, h):
    return (f'<a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/>'
            f'<a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm>')


# --- text style fragments --------------------------------------------------
#
# Every placeholder's look is declared here, in the layout, so a *slide* never has to
# set a font or a colour. That is the whole template-fidelity contract: if slide XML
# carries no <a:latin> and no <a:srgbClr>, it cannot have drifted off-template.


def run_props(sz, *, bold=False, colour="tx2", font="minor", caps=False, spc=None,
              italic=False):
    typeface = "+mj-lt" if font == "major" else "+mn-lt"
    attrs = f'sz="{sz}" b="{1 if bold else 0}" i="{1 if italic else 0}"'
    if caps:
        attrs += ' cap="all"'
    if spc is not None:
        attrs += f' spc="{spc}"'
    return (f'<a:defRPr {attrs}><a:solidFill><a:schemeClr val="{colour}"/></a:solidFill>'
            f'<a:latin typeface="{typeface}"/></a:defRPr>')


def lst_style(sz, *, bold=False, colour="tx2", font="minor", caps=False, spc=None,
              bullets=False, space_after=400, line=100000):
    """The <a:lstStyle> block a layout placeholder carries."""
    if bullets:
        bullet = ('<a:buClr><a:schemeClr val="accent1"/></a:buClr>'
                  '<a:buSzPct val="90000"/><a:buFont typeface="Arial"/><a:buChar char="&#8226;"/>')
        indent = 'marL="228600" indent="-228600"'
    else:
        bullet = "<a:buNone/>"
        indent = 'marL="0" indent="0"'
    return (f'<a:lstStyle><a:lvl1pPr {indent} algn="l">'
            f'<a:lnSpc><a:spcPct val="{line}"/></a:lnSpc>'
            f'<a:spcBef><a:spcPts val="0"/></a:spcBef>'
            f'<a:spcAft><a:spcPts val="{space_after}"/></a:spcAft>'
            f'{bullet}{run_props(sz, bold=bold, colour=colour, font=font, caps=caps, spc=spc)}'
            f'</a:lvl1pPr>'
            f'<a:lvl2pPr marL="514350" indent="-228600" algn="l">'
            f'<a:spcAft><a:spcPts val="{space_after}"/></a:spcAft>'
            f'{bullet}{run_props(max(sz - 200, 900), colour=colour, font=font)}'
            f'</a:lvl2pPr></a:lstStyle>')


def placeholder(shape_id, name, ph_type, idx, geom, styles, prompt, *, anchor="t"):
    """One placeholder shape on a layout."""
    ph_attrs = f'type="{ph_type}"' if idx is None else f'type="{ph_type}" idx="{idx}"'
    x, y, w, h = geom
    return (
        f'<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{shape_id}" name="{name}"/>'
        f'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
        f'<p:nvPr><p:ph {ph_attrs}/></p:nvPr>'
        f'</p:nvSpPr>'
        f'<p:spPr>{xfrm(x, y, w, h)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        f'<p:txBody><a:bodyPr anchor="{anchor}" wrap="square" lIns="0" tIns="45720" '
        f'rIns="0" bIns="45720"><a:normAutofit/></a:bodyPr>'
        f'{styles}'
        f'<a:p><a:r><a:rPr lang="en-GB"/><a:t>{prompt}</a:t></a:r></a:p></p:txBody></p:sp>'
    )


def plain_rect(shape_id, name, geom, fill_scheme):
    x, y, w, h = geom
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvSpPr/><p:nvPr/>'
        f'</p:nvSpPr>'
        f'<p:spPr>{xfrm(x, y, w, h)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:schemeClr val="{fill_scheme}"/></a:solidFill>'
        f'<a:ln><a:noFill/></a:ln></p:spPr>'
        f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-GB"/></a:p>'
        f'</p:txBody></p:sp>'
    )


def rule_line(shape_id, name, geom, colour_scheme, width_emu=12700):
    x, y, w, h = geom
    return (
        f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvCxnSpPr/>'
        f'<p:nvPr/></p:nvCxnSpPr>'
        f'<p:spPr>{xfrm(x, y, w, h)}<a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
        f'<a:ln w="{width_emu}"><a:solidFill><a:schemeClr val="{colour_scheme}"/></a:solidFill>'
        f'</a:ln></p:spPr></p:cxnSp>'
    )


# --- layout definitions ----------------------------------------------------
#
# Names on the left of each placeholder tuple are the contract with the plan format and
# with templates/html-generic/layouts.html. Renaming one here breaks every plan written
# against it, in exactly the way renaming a {{token}} there would.

BODY_TITLE = (MARGIN, 0.74, CONTENT_W, 0.78)
BODY_KICKER = (MARGIN, 0.40, CONTENT_W, 0.30)
BODY_FOOTER = (MARGIN, 6.78, CONTENT_W, 0.32)
BODY_TOP = 1.68
BODY_H = 4.98

TITLE_STYLE = lst_style(2600, colour="tx1", font="major", bold=True, space_after=0,
                        line=105000)
KICKER_STYLE = lst_style(1100, bold=True, colour="accent1", caps=True, spc=140,
                         space_after=0)
FOOTER_STYLE = lst_style(900, colour="accent2", space_after=0)
BODY_STYLE = lst_style(1800, bullets=True, space_after=500, line=108000)
COLHEAD_STYLE = lst_style(1100, bold=True, colour="accent2", caps=True, spc=80,
                          space_after=200)


def _col_split(fractions, gap=0.36):
    """Split the content width into columns by fraction, returning (x, w) pairs."""
    usable = CONTENT_W - gap * (len(fractions) - 1)
    out, cursor = [], MARGIN
    for frac in fractions:
        w = usable * frac
        out.append((round(cursor, 3), round(w, 3)))
        cursor += w + gap
    return out


LEFT_COL, RIGHT_COL = _col_split([0.5, 0.5])
CASE_MAIN, CASE_SIDE = _col_split([0.6, 0.4])

LAYOUTS = [
    {
        "id": "title-slide",
        "name": "Title Slide",
        "type": "title",
        "dark": False,
        "placeholders": [
            ("client", "body", 10, (0.9, 1.95, 11.5, 0.4),
             lst_style(1400, bold=True, colour="accent1", caps=True, spc=120, space_after=0),
             "Client legal name"),
            ("title", "ctrTitle", None, (0.9, 2.45, 11.5, 1.5),
             lst_style(4000, colour="tx1", font="major", bold=True, space_after=0, line=100000),
             "Engagement title"),
            ("subtitle", "body", 11, (0.9, 4.05, 11.5, 0.95),
             lst_style(1800, colour="tx2", space_after=0), "One-line positioning"),
            ("meta", "body", 12, (0.9, 5.75, 11.5, 0.7),
             lst_style(1100, colour="accent2", space_after=0),
             "Tender reference · submission date · draft status"),
        ],
        "decor": [("rule", (0.9, 5.62, 11.5, 0.0), "tx1", 25400)],
    },
    {
        "id": "section-header",
        "name": "Section Header",
        "type": "secHead",
        "dark": True,
        "placeholders": [
            ("kicker", "body", 10, (0.9, 2.55, 11.5, 0.34),
             lst_style(1200, bold=True, colour="accent1", caps=True, spc=140, space_after=0),
             "Kicker"),
            ("title", "title", None, (0.9, 2.98, 11.5, 1.2),
             lst_style(3400, colour="bg1", font="major", bold=True, space_after=0, line=105000),
             "Section title"),
            ("body", "body", 11, (0.9, 4.35, 8.2, 1.5),
             lst_style(1500, colour="bg2", space_after=300), "Optional standfirst"),
        ],
        "decor": [],
    },
    {
        "id": "title-and-content",
        "name": "Title and Content",
        "type": "obj",
        "dark": False,
        "placeholders": [
            ("kicker", "body", 10, BODY_KICKER, KICKER_STYLE, "Kicker"),
            ("title", "title", None, BODY_TITLE, TITLE_STYLE, "Slide title"),
            ("body", "body", 11, (MARGIN, BODY_TOP, CONTENT_W, BODY_H), BODY_STYLE,
             "Body content"),
            ("footer", "body", 12, BODY_FOOTER, FOOTER_STYLE, "Provenance footer"),
        ],
        "decor": [("rule", (MARGIN, 6.70, CONTENT_W, 0.0), "accent3", 9525)],
    },
    {
        "id": "two-content",
        "name": "Two Content",
        "type": "twoObj",
        "dark": False,
        "placeholders": [
            ("kicker", "body", 10, BODY_KICKER, KICKER_STYLE, "Kicker"),
            ("title", "title", None, BODY_TITLE, TITLE_STYLE, "Slide title"),
            ("left_heading", "body", 11, (LEFT_COL[0], BODY_TOP, LEFT_COL[1], 0.34),
             COLHEAD_STYLE, "Left column heading"),
            ("left", "body", 12, (LEFT_COL[0], BODY_TOP + 0.46, LEFT_COL[1], BODY_H - 0.46),
             lst_style(1600, bullets=True, space_after=450, line=108000), "Left column"),
            ("right_heading", "body", 13, (RIGHT_COL[0], BODY_TOP, RIGHT_COL[1], 0.34),
             COLHEAD_STYLE, "Right column heading"),
            ("right", "body", 14, (RIGHT_COL[0], BODY_TOP + 0.46, RIGHT_COL[1], BODY_H - 0.46),
             lst_style(1600, bullets=True, space_after=450, line=108000), "Right column"),
            ("footer", "body", 15, BODY_FOOTER, FOOTER_STYLE, "Provenance footer"),
        ],
        "decor": [
            ("rule", (LEFT_COL[0], BODY_TOP + 0.36, LEFT_COL[1], 0.0), "accent3", 9525),
            ("rule", (RIGHT_COL[0], BODY_TOP + 0.36, RIGHT_COL[1], 0.0), "accent3", 9525),
            ("rule", (MARGIN, 6.70, CONTENT_W, 0.0), "accent3", 9525),
        ],
    },
    {
        # Case studies carry the most text of any layout and overflow first, so this one
        # runs a step smaller than the body default — same reasoning as the CSS.
        "id": "case-study",
        "name": "Case Study",
        "type": "twoObj",
        "dark": False,
        "placeholders": [
            ("kicker", "body", 10, BODY_KICKER, KICKER_STYLE, "Kicker"),
            ("title", "title", None, BODY_TITLE, TITLE_STYLE, "Engagement title"),
            ("situation", "body", 11, (CASE_MAIN[0], BODY_TOP + 0.32, CASE_MAIN[1], 1.72),
             lst_style(1400, bullets=True, space_after=350), "Situation"),
            ("action", "body", 12, (CASE_MAIN[0], BODY_TOP + 2.42, CASE_MAIN[1], 2.56),
             lst_style(1400, bullets=True, space_after=350), "What we did"),
            ("outcome", "body", 13, (CASE_SIDE[0], BODY_TOP + 0.32, CASE_SIDE[1], 2.70),
             lst_style(1400, bullets=True, space_after=350), "Outcome"),
            ("metrics", "body", 14, (CASE_SIDE[0], BODY_TOP + 3.24, CASE_SIDE[1], 1.74),
             lst_style(1400, space_after=200), "Metrics"),
            ("footer", "body", 15, BODY_FOOTER, FOOTER_STYLE, "Provenance footer"),
        ],
        "decor": [
            ("rule", (MARGIN, 6.70, CONTENT_W, 0.0), "accent3", 9525),
        ],
        "labels": [
            ("Situation", (CASE_MAIN[0], BODY_TOP, CASE_MAIN[1], 0.30)),
            ("What we did", (CASE_MAIN[0], BODY_TOP + 2.10, CASE_MAIN[1], 0.30)),
            ("Outcome", (CASE_SIDE[0], BODY_TOP, CASE_SIDE[1], 0.30)),
        ],
    },
    {
        "id": "metric-row",
        "name": "Metric Row",
        "type": "obj",
        "dark": False,
        "placeholders": [
            ("kicker", "body", 10, BODY_KICKER, KICKER_STYLE, "Kicker"),
            ("title", "title", None, BODY_TITLE, TITLE_STYLE, "Slide title"),
            ("body", "body", 11, (MARGIN, BODY_TOP, CONTENT_W, 1.85), BODY_STYLE,
             "Optional lead-in"),
            ("metrics", "body", 12, (MARGIN, BODY_TOP + 2.05, CONTENT_W, BODY_H - 2.05),
             lst_style(1600, space_after=200), "Metric tiles"),
            ("footer", "body", 13, BODY_FOOTER, FOOTER_STYLE, "Provenance footer"),
        ],
        "decor": [("rule", (MARGIN, 6.70, CONTENT_W, 0.0), "accent3", 9525)],
    },
    {
        "id": "table",
        "name": "Table",
        "type": "tbl",
        "dark": False,
        "placeholders": [
            ("kicker", "body", 10, BODY_KICKER, KICKER_STYLE, "Kicker"),
            ("title", "title", None, BODY_TITLE, TITLE_STYLE, "Slide title"),
            ("body", "body", 11, (MARGIN, BODY_TOP, CONTENT_W, 1.05), BODY_STYLE,
             "Optional lead-in"),
            ("table", "body", 12, (MARGIN, BODY_TOP + 1.20, CONTENT_W, BODY_H - 1.20),
             lst_style(1200, space_after=0), "Table"),
            ("footer", "body", 13, BODY_FOOTER, FOOTER_STYLE, "Provenance footer"),
        ],
        "decor": [("rule", (MARGIN, 6.70, CONTENT_W, 0.0), "accent3", 9525)],
    },
    {
        "id": "timeline",
        "name": "Timeline",
        "type": "obj",
        "dark": False,
        "placeholders": [
            ("kicker", "body", 10, BODY_KICKER, KICKER_STYLE, "Kicker"),
            ("title", "title", None, BODY_TITLE, TITLE_STYLE, "Slide title"),
            ("body", "body", 11, (MARGIN, BODY_TOP, CONTENT_W, 1.05), BODY_STYLE,
             "Optional lead-in"),
            ("phases", "body", 12, (MARGIN, BODY_TOP + 1.20, CONTENT_W, BODY_H - 1.20),
             lst_style(1400, space_after=200), "Phases"),
            ("footer", "body", 13, BODY_FOOTER, FOOTER_STYLE, "Provenance footer"),
        ],
        "decor": [("rule", (MARGIN, 6.70, CONTENT_W, 0.0), "accent3", 9525)],
    },
    {
        "id": "team-grid",
        "name": "Team Grid",
        "type": "obj",
        "dark": False,
        "placeholders": [
            ("kicker", "body", 10, BODY_KICKER, KICKER_STYLE, "Kicker"),
            ("title", "title", None, BODY_TITLE, TITLE_STYLE, "Slide title"),
            ("members", "body", 11, (MARGIN, BODY_TOP, CONTENT_W, BODY_H),
             lst_style(1400, space_after=200), "Team members"),
            ("footer", "body", 12, BODY_FOOTER, FOOTER_STYLE, "Provenance footer"),
        ],
        "decor": [("rule", (MARGIN, 6.70, CONTENT_W, 0.0), "accent3", 9525)],
    },
]


# --- part builders ---------------------------------------------------------


def build_theme(name="Generic Business"):
    scheme = "".join(
        f'<a:{slot}><a:srgbClr val="{PALETTE[slot]}"/></a:{slot}>'
        for slot in ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3",
                     "accent4", "accent5", "accent6", "hlink", "folHlink")
    )
    # dk1/lt1 conventionally use sysClr; srgbClr is valid and keeps the palette literal.
    fill_styles = (
        '<a:fillStyleLst>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"><a:tint val="60000"/></a:schemeClr></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"><a:shade val="80000"/></a:schemeClr></a:solidFill>'
        '</a:fillStyleLst>'
    )
    line_styles = (
        '<a:lnStyleLst>'
        '<a:ln w="9525" cap="flat" cmpd="sng" algn="ctr"><a:solidFill>'
        '<a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>'
        '<a:ln w="15875" cap="flat" cmpd="sng" algn="ctr"><a:solidFill>'
        '<a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>'
        '<a:ln w="25400" cap="flat" cmpd="sng" algn="ctr"><a:solidFill>'
        '<a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>'
        '</a:lnStyleLst>'
    )
    effect_styles = (
        '<a:effectStyleLst>'
        '<a:effectStyle><a:effectLst/></a:effectStyle>'
        '<a:effectStyle><a:effectLst/></a:effectStyle>'
        '<a:effectStyle><a:effectLst/></a:effectStyle>'
        '</a:effectStyleLst>'
    )
    bg_styles = (
        '<a:bgFillStyleLst>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"><a:tint val="95000"/></a:schemeClr></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"><a:shade val="90000"/></a:schemeClr></a:solidFill>'
        '</a:bgFillStyleLst>'
    )
    return (
        XML_DECL +
        f'<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        f'name="{name}"><a:themeElements>'
        f'<a:clrScheme name="{name}">{scheme}</a:clrScheme>'
        f'<a:fontScheme name="{name}">'
        f'<a:majorFont><a:latin typeface="{MAJOR_FONT}"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
        f'<a:minorFont><a:latin typeface="{MINOR_FONT}"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
        f'</a:fontScheme>'
        f'<a:fmtScheme name="{name}">{fill_styles}{line_styles}{effect_styles}{bg_styles}</a:fmtScheme>'
        f'</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>'
    )


def build_master():
    """Slide master: the default title/body geometry plus the deck's text styles."""
    shapes = [
        placeholder(2, "Title Placeholder 1", "title", None, BODY_TITLE, TITLE_STYLE,
                    "Click to edit Master title style"),
        placeholder(3, "Text Placeholder 2", "body", 1,
                    (MARGIN, BODY_TOP, CONTENT_W, BODY_H), BODY_STYLE,
                    "Click to edit Master text styles"),
    ]

    def level(n, sz, marl, indent):
        return (f'<a:lvl{n}pPr marL="{marl}" indent="{indent}" algn="l">'
                f'<a:lnSpc><a:spcPct val="108000"/></a:lnSpc>'
                f'<a:spcAft><a:spcPts val="500"/></a:spcAft>'
                f'<a:buClr><a:schemeClr val="accent1"/></a:buClr>'
                f'<a:buSzPct val="90000"/><a:buFont typeface="Arial"/><a:buChar char="&#8226;"/>'
                f'{run_props(sz)}</a:lvl{n}pPr>')

    body_style = "".join([
        level(1, 1800, 228600, -228600),
        level(2, 1600, 514350, -228600),
        level(3, 1400, 800100, -228600),
        level(4, 1300, 1085850, -228600),
    ])
    other_style = ('<a:lvl1pPr marL="0" algn="l"><a:buNone/>' + run_props(1600) +
                   '</a:lvl1pPr>')

    return (
        XML_DECL +
        f'<p:sldMaster {NS_P}><p:cSld><p:bg><p:bgPr>'
        f'<a:solidFill><a:schemeClr val="bg1"/></a:solidFill><a:effectLst/>'
        f'</p:bgPr></p:bg><p:spTree>'
        f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f'{"".join(shapes)}</p:spTree></p:cSld>'
        f'<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" '
        f'accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
        f'accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        f'<p:sldLayoutIdLst>'
        + "".join(f'<p:sldLayoutId id="{2147483649 + i}" r:id="rId{i + 1}"/>'
                  for i in range(len(LAYOUTS)))
        + f'</p:sldLayoutIdLst>'
        f'<p:txStyles>'
        f'<p:titleStyle><a:lvl1pPr algn="l"><a:buNone/>'
        f'{run_props(2600, bold=True, colour="tx1", font="major")}</a:lvl1pPr></p:titleStyle>'
        f'<p:bodyStyle>{body_style}</p:bodyStyle>'
        f'<p:otherStyle>{other_style}</p:otherStyle>'
        f'</p:txStyles></p:sldMaster>'
    )


def build_layout(spec):
    shapes = []
    next_id = 2

    if spec["dark"]:
        shapes.append(plain_rect(next_id, "Background Panel",
                                 (0, 0, SLIDE_W_IN, SLIDE_H_IN), "tx1"))
        next_id += 1

    for name, geom, colour, width in (
        (d[0], d[1], d[2], d[3]) for d in spec.get("decor", [])
    ):
        shapes.append(rule_line(next_id, f"Rule {next_id}", geom, colour, width))
        next_id += 1

    for text, geom in spec.get("labels", []):
        shapes.append(
            f'<p:sp><p:nvSpPr><p:cNvPr id="{next_id}" name="Label {next_id}"/>'
            f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr>{xfrm(*geom)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0"/>'
            f'{COLHEAD_STYLE}<a:p><a:r><a:rPr lang="en-GB"/><a:t>{text}</a:t></a:r></a:p>'
            f'</p:txBody></p:sp>'
        )
        next_id += 1

    for name, ph_type, idx, geom, styles, prompt in spec["placeholders"]:
        anchor = "ctr" if spec["id"] == "title-slide" and name == "title" else "t"
        shapes.append(placeholder(next_id, name, ph_type, idx, geom, styles, prompt,
                                  anchor=anchor))
        next_id += 1

    return (
        XML_DECL +
        f'<p:sldLayout {NS_P} type="{spec["type"]}" preserve="1">'
        f'<p:cSld name="{spec["name"]}"><p:spTree>'
        f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f'{"".join(shapes)}</p:spTree></p:cSld>'
        f'<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
    )


def build_notes_master():
    body = placeholder(3, "Notes Placeholder 2", "body", 1, (0.75, 4.4, 6.0, 4.6),
                       lst_style(1200, space_after=200), "Speaker notes")
    return (
        XML_DECL +
        f'<p:notesMaster {NS_P}><p:cSld><p:spTree>'
        f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f'{body}</p:spTree></p:cSld>'
        f'<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" '
        f'accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
        f'accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        f'<p:notesStyle><a:lvl1pPr marL="0" algn="l"><a:buNone/>{run_props(1200)}'
        f'</a:lvl1pPr></p:notesStyle></p:notesMaster>'
    )


def build_presentation():
    return (
        XML_DECL +
        f'<p:presentation {NS_P} saveSubsetFonts="1">'
        f'<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f'<p:notesMasterIdLst><p:notesMasterId r:id="rId2"/></p:notesMasterIdLst>'
        f'<p:sldSz cx="{emu(SLIDE_W_IN)}" cy="{emu(SLIDE_H_IN)}"/>'
        f'<p:notesSz cx="6858000" cy="9144000"/>'
        f'<p:defaultTextStyle><a:lvl1pPr marL="0" algn="l"><a:buNone/>{run_props(1800)}'
        f'</a:lvl1pPr></p:defaultTextStyle></p:presentation>'
    )


def rels(pairs):
    body = "".join(
        f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
        f'{typ}" Target="{target}"/>'
        for rid, typ, target in pairs
    )
    return (XML_DECL +
            f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            f'relationships">{body}</Relationships>')


REL = "officeDocument/2006/relationships"
PKG_REL = "package/2006/relationships/metadata"


def build_package():
    parts = {}
    layout_names = [f"ppt/slideLayouts/slideLayout{i + 1}.xml" for i in range(len(LAYOUTS))]

    overrides = [
        ("/ppt/presentation.xml",
         "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"),
        ("/ppt/slideMasters/slideMaster1.xml",
         "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"),
        ("/ppt/notesMasters/notesMaster1.xml",
         "application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"),
        ("/ppt/presProps.xml",
         "application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"),
        ("/ppt/viewProps.xml",
         "application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"),
        ("/ppt/tableStyles.xml",
         "application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"),
        ("/ppt/theme/theme1.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
        ("/ppt/theme/theme2.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
        ("/docProps/core.xml",
         "application/vnd.openxmlformats-package.core-properties+xml"),
        ("/docProps/app.xml",
         "application/vnd.openxmlformats-officedocument.extended-properties+xml"),
    ] + [
        (f"/{n}", "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml")
        for n in layout_names
    ]

    parts["[Content_Types].xml"] = (
        XML_DECL +
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Default Extension="jpeg" ContentType="image/jpeg"/>'
        '<Default Extension="jpg" ContentType="image/jpeg"/>' +
        "".join(f'<Override PartName="{p}" ContentType="{c}"/>' for p, c in overrides) +
        '</Types>'
    )

    parts["_rels/.rels"] = rels([
        ("rId1", f"{REL}/officeDocument", "ppt/presentation.xml"),
        ("rId2", f"{PKG_REL}/core-properties", "docProps/core.xml"),
        ("rId3", f"{REL}/extended-properties", "docProps/app.xml"),
    ])

    parts["ppt/presentation.xml"] = build_presentation()
    parts["ppt/_rels/presentation.xml.rels"] = rels([
        ("rId1", f"{REL}/slideMaster", "slideMasters/slideMaster1.xml"),
        ("rId2", f"{REL}/notesMaster", "notesMasters/notesMaster1.xml"),
        ("rId3", f"{REL}/presProps", "presProps.xml"),
        ("rId4", f"{REL}/viewProps", "viewProps.xml"),
        ("rId5", f"{REL}/theme", "theme/theme1.xml"),
        ("rId6", f"{REL}/tableStyles", "tableStyles.xml"),
    ])

    parts["ppt/slideMasters/slideMaster1.xml"] = build_master()
    parts["ppt/slideMasters/_rels/slideMaster1.xml.rels"] = rels(
        [(f"rId{i + 1}", f"{REL}/slideLayout", f"../slideLayouts/slideLayout{i + 1}.xml")
         for i in range(len(LAYOUTS))]
        + [(f"rId{len(LAYOUTS) + 1}", f"{REL}/theme", "../theme/theme1.xml")]
    )

    for i, spec in enumerate(LAYOUTS):
        parts[layout_names[i]] = build_layout(spec)
        parts[f"ppt/slideLayouts/_rels/slideLayout{i + 1}.xml.rels"] = rels([
            ("rId1", f"{REL}/slideMaster", "../slideMasters/slideMaster1.xml"),
        ])

    parts["ppt/notesMasters/notesMaster1.xml"] = build_notes_master()
    parts["ppt/notesMasters/_rels/notesMaster1.xml.rels"] = rels([
        ("rId1", f"{REL}/theme", "../theme/theme2.xml"),
    ])

    parts["ppt/theme/theme1.xml"] = build_theme()
    parts["ppt/theme/theme2.xml"] = build_theme("Generic Business Notes")

    parts["ppt/presProps.xml"] = XML_DECL + f'<p:presentationPr {NS_P}/>'
    parts["ppt/viewProps.xml"] = XML_DECL + f'<p:viewPr {NS_P}/>'
    parts["ppt/tableStyles.xml"] = (
        XML_DECL +
        '<a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>'
    )

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts["docProps/core.xml"] = (
        XML_DECL +
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
        'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/'
        'XMLSchema-instance">'
        '<dc:title>Generic business proposal template</dc:title>'
        '<dc:subject>Stand-in template for cm-proposal-generator — not an approved '
        'firm template</dc:subject>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{stamp}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{stamp}</dcterms:modified>'
        '</cp:coreProperties>'
    )
    parts["docProps/app.xml"] = (
        XML_DECL +
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
        'extended-properties" xmlns:vt="http://schemas.openxmlformats.org/'
        'officeDocument/2006/docPropsVTypes">'
        '<Application>cm-proposal-generator make_pptx_template.py</Application>'
        f'<Slides>0</Slides><Notes>0</Notes>'
        '</Properties>'
    )
    return parts


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path,
                    default=Path("proposal-assets/templates/pptx-generic/pptx-generic.potx"))
    args = ap.parse_args()

    parts = build_package()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    # Fixed timestamp so re-running with no source change produces an identical file —
    # a template that churns its bytes every build is noise in every diff.
    fixed = (2026, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, date_time=fixed)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, parts[name])

    size_kb = args.out.stat().st_size / 1024
    print(f"Wrote {args.out} ({size_kb:.1f} KB, {len(parts)} parts)")
    print(f"  {len(LAYOUTS)} layouts: {', '.join(spec['id'] for spec in LAYOUTS)}")
    print(f"  slide size {SLIDE_W_IN}in x {SLIDE_H_IN}in (16:9)")
    print("  Re-run profile_template.py so the profile stays in step.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
