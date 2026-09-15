#!/usr/bin/env python3
"""Unit tests for render_comms_html.py, the local:render_comms_html producer for banner,
newsletter and edm (schemas/channel_registry.json).

    python skills/cm-comms-generator/tests/test_render_comms_html.py [-v]

Fixtures are the real northwind-payroll worked example (examples/northwind-payroll/), copied
into a tmp dir per test so QA-breaking edits never touch the committed files. Covers:

  1. Happy path per channel — banner, newsletter and edm each render, exit 0, and the output
     carries every fixture's real text.
  2. edm's output is actually email-safe: no <style> block, no CSS classes, no var(--), every
     <table> carries role="presentation".
  3. THE GATE: a QA-failing plan (stripped block sources) is refused — exit 1, no file
     written — same behaviour route_channel.py enforces before printing a route.
  4. A channel with no comms-html layout (email) is refused with a clear message, not a
     traceback.
  5. THE ACCESSIBILITY GATE: a brand palette that fails the WCAG floor is refused before any
     file is written, even though QA on the copy itself would pass.
  6. A `gap: true` block renders as a visible [GAP] marker — never silently dropped, never
     filled with invented text.
  7. _inline_font_stack flattens a fallback stack entry that already contains a comma
     (e.g. "system-ui, sans-serif") into separate tokens, instead of quoting the whole
     entry as one malformed family name (the bug fixed during development).
  8. A cta block with a URL embedded in its text becomes a real <a href> button; a cta block
     with no URL falls back to plain emphasised text and warns on stderr — never invents a
     destination.

Stdlib only (unittest + subprocess), matching tests/run_tests.py's convention for the sibling
training-material-generator skill.
"""

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = ROOT / "skills" / "cm-comms-generator" / "scripts"
EXAMPLE_DIR = ROOT / "examples" / "northwind-payroll"
SCRIPT = SCRIPTS_DIR / "render_comms_html.py"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(ROOT / "lib"))


def run(*args, check=False):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True, text=True,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {args}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


