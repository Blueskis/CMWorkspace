#!/usr/bin/env python3
"""Unit test for render_markdown.py's edm renderer (Stage 3a Markdown draft support).

Before this, "edm" had no entry in render_markdown.py's renderers dict and the script
would sys.exit if asked to draft one — a real functional gap since edm is a registered
channel in schemas/channel_registry.json.

    python skills/cm-comms-generator/tests/test_render_markdown_edm.py [-v]
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills" / "cm-comms-generator" / "scripts" / "render_markdown.py"
EDM_PLAN = ROOT / "examples" / "northwind-payroll" / "edm" / "comms_plan.json"
BRAND = ROOT / "examples" / "northwind-payroll" / "brand_profile.json"


class RenderMarkdownEdmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "draft.md"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def render(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(EDM_PLAN), "--brand", str(BRAND), "-o", str(self.out)],
            capture_output=True, text=True,
        )

    def test_edm_has_a_renderer_and_treats_subject_preheader_as_headers(self):
        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("no renderer for channel", result.stderr)
        draft = self.out.read_text(encoding="utf-8")
        self.assertIn("**Subject:**", draft)
        self.assertIn("**Preheader:**", draft)
        self.assertIn("Your pay cadence is changing", draft)
        self.assertIn("**Call to action:**", draft)

    def test_edm_body_word_count_excludes_subject_and_preheader(self):
        result = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        draft = self.out.read_text(encoding="utf-8")
        self.assertIn("excludes the subject and preheader", draft)


if __name__ == "__main__":
    unittest.main()
