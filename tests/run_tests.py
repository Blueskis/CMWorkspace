#!/usr/bin/env python3
"""Unit tests for training-material-generator, run against the fixtures in fixtures/.

    python tests/run_tests.py [-v]

Covers the "Verification" section of the v0.2 plan:

  1. extract_assets.py on a synthetic .docx: drops noise (a 3x-repeated logo), keeps
     real screenshots with correct captions/section_id/document order, and its
     section_ids agree with map_source.py's for the same document (both use
     lib/section_walk.py's shared heading-stack walker).
  2. map_source.py across all three input formats (.docx, .pptx, a .pdf/.txt sidecar).
  3. qa_training.py's audit() catches an uncovered procedure section, a missing-question
     objective, and a provenance failure — and passes a clean plan.
  4. render_diagram.py renders all five diagram types to well-formed, hex-free,
     inherited-font XML, and DiagramOverflowError actually fires on a label that can't
     fit; a rendered fragment round-trips through inject_slide_xml.py's diagram import
     without id collisions.
  5. render_annotation.py renders all five annotation types the same way (well-formed,
     hex-free, inherited-font XML; a step number is a real editable text run); its fitted
     rect matches inject_slide_xml.fit_extent() exactly; out-of-bounds coordinates and an
     unknown type raise; and a picture + annotation overlay round-trip through
     inject_slide_xml.py with the picture ahead of the overlay in document order (z-order).
  6. png_ops.py's PNG codec round-trips a genuinely Paeth-filtered image byte-identically;
     redact destroys pixels inside its rect and nowhere else; crop+upscale produces exact
     dimensions and a matching corner pixel; interlaced and 16-bit PNG are refused.
  7. qa_training.py's check 6 catches a callout step numbering that isn't exactly {1..N}
     against its slide's bullets, an out-of-bounds annotation coordinate, and a `redact`
     annotation whose asset has no redacted_from — and reports (without hard-failing) an
     over-dense screenshot.
  8. Every script under skills/training-material-generator/scripts/ and lib/ answers
     --help with exit 0, and imports nothing outside the stdlib except
     inject_slide_xml.py (defusedxml).

Stdlib only (unittest + subprocess + ast). Run standalone; no pytest required.
"""

import ast
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.dom.minidom import parseString

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "skills" / "training-material-generator" / "scripts"
LIB_DIR = ROOT / "lib"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))