class RenderCommsHtmlTests(unittest.TestCase):
    """Copies the real northwind-payroll fixtures into a tmp dir so mutated copies (a
    stripped source, a broken palette) never touch the committed example files."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for name in ("change_brief.json", "brand_profile.json"):
            shutil.copy(EXAMPLE_DIR / name, self.tmp / name)
        for channel in ("banner", "newsletter", "edm", "email"):
            (self.tmp / channel).mkdir()
            shutil.copy(EXAMPLE_DIR / channel / "comms_plan.json", self.tmp / channel / "comms_plan.json")
        self.brief = self.tmp / "change_brief.json"
        self.brand = self.tmp / "brand_profile.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan_path(self, channel):
        return self.tmp / channel / "comms_plan.json"

    def load_plan(self, channel):
        return json.loads(self.plan_path(channel).read_text(encoding="utf-8"))

    def write_plan(self, channel, plan):
        self.plan_path(channel).write_text(json.dumps(plan), encoding="utf-8")

    def render(self, channel, out=None):
        out = out or (self.tmp / channel / f"comms_{channel}.html")
        result = run(self.plan_path(channel), "--brief", self.brief, "--brand", self.brand, "-o", out)
        return result, out

    # --- 1. happy path per channel -------------------------------------------------------

    def test_banner_renders_real_text_and_exits_zero(self):
        result, out = self.render("banner")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(out.exists())
        html = out.read_text(encoding="utf-8")
        self.assertIn("Activate your pay portal by 14 September", html)
        self.assertIn("Pay moves to twice a month from 1 October", html)
        self.assertIn("Activate now", html)

    def test_newsletter_renders_all_sections_with_no_nested_paragraph_bug(self):
        result, out = self.render("newsletter")
        self.assertEqual(result.returncode, 0, result.stderr)
        html = out.read_text(encoding="utf-8")
        self.assertIn("Payday just got more frequent", html)
        self.assertIn("New pay dates from 1 October", html)
        # regression: the intro slot used to double-wrap a "text" block already rendered as
        # <p>...</p>, producing <p><p>...</p></p> — invalid HTML.
        self.assertNotIn("<p><p>", html)

    def test_edm_renders_real_text_and_exits_zero(self):
        result, out = self.render("edm")
        self.assertEqual(result.returncode, 0, result.stderr)
        html = out.read_text(encoding="utf-8")
        self.assertIn("Your pay cadence is changing", html)
        self.assertIn("Activate your account", html)

    # --- 2. edm must be email-safe ------------------------------------------------------

    def test_edm_output_is_email_safe_html(self):
        _, out = self.render("edm")
        html = out.read_text(encoding="utf-8")
        self.assertNotIn("<style", html, "edm must inline every style, not use a <style> block")
        self.assertNotIn(' class="', html, "edm must not rely on CSS classes")
        self.assertNotIn("var(--", html, "edm must not rely on CSS custom properties")
        self.assertNotIn("display:flex", html)
        self.assertNotIn("display:grid", html)
        tables = [line for line in html.splitlines() if "<table" in line]
        self.assertTrue(tables, "expected at least one <table> in edm output")
        for line in tables:
            self.assertIn('role="presentation"', line, f"table missing role=presentation: {line}")

    # --- 3. THE GATE: QA failure blocks rendering ----------------------------------------

    def test_qa_failure_refuses_to_render_and_writes_no_file(self):
        plan = self.load_plan("banner")
        plan["sections"][0]["slides"][0]["blocks"][0]["sources"] = []  # unattributed headline block
        self.write_plan("banner", plan)
        out = self.tmp / "banner" / "should_not_exist.html"
        result, _ = self.render("banner", out=out)
        self.assertEqual(result.returncode, 1)
        self.assertIn("REFUSED", result.stderr)
        self.assertIn("QA has", result.stderr)
        self.assertFalse(out.exists(), "no file should be written when QA fails")

    # --- 4. wrong channel is refused, not a traceback ------------------------------------

    def test_channel_with_no_html_layout_is_refused(self):
        out = self.tmp / "email" / "should_not_exist.html"
        result, _ = self.render("email", out=out)
        self.assertEqual(result.returncode, 1)
        self.assertIn("REFUSED", result.stderr)
        self.assertIn("no comms-html route", result.stderr)
        self.assertFalse(out.exists())

    # --- 5. THE ACCESSIBILITY GATE --------------------------------------------------------

    def test_low_contrast_palette_is_refused_even_when_qa_passes(self):
        brand = json.loads(self.brand.read_text(encoding="utf-8"))
        # near-white on white: fails the 4.5:1 floor while leaving the copy itself untouched.
        brand["palette"]["ink_soft"]["hex"] = "#f0f0f0"
        self.brand.write_text(json.dumps(brand), encoding="utf-8")
        out = self.tmp / "banner" / "should_not_exist.html"
        result, _ = self.render("banner", out=out)
        self.assertEqual(result.returncode, 1)
        self.assertIn("REFUSED", result.stderr)
        self.assertIn("accessibility floor", result.stderr)
        self.assertFalse(out.exists())

    # --- 6. a gap renders visibly, never invented or dropped -----------------------------

    def test_gap_block_renders_visibly(self):
        plan = self.load_plan("banner")
        help_slide = next(
            s for sec in plan["sections"] for s in sec["slides"] if s["part_kind"] == "help"
        )
        help_slide["blocks"] = [{"kind": "text", "content": "", "gap": True,
                                  "gap_note": "No confirmed help route yet."}]
        self.write_plan("banner", plan)
        result, out = self.render("banner")
        self.assertEqual(result.returncode, 0, result.stderr)
        html = out.read_text(encoding="utf-8")
        self.assertIn("[GAP]", html)
        self.assertIn("No confirmed help route yet.", html)


class FontStackTests(unittest.TestCase):
    """_inline_font_stack must split every stack entry on "," before quoting — apply_brand.py's
    font_stack() appends web_safe_fallback (e.g. "system-ui, sans-serif") as one entry that
    already contains a comma."""

    def test_embedded_comma_fallback_is_split_not_quoted_whole(self):
        import render_comms_html
        theme = {"typography": {"body": ["Arial", "system-ui, sans-serif"]}}
        result = render_comms_html._inline_font_stack(theme, "body")
        self.assertEqual(result, "Arial, system-ui, sans-serif")
        self.assertNotIn("'system-ui, sans-serif'", result)

    def test_name_with_a_space_is_quoted(self):
        import render_comms_html
        theme = {"typography": {"body": ["Northwind Sans", "Arial"]}}
        result = render_comms_html._inline_font_stack(theme, "body")
        self.assertEqual(result, "'Northwind Sans', Arial")


class CtaUrlExtractionTests(unittest.TestCase):
    """_extract_cta_link never invents a destination: a URL embedded in the cta label becomes
    a real link; its absence falls back to plain text, with the caller responsible for
    warning (fill_edm does, at the point it calls this)."""

    def setUp(self):
        import render_comms_html
        self.mod = render_comms_html
        self.theme = {"palette": {"accent": "#1a7a45"}, "typography": {"body": ["Arial"]}}

    def test_url_in_label_becomes_a_real_link(self):
        part = {"blocks": [{"kind": "text",
                             "content": "Activate your account: https://portal.example/activate"}]}
        html, plain = self.mod._extract_cta_link(part, self.theme)
        self.assertIsNotNone(html)
        self.assertIsNone(plain)
        self.assertIn('href="https://portal.example/activate"', html)
        self.assertIn("Activate your account", html)

    def test_no_url_falls_back_to_plain_text_not_invented_link(self):
        part = {"blocks": [{"kind": "text", "content": "Activate your account now"}]}
        html, plain = self.mod._extract_cta_link(part, self.theme)
        self.assertIsNone(html)
        self.assertEqual(plain, "Activate your account now")

    def test_fill_edm_warns_on_stderr_when_cta_has_no_url(self):
        # Route this one through the real CLI so the warning's stderr path is exercised
        # end-to-end, not just the helper function in isolation.
        tmp = Path(tempfile.mkdtemp())
        try:
            for name in ("change_brief.json", "brand_profile.json"):
                shutil.copy(EXAMPLE_DIR / name, tmp / name)
            (tmp / "edm").mkdir()
            plan = json.loads((EXAMPLE_DIR / "edm" / "comms_plan.json").read_text(encoding="utf-8"))
            cta_section = next(s for s in plan["sections"] if s["section_id"] == "cta")
            cta_section["slides"][0]["blocks"][0]["content"] = "Activate your account now"
            (tmp / "edm" / "comms_plan.json").write_text(json.dumps(plan), encoding="utf-8")
            result = run(tmp / "edm" / "comms_plan.json", "--brief", tmp / "change_brief.json",
                         "--brand", tmp / "brand_profile.json", "-o", tmp / "edm" / "comms_edm.html")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("WARNING edm: cta part has no URL", result.stderr)
            html = (tmp / "edm" / "comms_edm.html").read_text(encoding="utf-8")
            self.assertIn("Activate your account now", html)
            self.assertNotIn("<a href", html, "no link should be invented when the label has no URL")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
