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
  5. Every script under skills/training-material-generator/scripts/ and lib/ answers
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