def run(*args, check=True):
    result = subprocess.run(
        [sys.executable, *[str(a) for a in args]],
        capture_output=True, text=True,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {args}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


class DocxExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.docx = self.tmp / "sample-fsd.docx"
        run(FIXTURES / "make_docx_fixture.py", "-o", self.docx)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_extract_assets_drops_noise_keeps_real_screenshots(self):
        assets_dir = self.tmp / "assets"
        idx_path = self.tmp / "asset_index.json"
        run(SCRIPTS_DIR / "extract_assets.py", self.docx, "--assets", assets_dir,
            "-o", idx_path, "--run-id", "t")

        index = json.loads(idx_path.read_text())
        assets = index["assets"]
        self.assertEqual(len(assets), 2, f"expected 2 surviving assets, got {[a['asset_id'] for a in assets]}")

        by_id = {a["asset_id"]: a for a in assets}
        screenshot = next(a for a in assets if a["width_px"] == 800)
        self.assertEqual(screenshot["height_px"], 600)
        self.assertEqual(screenshot["role"], "screenshot")
        self.assertEqual(screenshot["quality"], [])
        self.assertEqual(screenshot["caption_candidate"], "Figure 1: The approval screen.")
        self.assertEqual(screenshot["repeat_count"], 1)

        low_res = next(a for a in assets if a["width_px"] == 200)
        self.assertEqual(low_res["height_px"], 150)
        self.assertIn("low_res", low_res["quality"])

        # doc_order_index: the 800x600 screenshot appears before the 200x150 one
        self.assertLess(screenshot["doc_order_index"], low_res["doc_order_index"])

        # the 3x-repeated 300x300 "logo" must be dropped entirely
        self.assertFalse(any(a["width_px"] == 300 for a in assets))

    def test_section_ids_agree_between_map_source_and_extract_assets(self):
        source_map_path = self.tmp / "source_map.json"
        assets_dir = self.tmp / "assets"
        idx_path = self.tmp / "asset_index.json"
        run(SCRIPTS_DIR / "map_source.py", self.docx, "-o", source_map_path, "--run-id", "t")
        run(SCRIPTS_DIR / "extract_assets.py", self.docx, "--assets", assets_dir,
            "-o", idx_path, "--run-id", "t")

        section_ids = {s["section_id"] for s in json.loads(source_map_path.read_text())["sections"]}
        asset_section_ids = {a["section_id"] for a in json.loads(idx_path.read_text())["assets"]}
        self.assertTrue(asset_section_ids)
        self.assertTrue(asset_section_ids <= section_ids,
                         f"asset section_ids not found in source_map: {asset_section_ids - section_ids}")

    def test_map_source_finds_expected_sections_and_procedure_classifier(self):
        out = self.tmp / "source_map.json"
        run(SCRIPTS_DIR / "map_source.py", self.docx, "-o", out, "--run-id", "t")
        sections = {s["section_id"]: s for s in json.loads(out.read_text())["sections"]}
        self.assertIn("sample-fsd#4.2.1", sections)
        self.assertEqual(sections["sample-fsd#4.2.1"]["classifier"], "procedure")
        self.assertIn("Step 1", sections["sample-fsd#4.2.1"]["text"])
        self.assertEqual(sections["sample-fsd#4.2.2"]["table_count"], 1)


class PptxSourceExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pptx = self.tmp / "sample-source.pptx"
        run(FIXTURES / "make_pptx_fixture.py", "-o", self.pptx)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_map_source_one_section_per_slide(self):
        out = self.tmp / "source_map.json"
        run(SCRIPTS_DIR / "map_source.py", self.pptx, "-o", out, "--run-id", "t")
        sections = json.loads(out.read_text())["sections"]
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["title"], "Welcome")
        self.assertEqual(sections[1]["section_id"], "sample-source#slide2")

    def test_extract_assets_resolves_slide_relationship(self):
        assets_dir = self.tmp / "assets"
        idx_path = self.tmp / "asset_index.json"
        run(SCRIPTS_DIR / "extract_assets.py", self.pptx, "--assets", assets_dir,
            "-o", idx_path, "--run-id", "t")
        assets = json.loads(idx_path.read_text())["assets"]
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["width_px"], 640)
        self.assertEqual(assets[0]["section_id"], "sample-source#slide2")
        self.assertEqual(assets[0]["alt_text"], "Approval dialog")


