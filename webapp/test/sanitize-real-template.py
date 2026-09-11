#!/usr/bin/env python3
"""
One-off, test-only utility: turn a real uploaded .pptx template into a structural-only
fixture safe to commit as a regression test.

The uploaded template (a genuine client training-deck shell) carries real employee names
and corporate email addresses in ppt/authors.xml, an active Microsoft Purview sensitivity
label in docMetadata/LabelInfo.xml and docProps/custom.xml (including a literal
"Confidential" classification property), and the document's real title/creator in
docProps/core.xml — none of which either pipeline reads, and none of which belongs in
version control.

Rather than hunt down and redact each sensitive field, this rebuilds a minimal package
containing only the parts either profiler actually reads: slide masters, slide layouts,
and the theme. Within the master and each layout, only placeholder shapes (`<p:sp>` with
a `<p:ph>` child) are kept — decorative shapes are dropped entirely, which incidentally
also removes a "think-cell data - do not delete" hidden picture/OLE-object pair present on
several layouts and the master (a PowerPoint add-in artifact, not client content, but
dropped anyway since it is not a placeholder and profile_template.py/profile-template.js
never read non-placeholder shapes to begin with — this changes nothing they observe).
Every other part class (customXml, docMetadata, docProps/custom.xml, ppt/authors.xml,
ppt/tags, notesMasters, notesSlides, the 14 example slides, and three of four decorative
background images) is left out of the rebuilt package rather than redacted, so there is
nothing to have missed.

Usage: python3 sanitize-real-template.py <input.pptx> <output.pptx>
"""
import io
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
for prefix, uri in NS.items():
    # ct and rel each want the unprefixed default ("" -> <Types>/<Relationships>, not
    # <ns0:Types>) but ElementTree's registry only lets ONE uri own "" at a time — the
    # module-scope loop below settles on rel (it's serialized far more often, once per
    # part); ct's Content_Types.xml is instead built via its own dedicated helper
    # (to_bytes_ct) that re-registers "" -> ct's uri immediately before that one
    # tostring() call, since the two are never serialized concurrently.
    ET.register_namespace("" if prefix == "rel" else prefix, uri)


def to_bytes_ct(elem):
    ET.register_namespace("", NS["ct"])
    data = ET.tostring(elem, encoding="UTF-8", xml_declaration=True)
    ET.register_namespace("", NS["rel"])
    return data

REL_NS = "{%s}" % NS["rel"]
P_NS = "{%s}" % NS["p"]


def strip_decorative_shapes(xml_bytes):
    """Keep only placeholder <p:sp> shapes inside <p:spTree>; drop pics/graphicFrames/etc.
    Also drop <p:custDataLst> (cites ppt/tags/*.xml, which we don't ship) and <p:extLst>
    (PowerPoint's own section list, citing slide ids we've dropped) at the document root —
    both would otherwise be dangling references once those parts are gone."""
    root = ET.fromstring(xml_bytes)
    spTree = root.find(f"{P_NS}cSld/{P_NS}spTree")
    keep_tags = {f"{P_NS}nvGrpSpPr", f"{P_NS}grpSpPr"}
    for child in list(spTree):
        if child.tag in keep_tags:
            continue
        if child.tag == f"{P_NS}sp" and child.find(f"{P_NS}nvSpPr/{P_NS}nvPr/{P_NS}ph") is not None:
            continue  # a real placeholder shape — keep it
        spTree.remove(child)
    for tag in (f"{P_NS}custDataLst", f"{P_NS}extLst"):
        el = root.find(tag)
        if el is not None:
            root.remove(el)
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def rels_for(zf, part_name):
    rels_path = part_name.rsplit("/", 1)
    rels_path = f"{rels_path[0]}/_rels/{rels_path[1]}.rels" if len(rels_path) == 2 else f"_rels/{rels_path[0]}.rels"
    try:
        return ET.fromstring(zf.read(rels_path)), rels_path
    except KeyError:
        return None, rels_path


def filter_rels(rels_root, keep_types):
    """keep_types matches the relationship type URI's TRAILING segment exactly — e.g.
    "officeDocument" for .../relationships/officeDocument. A substring match would be
    wrong here: most relationship type URIs share the "officeDocument/2006/relationships/"
    prefix regardless of what they point to, so "officeDocument" as a substring check
    would also match .../relationships/custom-properties and let a relationship straight
    to the confidentiality-classified docProps/custom.xml survive."""
    if rels_root is None:
        return None
    for rel in list(rels_root):
        trailing = rel.get("Type", "").rstrip("/").rsplit("/", 1)[-1]
        if trailing not in keep_types:
            rels_root.remove(rel)
    return rels_root


