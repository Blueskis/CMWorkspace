#!/usr/bin/env python3
"""Generate the awkward .pptx templates the layout mapper and assembler must survive.

    python test/make-template-matrix.py -o test/fixtures/templates

The friendly 6-layout case is already covered by the skill's own
make_placeholder_template.py. These are the shapes a real client template throws at us
that a happy-path fixture never would:

  no-picture.pptx     no `pic` placeholder anywhere — forces the free-floating-picture
                      fallback in map-layouts.js / build-pptx.js
  two-masters.pptx    two slideMasters with layouts under each — a very common corporate
                      shape (e.g. a light and a dark master)
  with-examples.pptx  ships 3 example slides that must be dropped from the built deck
  odd-idx.pptx        placeholders numbered idx="7"/"12" and named in another language,
                      to prove nothing keys off idx ordering or English layout names
  minimal.pptx        exactly one usable layout — everything must degrade onto it

Stdlib only. Reuses the skill's own template writer for the parts that are identical.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "training-material-generator" / "scripts"))
import make_placeholder_template as base  # noqa: E402

P_NS = base.P_NS
A_NS = base.A_NS
REL_NS = base.REL_NS
M = base.M
SLIDE_W_IN = base.SLIDE_W_IN
SLIDE_H_IN = base.SLIDE_H_IN
TITLE_H = base.TITLE_H


def layout_variant(name, type_attr, placeholders):
    return (None, name, type_attr, placeholders)


# (ph_type, idx, name, x, y, w, h, prompt)
TITLE_PH = ("title", None, "Title", M, M, SLIDE_W_IN - 2 * M, TITLE_H, "Click to add title")
BODY_PH = ("body", "1", "Content", M, M + TITLE_H + 0.2, SLIDE_W_IN - 2 * M,
           SLIDE_H_IN - M - TITLE_H - 0.2 - M, "Click to add text")


def write_template(out_path, layouts, n_masters=1, n_example_slides=0):
    """layouts: list of (part_stem, name, type_attr, placeholders)."""
    n_layouts = len(layouts)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for i in range(1, n_masters + 1):
        overrides.append(
            f'<Override PartName="/ppt/slideMasters/slideMaster{i}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        )
        # Each master needs its OWN theme part — sharing one across masters is invalid
        # OOXML, which the pptx skill's validate.py correctly rejects.
        if i > 1:
            overrides.append(
                f'<Override PartName="/ppt/theme/theme{i}.xml" '
                f'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
            )
    for i in range(1, n_layouts + 1):
        overrides.append(
            f'<Override PartName="/ppt/slideLayouts/slideLayout{i}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        )
    for i in range(1, n_example_slides + 1):
        overrides.append(
            f'<Override PartName="/ppt/slides/slide{i}.xml" '
            f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        )

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{base.CT_NS}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Default Extension="jpeg" ContentType="image/jpeg"/>'
        f'{"".join(overrides)}</Types>'
    )

    # presentation.xml: master id list + slide id list
    master_ids = "".join(
        f'<p:sldMasterId id="{2147483648 + i}" r:id="rIdMaster{i + 1}"/>' for i in range(n_masters)
    )
    slide_ids = "".join(
        f'<p:sldId id="{256 + i}" r:id="rIdSlide{i + 1}"/>' for i in range(n_example_slides)
    )
    presentation = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:presentation xmlns:a="{A_NS}" xmlns:r="{base.R_NS}" xmlns:p="{P_NS}">'
        f'<p:sldMasterIdLst>{master_ids}</p:sldMasterIdLst>'
        f'<p:sldIdLst>{slide_ids}</p:sldIdLst>'
        f'<p:sldSz cx="{base.emu(SLIDE_W_IN)}" cy="{base.emu(SLIDE_H_IN)}" type="screen16x9"/>'
        f'<p:notesSz cx="{base.emu(SLIDE_H_IN)}" cy="{base.emu(SLIDE_W_IN)}"/>'
        '</p:presentation>'
    )

    pres_rels = [
        f'<Relationship Id="rIdTheme1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
    ]
    for i in range(n_masters):
        pres_rels.append(
            f'<Relationship Id="rIdMaster{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
            f'Target="slideMasters/slideMaster{i + 1}.xml"/>'
        )
    for i in range(n_example_slides):
        pres_rels.append(
            f'<Relationship Id="rIdSlide{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            f'Target="slides/slide{i + 1}.xml"/>'
        )
    pres_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{REL_NS}">{"".join(pres_rels)}</Relationships>'
    )

    # Split layouts across masters as evenly as possible.
    per_master = [[] for _ in range(n_masters)]
    for i in range(n_layouts):
        per_master[i % n_masters].append(i + 1)

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", base.pkg_rels_xml())
        zf.writestr("docProps/core.xml", base.core_xml())
        zf.writestr("docProps/app.xml", base.app_xml())
        zf.writestr("ppt/presentation.xml", presentation)
        zf.writestr("ppt/_rels/presentation.xml.rels", pres_rels_xml)
        for m_i in range(n_masters):
            zf.writestr(f"ppt/theme/theme{m_i + 1}.xml", base.theme_xml())

            layout_ids = "".join(
                f'<p:sldLayoutId id="{2147483649 + n}" r:id="rIdLayout{n}"/>' for n in per_master[m_i]
            )
            master = re.sub(
                r"<p:sldLayoutIdLst>.*?</p:sldLayoutIdLst>",
                f"<p:sldLayoutIdLst>{layout_ids}</p:sldLayoutIdLst>",
                base.slide_master_xml(0),
                flags=re.DOTALL,
            )
            zf.writestr(f"ppt/slideMasters/slideMaster{m_i + 1}.xml", master)

            rels = [
                f'<Relationship Id="rIdTheme1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" '
                f'Target="../theme/theme{m_i + 1}.xml"/>'
            ]
            for n in per_master[m_i]:
                rels.append(
                    f'<Relationship Id="rIdLayout{n}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
                    f'Target="../slideLayouts/slideLayout{n}.xml"/>'
                )
            zf.writestr(
                f"ppt/slideMasters/_rels/slideMaster{m_i + 1}.xml.rels",
                f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL_NS}">{"".join(rels)}</Relationships>',
            )

        for i, (_stem, name, type_attr, phs) in enumerate(layouts, start=1):
            zf.writestr(
                f"ppt/slideLayouts/slideLayout{i}.xml",
                base.layout_xml(f"slideLayout{i}", name, type_attr, phs),
            )
            owning_master = next(m_i for m_i in range(n_masters) if i in per_master[m_i]) + 1
            zf.writestr(
                f"ppt/slideLayouts/_rels/slideLayout{i}.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<Relationships xmlns="{REL_NS}">'
                f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
                f'Target="../slideMasters/slideMaster{owning_master}.xml"/></Relationships>',
            )

        for i in range(1, n_example_slides + 1):
            zf.writestr(f"ppt/slides/slide{i}.xml", base.cover_slide_xml())
            zf.writestr(
                f"ppt/slides/_rels/slide{i}.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<Relationships xmlns="{REL_NS}">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
                'Target="../slideLayouts/slideLayout1.xml"/></Relationships>',
            )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", type=Path, default=Path("test/fixtures/templates"))
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    # 1. no picture placeholder anywhere
    write_template(out / "no-picture.pptx", [
        layout_variant("Title Slide", "title", [
            ("ctrTitle", None, "Title", M, 2.6, SLIDE_W_IN - 2 * M, 1.3, "Title"),
            ("subTitle", "1", "Subtitle", M, 4.0, SLIDE_W_IN - 2 * M, 1.0, "Subtitle"),
        ]),
        layout_variant("Body", "obj", [TITLE_PH, BODY_PH]),
        layout_variant("Divider", "secHead", [
            ("title", None, "Title", M, 2.9, SLIDE_W_IN - 2 * M, 1.4, "Section"),
        ]),
    ])

    # 2. two slide masters
    write_template(out / "two-masters.pptx", [
        layout_variant("Title Slide", "title", [
            ("ctrTitle", None, "Title", M, 2.6, SLIDE_W_IN - 2 * M, 1.3, "Title"),
            ("subTitle", "1", "Subtitle", M, 4.0, SLIDE_W_IN - 2 * M, 1.0, "Subtitle"),
        ]),
        layout_variant("Body", "obj", [TITLE_PH, BODY_PH]),
        layout_variant("Picture", "picTx", [
            ("title", None, "Title", M, M, SLIDE_W_IN - 2 * M, 0.7, "Title"),
            ("pic", "1", "Picture Placeholder", M, M + 0.9, SLIDE_W_IN - 2 * M, 4.7, "Picture"),
            ("body", "2", "Caption", M, SLIDE_H_IN - M - 0.6, SLIDE_W_IN - 2 * M, 0.6, "Caption"),
        ]),
        layout_variant("Body Dark", "obj", [TITLE_PH, BODY_PH]),
    ], n_masters=2)

    # 3. ships example slides that must be dropped
    write_template(out / "with-examples.pptx", [
        layout_variant("Title Slide", "title", [
            ("ctrTitle", None, "Title", M, 2.6, SLIDE_W_IN - 2 * M, 1.3, "Title"),
            ("subTitle", "1", "Subtitle", M, 4.0, SLIDE_W_IN - 2 * M, 1.0, "Subtitle"),
        ]),
        layout_variant("Body", "obj", [TITLE_PH, BODY_PH]),
        layout_variant("Picture", "picTx", [
            ("title", None, "Title", M, M, SLIDE_W_IN - 2 * M, 0.7, "Title"),
            ("pic", "1", "Picture Placeholder", M, M + 0.9, SLIDE_W_IN - 2 * M, 4.7, "Picture"),
        ]),
    ], n_example_slides=3)

    # 4. odd idx numbering + non-English names
    write_template(out / "odd-idx.pptx", [
        layout_variant("Titelfolie", "title", [
            ("ctrTitle", None, "Titel", M, 2.6, SLIDE_W_IN - 2 * M, 1.3, "Titel"),
            ("subTitle", "7", "Untertitel", M, 4.0, SLIDE_W_IN - 2 * M, 1.0, "Untertitel"),
        ]),
        layout_variant("Inhalt", "obj", [
            ("title", None, "Titel", M, M, SLIDE_W_IN - 2 * M, TITLE_H, "Titel"),
            ("body", "12", "Inhaltsplatzhalter", M, M + TITLE_H + 0.2, SLIDE_W_IN - 2 * M,
             SLIDE_H_IN - M - TITLE_H - 0.2 - M, "Text"),
        ]),
        layout_variant("Bild mit Untertitel", "picTx", [
            ("title", None, "Titel", M, M, SLIDE_W_IN - 2 * M, 0.7, "Titel"),
            ("pic", "9", "Bildplatzhalter", M, M + 0.9, SLIDE_W_IN - 2 * M, 4.7, "Bild"),
            ("body", "14", "Bildunterschrift", M, SLIDE_H_IN - M - 0.6, SLIDE_W_IN - 2 * M, 0.6, "Untertitel"),
        ]),
    ])

    # 5. exactly one usable layout — everything must degrade onto it
    write_template(out / "minimal.pptx", [
        layout_variant("Standard", "obj", [TITLE_PH, BODY_PH]),
    ])

    for f in sorted(out.glob("*.pptx")):
        print(f"built {f} ({f.stat().st_size} bytes)")


if __name__ == "__main__":
    sys.exit(main())