class PdfSidecarTests(unittest.TestCase):
    def test_map_source_reads_sidecar_text_and_infers_clause_headings(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            out = tmp / "source_map.json"
            run(SCRIPTS_DIR / "map_source.py", FIXTURES / "pdf_sidecar" / "sample.pdf",
                "-o", out, "--run-id", "t")
            sections = {s["section_id"]: s for s in json.loads(out.read_text())["sections"]}
            self.assertIn("sample#5.1.11", sections)
            self.assertIn("sample#5.1.12", sections)
            self.assertIn("Singapore", sections["sample#5.1.11"]["text"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class QaTrainingAuditTests(unittest.TestCase):
    """Imports qa_training directly (audit() has no side effects) rather than shelling out,
    since these tests construct many small plan variants in-memory."""

    @classmethod
    def setUpClass(cls):
        import qa_training  # noqa: PLC0415 (deliberately deferred: needs sys.path set above)
        cls.qa_training = qa_training
        cls.brief = json.loads((FIXTURES / "qa" / "training_brief.json").read_text())
        cls.plan = json.loads((FIXTURES / "qa" / "deck_plan_pass.json").read_text())
        cls.questions = json.loads((FIXTURES / "qa" / "question_bank_pass.json").read_text())
        cls.source_map_dir = None

    def setUp(self):
        # Build a fresh source_map/asset_index pair from the docx fixture so section_ids
        # line up with the qa/ fixtures' hardcoded "sample-fsd#..." references.
        self.tmp = Path(tempfile.mkdtemp())
        docx = self.tmp / "sample-fsd.docx"
        run(FIXTURES / "make_docx_fixture.py", "-o", docx)
        sm_path = self.tmp / "source_map.json"
        ai_path = self.tmp / "asset_index.json"
        run(SCRIPTS_DIR / "map_source.py", docx, "-o", sm_path, "--run-id", "t")
        run(SCRIPTS_DIR / "extract_assets.py", docx, "--assets", self.tmp / "assets",
            "-o", ai_path, "--run-id", "t")
        self.source_map = json.loads(sm_path.read_text())
        self.asset_index = json.loads(ai_path.read_text())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_plan_passes(self):
        result = self.qa_training.audit(self.brief, self.plan, self.source_map, self.asset_index, self.questions)
        self.assertEqual(result["lo_no_slide"], [])
        self.assertEqual(result["lo_no_question"], [])
        self.assertEqual(result["missing_provenance"], [])
        self.assertEqual(result["uncovered_procedures"], [])
        self.assertEqual(result["unplaced_screenshots"], [])

    def test_missing_question_for_objective_is_caught(self):
        questions = {"run_id": "t", "questions": [q for q in self.questions["questions"] if q["objective_id"] != "LO2"]}
        result = self.qa_training.audit(self.brief, self.plan, self.source_map, self.asset_index, questions)
        self.assertIn("LO2", result["lo_no_question"])

    def test_block_without_sources_or_gap_is_caught(self):
        import copy
        plan = copy.deepcopy(self.plan)
        plan["modules"][1]["slides"][0]["blocks"][0]["sources"] = []
        result = self.qa_training.audit(self.brief, plan, self.source_map, self.asset_index, self.questions)
        self.assertTrue(result["missing_provenance"])

    def test_uncovered_procedure_section_is_caught(self):
        import copy
        plan = copy.deepcopy(self.plan)
        for slide in plan["modules"][0]["slides"]:
            for block in slide["blocks"]:
                block["sources"] = ["sample-fsd#4"]  # re-point away from the procedure section
        result = self.qa_training.audit(self.brief, plan, self.source_map, self.asset_index, self.questions)
        self.assertIn("sample-fsd#4.2.1", result["uncovered_procedures"])

    def test_out_of_scope_entry_clears_the_uncovered_procedure(self):
        import copy
        plan = copy.deepcopy(self.plan)
        for slide in plan["modules"][0]["slides"]:
            for block in slide["blocks"]:
                block["sources"] = ["sample-fsd#4"]
        brief = copy.deepcopy(self.brief)
        brief["out_of_scope"] = [{"section_id": "sample-fsd#4.2.1", "reason": "covered in a separate session"}]
        result = self.qa_training.audit(brief, plan, self.source_map, self.asset_index, self.questions)
        self.assertNotIn("sample-fsd#4.2.1", result["uncovered_procedures"])


class DiagramRenderTests(unittest.TestCase):
    SPECS = {
        "process": {"steps": ["Create PO", "Submit", "Approve", "Post"]},
        "swimlane": {
            "roles": ["Requester", "Approver"],
            "steps": [{"step": "Create PO", "role": "Requester"}, {"step": "Review", "role": "Approver"}],
        },
        "decision": {"rules": [
            {"condition": "Amount <= $1,000", "outcome": "Auto-approved"},
            {"condition": "Amount > $1,000", "outcome": "Manager approval"},
        ]},
        "hierarchy": {"root": {"name": "Director", "children": [{"name": "Manager A"}, {"name": "Manager B"}]}},
        "timeline": {"milestones": [{"label": "Kickoff", "date": "Jan 2026"}, {"label": "Go-live", "date": "Mar 2026"}]},
    }

    def test_all_five_types_render_well_formed_hex_free_xml(self):
        import render_diagram
        for diagram_type, spec in self.SPECS.items():
            with self.subTest(diagram_type=diagram_type):
                ooxml, svg = render_diagram.render(diagram_type, spec, (0.5, 1.5, 9.0, 5.0))
                parseString(ooxml)  # raises on malformed XML
                self.assertNotRegex(ooxml, r"srgbClr|#[0-9a-fA-F]{6}", "diagram must use schemeClr, never hex")
                self.assertNotIn("a:latin", ooxml, "diagram must never set an explicit typeface")
                self.assertIn("<svg", svg)

    def test_overflow_raises_diagram_overflow_error(self):
        import render_diagram
        spec = {"steps": ["A label so long it will never fit in a box this small no matter the font size chosen"]}
        with self.assertRaises(render_diagram.DiagramOverflowError):
            render_diagram.render("process", spec, (0.5, 1.5, 1.0, 0.3))

    def test_bad_spec_raises_diagram_spec_error(self):
        import render_diagram
        with self.assertRaises(render_diagram.DiagramSpecError):
            render_diagram.render("process", {"steps": []}, (0.5, 1.5, 9.0, 5.0))

    def test_diagram_fragment_round_trips_through_inject_slide_xml(self):
        import inject_slide_xml
        import render_diagram

        tmp = Path(tempfile.mkdtemp())
        try:
            ooxml, _ = render_diagram.render("process", self.SPECS["process"], (0.5, 1.5, 9.0, 5.0))
            frag_path = tmp / "diagram.xml"
            frag_path.write_text(ooxml, encoding="utf-8")

            unpacked = tmp / "unpacked"
            (unpacked / "ppt" / "slides").mkdir(parents=True)
            (unpacked / "[Content_Types].xml").write_text(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/></Types>',
                encoding="utf-8",
            )
            slide_path = unpacked / "ppt" / "slides" / "slide1.xml"
            slide_path.write_text(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<p:cSld><p:spTree>'
                '<p:sp><p:nvSpPr><p:cNvPr id="1" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
                '<p:spPr/><p:txBody/></p:sp>'
                '</p:spTree></p:cSld></p:sld>',
                encoding="utf-8",
            )

            inject_slide_xml.insert_diagram(unpacked, "ppt/slides/slide1.xml", frag_path)

            from xml.dom.minidom import parse
            dom = parse(str(slide_path))
            ids = [el.getAttribute("id") for el in dom.getElementsByTagName("p:cNvPr")]
            self.assertEqual(len(ids), len(set(ids)), "shape ids must not collide after injection")
            self.assertIn("1", ids)  # the original title shape survives untouched
            self.assertEqual(len(dom.getElementsByTagName("p:grpSp")), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class AnnotationRenderTests(unittest.TestCase):
    """render_annotation.py — mirrors DiagramRenderTests: well-formed, hex-free,
    inherited-font XML; the coordinate transform against fit_extent(); and the same
    fail-loudly discipline for out-of-bounds or unfittable annotations."""

    ANNOTATIONS = [
        {"type": "highlight", "rect": [0.41, 0.22, 0.28, 0.06], "step": 1, "label": "Approve button"},
        {"type": "callout", "point": [0.55, 0.25], "step": 1},
        {"type": "arrow", "from": [0.70, 0.40], "to": [0.56, 0.26], "step": 2},
        {"type": "redact", "rect": [0.05, 0.05, 0.22, 0.04], "reason": "vendor name"},
        {"type": "zoom", "rect": [0.40, 0.20, 0.10, 0.08], "scale": 3, "place": "right", "step": 3},
    ]

    @classmethod
    def setUpClass(cls):
        import png_ops
        import render_annotation
        cls.render_annotation = render_annotation
        cls.tmp = Path(tempfile.mkdtemp())
        # 400x300 (4:3) synthetic PNG, real Paeth-filtered rows, via the shared fixture module.
        w, h, bpp = 400, 300, 3
        rows = [bytes(b for x in range(w) for b in ((x) % 256, (y) % 256, 128)) for y in range(h)]
        cls.image_path = cls.tmp / "screenshot.png"
        cls.image_path.write_bytes(png_ops.encode_png(w, h, bpp, rows))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_all_types_render_well_formed_hex_free_xml(self):
        ooxml, svg, fitted = self.render_annotation.render(
            self.ANNOTATIONS, self.image_path, (0.6, 1.8, 8.5, 4.5), id_start=200,
        )
        parseString(ooxml)  # raises on malformed XML
        self.assertNotRegex(ooxml, r"srgbClr|#[0-9a-fA-F]{6}", "annotation must use schemeClr, never hex")
        self.assertNotIn("a:latin", ooxml, "annotation must never set an explicit typeface")
        self.assertIn("<svg", svg)

    def test_fitted_rect_matches_fit_extent(self):
        import inject_slide_xml
        bbox = (0.6, 1.8, 8.5, 4.5)
        expected = inject_slide_xml.fit_extent(bbox, 400, 300)
        _, _, fitted = self.render_annotation.render(self.ANNOTATIONS, self.image_path, bbox, id_start=200)
        self.assertEqual(fitted, expected, "render_annotation must reuse inject_slide_xml's own fit_extent")

    def test_callout_number_is_a_real_editable_text_run(self):
        ooxml, _, _ = self.render_annotation.render(
            [{"type": "callout", "point": [0.5, 0.5], "step": 7}], self.image_path, (0.6, 1.8, 8.5, 4.5),
        )
        self.assertIn("<a:t>7</a:t>", ooxml, "the step number must be a genuine text run, not a rasterized digit")

    def test_out_of_bounds_point_raises_annotation_spec_error(self):
        with self.assertRaises(self.render_annotation.AnnotationSpecError):
            self.render_annotation.render(
                [{"type": "callout", "point": [1.5, 0.2], "step": 1}], self.image_path, (0.6, 1.8, 8.5, 4.5),
            )

    def test_rect_extending_past_image_edge_raises(self):
        with self.assertRaises(self.render_annotation.AnnotationSpecError):
            self.render_annotation.render(
                [{"type": "highlight", "rect": [0.9, 0.9, 0.5, 0.5], "step": 1}], self.image_path, (0.6, 1.8, 8.5, 4.5),
            )

    def test_unknown_annotation_type_raises(self):
        with self.assertRaises(self.render_annotation.AnnotationSpecError):
            self.render_annotation.render(
                [{"type": "bogus", "point": [0.1, 0.1]}], self.image_path, (0.6, 1.8, 8.5, 4.5),
            )

    def test_annotation_fragment_round_trips_after_picture_with_correct_z_order(self):
        import inject_slide_xml

        tmp = Path(tempfile.mkdtemp())
        try:
            unpacked = tmp / "unpacked"
            (unpacked / "ppt" / "slides").mkdir(parents=True)
            (unpacked / "[Content_Types].xml").write_text(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/></Types>',
                encoding="utf-8",
            )
            slide_path = unpacked / "ppt" / "slides" / "slide1.xml"
            slide_path.write_text(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<p:cSld><p:spTree>'
                '<p:sp><p:nvSpPr><p:cNvPr id="1" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
                '<p:spPr/><p:txBody/></p:sp>'
                '</p:spTree></p:cSld></p:sld>',
                encoding="utf-8",
            )

            bbox = (0.6, 1.8, 8.5, 4.5)
            inject_slide_xml.insert_picture(unpacked, "ppt/slides/slide1.xml", self.image_path, bbox)
            ooxml, _, _ = self.render_annotation.render(self.ANNOTATIONS, self.image_path, bbox, id_start=200)
            frag_path = tmp / "ann.xml"
            frag_path.write_text(ooxml, encoding="utf-8")
            inject_slide_xml.insert_diagram(unpacked, "ppt/slides/slide1.xml", frag_path)

            from xml.dom.minidom import parse
            dom = parse(str(slide_path))
            ids = [el.getAttribute("id") for el in dom.getElementsByTagName("p:cNvPr")]
            self.assertEqual(len(ids), len(set(ids)), "shape ids must not collide after injection")

            sptree = dom.getElementsByTagName("p:spTree")[0]
            child_tags = [c.tagName for c in sptree.childNodes if c.nodeType == 1]
            self.assertLess(
                child_tags.index("p:pic"), child_tags.index("p:grpSp"),
                "the picture must precede the annotation overlay in document order (z-order)",
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class PngOpsTests(unittest.TestCase):
    """png_ops.py — stdlib-only PNG codec plus redact/crop, verified against a genuinely
    Paeth-filtered fixture (not just filter-0) so the defiltering branches are exercised."""

    @classmethod
    def setUpClass(cls):
        import png_ops
        cls.png_ops = png_ops
        w, h, bpp = 64, 40, 3
        cls.W, cls.H, cls.BPP = w, h, bpp
        cls.rows = [bytes(b for x in range(w) for b in ((x * 4) % 256, (y * 6) % 256, 128)) for y in range(h)]

    def _encode_paeth(self, rows, w, bpp):
        prev = bytes(w * bpp)
        parts = []
        for r in rows:
            enc = bytearray(len(r))
            for x in range(len(r)):
                a = r[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                enc[x] = (r[x] - pr) & 0xFF
            parts.append(bytes([4]) + bytes(enc))
            prev = r
        import struct
        import zlib
        color_type = 2 if bpp == 3 else 6
        ihdr = struct.pack(">IIBBBBB", w, len(rows), 8, color_type, 0, 0, 0)

        def chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        idat = zlib.compress(b"".join(parts), 9)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))

    def test_decode_of_real_paeth_filtered_png_round_trips(self):
        paeth_png = self._encode_paeth(self.rows, self.W, self.BPP)
        w, h, bpp, dec = self.png_ops.decode_png(paeth_png)
        self.assertEqual((w, h, bpp), (self.W, self.H, self.BPP))
        self.assertEqual(dec, self.rows)

    def test_redact_destroys_pixels_inside_rect_only(self):
        src = self.png_ops.encode_png(self.W, self.H, self.BPP, self.rows)
        out = self.png_ops.redact(src, (10 / self.W, 8 / self.H, 30 / self.W, 12 / self.H))
        _, _, _, out_rows = self.png_ops.decode_png(out)
        self.assertNotEqual(out_rows[10][20 * 3:20 * 3 + 3], self.rows[10][20 * 3:20 * 3 + 3], "pixel inside the rect must change")
        self.assertEqual(out_rows[35], self.rows[35], "a row outside the rect must be untouched")

    def test_crop_scale_dimensions_and_corner_pixel(self):
        src = self.png_ops.encode_png(self.W, self.H, self.BPP, self.rows)
        out = self.png_ops.crop_scale(src, (8 / self.W, 6 / self.H, 16 / self.W, 12 / self.H), 3)
        w, h, bpp, out_rows = self.png_ops.decode_png(out)
        self.assertEqual((w, h), (48, 36))
        self.assertEqual(out_rows[0][:3], self.rows[6][8 * 3:8 * 3 + 3])

    def test_rejects_interlaced_png(self):
        import struct
        import zlib
        ihdr = struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 1)  # interlace=1

        def chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        bogus = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00" * 100)) + chunk(b"IEND", b"")
        with self.assertRaises(self.png_ops.PngOpsError):
            self.png_ops.decode_png(bogus)

    def test_rejects_16bit_png(self):
        import struct
        import zlib
        ihdr = struct.pack(">IIBBBBB", 4, 4, 16, 2, 0, 0, 0)

        def chunk(t, d):
            c = t + d
            return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        bogus = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00" * 100)) + chunk(b"IEND", b"")
        with self.assertRaises(self.png_ops.PngOpsError):
            self.png_ops.decode_png(bogus)


class QaAnnotationTests(unittest.TestCase):
    """qa_training.py check 6 — in-memory plan variants, same style as
    QaTrainingAuditTests but self-contained (no docx fixture needed: annotation binding
    only reads deck_plan.json's own blocks)."""

    @classmethod
    def setUpClass(cls):
        import qa_training
        cls.qa_training = qa_training

    @staticmethod
    def _plan(annotations, n_bullets=3, asset_id="fsd-img-014"):
        return {
            "run_id": "t",
            "modules": [{
                "module_id": "m1", "objective_ids": ["LO1"],
                "slides": [{
                    "slide_id": "s1",
                    "blocks": [
                        {"placeholder": "Bullets", "kind": "bullets",
                         "content": [f"Step {i+1}" for i in range(n_bullets)], "sources": ["s1"]},
                        {"placeholder": "Picture", "kind": "image",
                         "content": {"asset_id": asset_id, "annotations": annotations}, "sources": ["s1"]},
                    ],
                }],
            }],
        }

    def _audit(self, plan, asset_index=None):
        brief = {"learning_objectives": [{"lo_id": "LO1", "text": "x"}]}
        source_map = {"sections": []}
        asset_index = asset_index or {"assets": [
            {"asset_id": "fsd-img-014", "role": "screenshot"},
            {"asset_id": "fsd-img-014-r1", "role": "screenshot", "redacted_from": "fsd-img-014"},
        ]}
        return self.qa_training.audit(brief, plan, source_map, asset_index, None)

    def test_clean_callout_binding_passes(self):
        plan = self._plan([{"type": "callout", "point": [0.5, 0.1 * s], "step": s} for s in (1, 2, 3)])
        result = self._audit(plan)
        self.assertEqual(result["annotation_binding_errors"], [])

    def test_gap_in_step_numbers_is_caught(self):
        plan = self._plan([{"type": "callout", "point": [0.5, 0.1], "step": s} for s in (1, 3)])
        result = self._audit(plan)
        self.assertTrue(result["annotation_binding_errors"])

    def test_step_above_bullet_count_is_caught(self):
        plan = self._plan([{"type": "callout", "point": [0.5, 0.1 * s], "step": s} for s in (1, 2, 4)])
        result = self._audit(plan)
        self.assertTrue(result["annotation_binding_errors"])

    def test_redact_without_redacted_from_is_hard_caught(self):
        plan = self._plan([{"type": "redact", "rect": [0.1, 0.1, 0.1, 0.1], "reason": "x"}], n_bullets=1)
        result = self._audit(plan)
        self.assertTrue(result["annotation_redact_unflattened"])

    def test_redact_with_redacted_from_passes(self):
        plan = self._plan(
            [{"type": "redact", "rect": [0.1, 0.1, 0.1, 0.1], "reason": "x"}],
            n_bullets=1, asset_id="fsd-img-014-r1",
        )
        result = self._audit(plan)
        self.assertEqual(result["annotation_redact_unflattened"], [])

    def test_out_of_bounds_coordinate_is_caught(self):
        plan = self._plan([{"type": "callout", "point": [1.9, 0.2], "step": 1}], n_bullets=1)
        result = self._audit(plan)
        self.assertTrue(result["annotation_geometry_errors"])

    def test_dense_annotations_reported_but_not_hard_fail(self):
        plan = self._plan([{"type": "highlight", "rect": [0.01 * i, 0.01, 0.02, 0.02]} for i in range(8)], n_bullets=1)
        result = self._audit(plan)
        self.assertTrue(result["annotation_density_report"])
        self.assertEqual(result["annotation_binding_errors"], [])
        self.assertEqual(result["annotation_geometry_errors"], [])


class ScriptHygieneTests(unittest.TestCase):
    """--help works, and every script stays inside the documented dependency boundary:
    stdlib only, except inject_slide_xml.py's defusedxml (with its own graceful fallback)."""

    ALLOWED_NONSTDLIB = {
        "inject_slide_xml.py": {"defusedxml"},
    }

    def _all_scripts(self):
        return sorted(SCRIPTS_DIR.glob("*.py")) + sorted(LIB_DIR.glob("*.py"))

    def test_every_script_answers_help(self):
        for script in self._all_scripts():
            with self.subTest(script=script.name):
                result = run(script, "--help", check=False)
                self.assertEqual(result.returncode, 0, f"{script.name} --help exited {result.returncode}: {result.stderr}")

    def test_no_nonstdlib_imports_outside_the_documented_exception(self):
        stdlib = set(sys.stdlib_module_names) | {"__future__"}
        local_modules = {p.stem for p in self._all_scripts()}
        for script in self._all_scripts():
            with self.subTest(script=script.name):
                tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
                allowed_extra = self.ALLOWED_NONSTDLIB.get(script.name, set())
                for node in ast.walk(tree):
                    names = []
                    if isinstance(node, ast.Import):
                        names = [n.name.split(".")[0] for n in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.level == 0:
                        names = [node.module.split(".")[0]] if node.module else []
                    for name in names:
                        if name in stdlib or name in local_modules:
                            continue
                        self.assertIn(
                            name, allowed_extra,
                            f"{script.name} imports non-stdlib module '{name}' outside the documented exception",
                        )


if __name__ == "__main__":
    unittest.main()