def tiny_placeholder_png():
    # A 2x2 opaque mid-grey PNG — smallest reasonable stand-in for the original's
    # multi-megabyte decorative background photos, whose content was never inspected for
    # client identifiability and is irrelevant to what these tests actually check.
    import struct
    import zlib

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
    raw = b"\x00" + b"\x80\x80\x80" * 2
    raw *= 2
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def main():
    src_path, out_path = sys.argv[1], sys.argv[2]
    zin = zipfile.ZipFile(src_path)

    keep_parts = [
        "ppt/presentation.xml",
        "ppt/theme/theme1.xml",
        "ppt/presProps.xml",
        "ppt/viewProps.xml",
        "ppt/tableStyles.xml",
        "ppt/slideMasters/slideMaster1.xml",
    ] + [f"ppt/slideLayouts/slideLayout{i}.xml" for i in range(1, 6)]

    out = {}

    # --- presentation.xml: drop the slide list and notes-master reference ---
    pres = ET.fromstring(zin.read("ppt/presentation.xml"))
    sldIdLst = pres.find(f"{P_NS}sldIdLst")
    if sldIdLst is not None:
        pres.remove(sldIdLst)
    notesMasterIdLst = pres.find(f"{P_NS}notesMasterIdLst")
    if notesMasterIdLst is not None:
        pres.remove(notesMasterIdLst)
    custDataLst = pres.find(f"{P_NS}custDataLst")
    if custDataLst is not None:
        pres.remove(custDataLst)  # referenced ppt/tags/*.xml, which we drop
    extLst = pres.find(f"{P_NS}extLst")
    if extLst is not None:
        pres.remove(extLst)  # PowerPoint section list citing the 14 dropped slide ids
    out["ppt/presentation.xml"] = ET.tostring(pres, encoding="UTF-8", xml_declaration=True)

    # --- presentation.xml.rels: keep only slideMaster/theme/presProps/viewProps/tableStyles ---
    pres_rels, pres_rels_path = rels_for(zin, "ppt/presentation.xml")
    filter_rels(pres_rels, ["slideMaster", "theme", "presProps", "viewProps", "tableStyles"])
    out[pres_rels_path] = ET.tostring(pres_rels, encoding="UTF-8", xml_declaration=True)

    # --- master + layouts: strip decorative shapes, keep placeholders only ---
    for part in ["ppt/slideMasters/slideMaster1.xml"] + [f"ppt/slideLayouts/slideLayout{i}.xml" for i in range(1, 6)]:
        out[part] = strip_decorative_shapes(zin.read(part))
        rels_root, rels_path = rels_for(zin, part)
        filter_rels(rels_root, ["slideLayout", "theme", "image"])
        # Of the surviving image relationships, only keep ones actually still referenced
        # by a placeholder shape (there are none in practice — decorative pics carried the
        # only image refs — but check rather than assume).
        remaining_xml = out[part].decode("utf-8")
        if rels_root is not None:
            for rel in list(rels_root):
                if "image" in rel.get("Type", "") and rel.get("Id") not in remaining_xml:
                    rels_root.remove(rel)
            out[rels_path] = ET.tostring(rels_root, encoding="UTF-8", xml_declaration=True)

    out["ppt/theme/theme1.xml"] = zin.read("ppt/theme/theme1.xml")
    out["ppt/presProps.xml"] = zin.read("ppt/presProps.xml")
    out["ppt/viewProps.xml"] = zin.read("ppt/viewProps.xml")
    out["ppt/tableStyles.xml"] = zin.read("ppt/tableStyles.xml")

    # --- minimal, generic docProps (no creator/company/title from the original) ---
    out["docProps/core.xml"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        b'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b"<dc:title>Structural test fixture</dc:title></cp:coreProperties>"
    )
    out["docProps/app.xml"] = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        b"<Application>python-sanitize</Application></Properties>"
    )

    # --- [Content_Types].xml: keep only the parts we're actually shipping ---
    ct = ET.fromstring(zin.read("[Content_Types].xml"))
    CT_NS = "{%s}" % NS["ct"]
    keep_override_parts = {f"/{p}" for p in keep_parts} | {
        "/docProps/core.xml", "/docProps/app.xml",
    }
    for override in list(ct):
        if override.tag == f"{CT_NS}Override" and override.get("PartName") not in keep_override_parts:
            ct.remove(override)
    out["[Content_Types].xml"] = to_bytes_ct(ct)

    # --- root _rels/.rels: officeDocument + core/extended properties only ---
    root_rels, root_rels_path = rels_for(zin, "")
    filter_rels(root_rels, ["officeDocument", "core-properties", "extended-properties"])
    out[root_rels_path] = ET.tostring(root_rels, encoding="UTF-8", xml_declaration=True)

    # --- media: only image1.emf (inert think-cell marker, no client content) survives
    #     structurally if still referenced; the three decorative backgrounds are replaced
    #     with a tiny generic placeholder rather than judged individually. Since decorative
    #     pics were dropped above, no layout/master XML references any media part anymore —
    #     confirm that and skip writing ppt/media/* entirely if so.
    referenced_media = any(
        b"media/image" in v or b'Target="../media' in v for k, v in out.items() if k.endswith(".rels")
    )
    if referenced_media:
        out["ppt/media/image1.emf"] = tiny_placeholder_png()  # placeholder if ever needed

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in out.items():
            zf.writestr(name, data)

    print(f"wrote {out_path}: {len(out)} parts, "
          f"{sum(len(v) for v in out.values())} bytes uncompressed")
    print("referenced_media after stripping decorative shapes:", referenced_media)


if __name__ == "__main__":
    main()
