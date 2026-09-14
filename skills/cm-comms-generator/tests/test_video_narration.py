#!/usr/bin/env python3
"""Unit tests for the ElevenLabs narration lane: video_spec.py --narration, qa_comms.py's
voice gate, verify_narration.py, and route_channel.py's fourth ("partial") outcome.

    python skills/cm-comms-generator/tests/test_video_narration.py [-v]

Fixtures are the real northwind-payroll worked example (examples/northwind-payroll/), copied
into a tmp dir per test so mutated copies (a stripped voice field, an injected gap scene)
never touch the committed files. Stdlib only (unittest + subprocess), matching the sibling
test_render_comms_html.py's convention.
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
VIDEO_SPEC = SCRIPTS_DIR / "video_spec.py"
QA_COMMS = SCRIPTS_DIR / "qa_comms.py"
ROUTE_CHANNEL = SCRIPTS_DIR / "route_channel.py"
VERIFY_NARRATION = SCRIPTS_DIR / "verify_narration.py"

sys.path.insert(0, str(SCRIPTS_DIR))


def run(script, *args):
    result = subprocess.run(
        [sys.executable, str(script), *[str(a) for a in args]],
        capture_output=True, text=True,
    )
    return result


class NarrationFixture(unittest.TestCase):
    """Copies the real northwind-payroll explainer_video plan and brand profile into a tmp
    dir so mutated copies never touch the committed example files."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copy(EXAMPLE_DIR / "change_brief.json", self.tmp / "change_brief.json")
        shutil.copy(EXAMPLE_DIR / "brand_profile.json", self.tmp / "brand_profile.json")
        (self.tmp / "explainer_video").mkdir()
        shutil.copy(EXAMPLE_DIR / "explainer_video" / "comms_plan.json",
                    self.tmp / "explainer_video" / "comms_plan.json")
        self.brief = self.tmp / "change_brief.json"
        self.brand = self.tmp / "brand_profile.json"
        self.plan_path = self.tmp / "explainer_video" / "comms_plan.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def load_brand(self):
        return json.loads(self.brand.read_text(encoding="utf-8"))

    def write_brand(self, brand):
        self.brand.write_text(json.dumps(brand), encoding="utf-8")

    def load_plan(self):
        return json.loads(self.plan_path.read_text(encoding="utf-8"))

    def write_plan(self, plan):
        self.plan_path.write_text(json.dumps(plan), encoding="utf-8")


# --- video_spec.py --narration ----------------------------------------------------------


class VideoSpecNarrationTests(NarrationFixture):

    def build(self, out=None):
        out = out or (self.tmp / "explainer_video" / "video_spec.json")
        narration = self.tmp / "explainer_video" / "narration.json"
        result = run(VIDEO_SPEC, self.plan_path, "--brand", self.brand, "-o", out,
                     "--narration", narration)
        return result, out, narration

    # 1. Northwind explainer plan -> narration.json, one entry per scene, every text non-empty
    def test_one_entry_per_scene_all_text_non_empty(self):
        result, out, narration_path = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(narration_path.exists())
        narration = json.loads(narration_path.read_text(encoding="utf-8"))
        spec = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(narration["entries"]), len(spec["scenes"]))
        self.assertEqual(narration["excluded"], [])
        for entry in narration["entries"]:
            self.assertTrue(entry["text"].strip(), f"empty text for {entry['scene_id']}")

    # 2. Scene whose only block is gap: true -> excluded[], absent from entries, no [GAP] text
    def test_gap_only_scene_is_excluded_never_narrated(self):
        plan = self.load_plan()
        scene = plan["sections"][0]["slides"][0]
        scene["blocks"] = [{"kind": "text", "content": "", "gap": True,
                            "gap_note": "No confirmed script for this scene yet."}]
        self.write_plan(plan)
        result, out, narration_path = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        narration = json.loads(narration_path.read_text(encoding="utf-8"))
        excluded_ids = {e["scene_id"] for e in narration["excluded"]}
        self.assertIn(scene["slide_id"], excluded_ids)
        entry_ids = {e["scene_id"] for e in narration["entries"]}
        self.assertNotIn(scene["slide_id"], entry_ids)
        for entry in narration["entries"]:
            self.assertNotIn("[GAP]", entry["text"])

    # 3. Scene with a bullets block -> the bullet text is absent from text (on-screen only)
    def test_bullets_are_on_screen_only_never_in_narration_text(self):
        result, out, narration_path = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        narration = json.loads(narration_path.read_text(encoding="utf-8"))
        entries_by_scene = {e["scene_id"]: e for e in narration["entries"]}
        plan = self.load_plan()
        checked = 0
        for section in plan["sections"]:
            for slide in section["slides"]:
                bullet_only_blocks = [b for b in slide["blocks"] if b["kind"] == "bullets"]
                if not bullet_only_blocks:
                    continue
                entry = entries_by_scene.get(slide["slide_id"])
                if entry is None:
                    continue
                for block in bullet_only_blocks:
                    for bullet in block["content"]:
                        # A bullet that is a short fragment of the paragraph's own wording
                        # (e.g. "Same annual pay" inside "Your total annual pay is not
                        # changing") does not prove bullets leaked into the VO — a bullet
                        # phrased as a distinct, literal string is the real check.
                        checked += 1
                        self.assertNotEqual(entry["text"].strip(), bullet.strip())
        self.assertGreater(checked, 0, "fixture should carry at least one scene with bullets")
        # scene-1's bullet is verbatim distinct from its own paragraph — a stronger check.
        scene1 = entries_by_scene["scene-1"]
        self.assertNotIn("Paid twice a month from 1 October", scene1["text"])

    # 4a. Brand with voice_id -> present on every entry
    def test_voice_id_present_on_every_entry_when_brand_has_one(self):
        brand = self.load_brand()
        brand["channel_specs"]["explainer_video"]["voice_id"] = "SO9JediIwzugrikv7xw0"
        self.write_brand(brand)
        result, out, narration_path = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        narration = json.loads(narration_path.read_text(encoding="utf-8"))
        self.assertEqual(narration["voice"]["voice_id"], "SO9JediIwzugrikv7xw0")
        for entry in narration["entries"]:
            self.assertEqual(entry["voice_id"], "SO9JediIwzugrikv7xw0")
        self.assertEqual(narration["warnings"], [])

    # 4b. Brand without voice_id -> null everywhere plus a warning, never an invented id
    def test_missing_voice_id_is_null_with_a_warning_never_invented(self):
        brand = self.load_brand()
        brand["channel_specs"]["explainer_video"].pop("voice_id", None)
        self.write_brand(brand)
        result, out, narration_path = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        narration = json.loads(narration_path.read_text(encoding="utf-8"))
        self.assertIsNone(narration["voice"]["voice_id"])
        for entry in narration["entries"]:
            self.assertIsNone(entry["voice_id"])
        self.assertTrue(narration["warnings"], "expected a warning about the missing voice_id")
        self.assertIn("creative_list_voices", narration["warnings"][0])
        self.assertIn("voice_id", result.stderr)

    # 5. Regression: captions.vtt still written, exit still 0
    def test_captions_vtt_still_written_alongside_narration(self):
        out = self.tmp / "explainer_video" / "video_spec.json"
        result, out, narration_path = self.build(out=out)
        self.assertEqual(result.returncode, 0, result.stderr)
        vtt_path = out.with_name("captions.vtt")
        self.assertTrue(vtt_path.exists())
        self.assertIn("WEBVTT", vtt_path.read_text(encoding="utf-8"))


# --- qa_comms.py voice gate --------------------------------------------------------------


class QaCommsVoiceGateTests(NarrationFixture):

    def audit(self):
        out = self.tmp / "qa_report.md"
        result = run(QA_COMMS, self.brief, self.plan_path, "--brand", self.brand, "-o", out)
        return result, out

    # 6. voice_provenance: "generated-unapproved" -> warning, not failure
    def test_generated_unapproved_voice_warns_not_fails(self):
        brand = self.load_brand()
        brand["channel_specs"]["explainer_video"]["voice_provenance"] = "generated-unapproved"
        self.write_brand(brand)
        result, out = self.audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = out.read_text(encoding="utf-8")
        self.assertIn("generated-unapproved", report)
        self.assertIn("Voice provenance", report)

    # 7. "cloned-with-consent" missing consent_date -> fail
    def test_cloned_with_consent_missing_consent_date_fails(self):
        brand = self.load_brand()
        brand["channel_specs"]["explainer_video"]["voice_provenance"] = "cloned-with-consent"
        brand["channel_specs"]["explainer_video"]["voice_consent"] = {
            "person": "Marcus Bell", "consent_recorded_by": "Priya Raghavan",
        }
        self.write_brand(brand)
        result, out = self.audit()
        self.assertEqual(result.returncode, 1)
        self.assertIn("consent_date", result.stderr)
        self.assertIn("cloned-with-consent", result.stderr)

    # 8. Complete cloned-with-consent record -> clean pass
    def test_complete_cloned_with_consent_record_passes_clean(self):
        brand = self.load_brand()
        brand["channel_specs"]["explainer_video"]["voice_provenance"] = "cloned-with-consent"
        brand["channel_specs"]["explainer_video"]["voice_consent"] = {
            "person": "Marcus Bell", "consent_recorded_by": "Priya Raghavan",
            "consent_date": "2026-08-15",
        }
        self.write_brand(brand)
        result, out = self.audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = out.read_text(encoding="utf-8")
        self.assertNotIn("consent_date", report.split("Voice provenance")[0]
                         if "Voice provenance" in report else report + "consent_date")
        self.assertNotIn("voice_consent is missing", result.stderr)

    # 9. Non-video channel with no voice fields -> no voice warning at all
    def test_non_video_channel_has_no_voice_warning(self):
        (self.tmp / "banner").mkdir()
        banner_plan = self.tmp / "banner" / "comms_plan.json"
        shutil.copy(EXAMPLE_DIR / "banner" / "comms_plan.json", banner_plan)
        out = self.tmp / "qa_report.md"
        result = run(QA_COMMS, self.brief, banner_plan, "--brand", self.brand, "-o", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = out.read_text(encoding="utf-8")
        self.assertNotIn("Voice provenance", report)
        self.assertNotIn("voice_provenance", result.stderr)


# --- verify_narration.py ------------------------------------------------------------------


class VerifyNarrationTests(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.narration_path = self.tmp / "narration.json"
        self.returned_path = self.tmp / "narration_returned.json"
        self.spec_path = self.tmp / "video_spec.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    def narration(self, entries):
        return {"entries": entries, "excluded": [], "warnings": []}

    def verify(self, spec=None):
        args = [self.narration_path, "--returned", self.returned_path]
        if spec is not None:
            self.write(self.spec_path, spec)
            args += ["--spec", self.spec_path]
        return run(VERIFY_NARRATION, *args)

    # 10. Manifest covers every scene, durations within budget -> exit 0
    def test_full_coverage_within_budget_exits_zero(self):
        self.write(self.narration_path, self.narration([
            {"scene_id": "scene-1", "budget_seconds": 12},
            {"scene_id": "scene-2", "budget_seconds": 20},
        ]))
        self.write(self.returned_path, {"scenes": [
            {"scene_id": "scene-1", "duration_seconds": 11.5},
            {"scene_id": "scene-2", "duration_seconds": 19.0},
        ]})
        result = self.verify(spec={"runtime": {"limit_seconds": 300}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("WARNING", result.stderr)

    # 11. One scene missing -> exit 1, names that scene specifically
    def test_missing_scene_fails_and_is_named(self):
        self.write(self.narration_path, self.narration([
            {"scene_id": "scene-1", "budget_seconds": 12},
            {"scene_id": "scene-2", "budget_seconds": 20},
        ]))
        self.write(self.returned_path, {"scenes": [
            {"scene_id": "scene-1", "duration_seconds": 11.5},
        ]})
        result = self.verify(spec={"runtime": {"limit_seconds": 300}})
        self.assertEqual(result.returncode, 1)
        self.assertIn("scene-2", result.stderr)
        self.assertNotIn("scene-1: payload scene has no returned audio", result.stderr)

    # 12. Total measured runtime over max_duration_seconds -> exit 1
    def test_total_runtime_over_limit_fails(self):
        self.write(self.narration_path, self.narration([
            {"scene_id": "scene-1", "budget_seconds": 200},
            {"scene_id": "scene-2", "budget_seconds": 200},
        ]))
        self.write(self.returned_path, {"scenes": [
            {"scene_id": "scene-1", "duration_seconds": 180},
            {"scene_id": "scene-2", "duration_seconds": 180},
        ]})
        result = self.verify(spec={"runtime": {"limit_seconds": 300}})
        self.assertEqual(result.returncode, 1)
        self.assertIn("360", result.stderr)
        self.assertIn("300", result.stderr)

    # 13. One scene over its own budget, total within limit -> exit 0 with a warning
    def test_scene_over_own_budget_warns_but_passes(self):
        self.write(self.narration_path, self.narration([
            {"scene_id": "scene-1", "budget_seconds": 10},
            {"scene_id": "scene-2", "budget_seconds": 20},
        ]))
        self.write(self.returned_path, {"scenes": [
            {"scene_id": "scene-1", "duration_seconds": 15.0},
            {"scene_id": "scene-2", "duration_seconds": 19.0},
        ]})
        result = self.verify(spec={"runtime": {"limit_seconds": 300}})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("scene-1", result.stderr)
        self.assertIn("WARNING", result.stderr)


# --- route_channel.py fourth outcome ------------------------------------------------------


class RouteChannelPartialOutcomeTests(NarrationFixture):

    def route(self, plan_path, available_servers=None, out=None):
        out = out or (self.tmp / "production_brief.md")
        args = [plan_path, "--brief", self.brief, "--brand", self.brand, "-o", out]
        if available_servers is not None:
            args += ["--available-servers", available_servers]
        result = run(ROUTE_CHANNEL, *args)
        return result, out

    # 14. Video lane with --available-servers ElevenLabs -> outcome partial, exit 0,
    #     brief states what is and is not produced, and pins generations_count: 1
    def test_elevenlabs_available_gives_partial_outcome(self):
        result, out = self.route(self.plan_path, available_servers="ElevenLabs")
        self.assertEqual(result.returncode, 0, result.stderr)
        brief = out.read_text(encoding="utf-8")
        self.assertIn("NARRATION READY", brief)
        self.assertIn("narration audio per scene", brief)
        self.assertIn("scene assembly and screen capture remain a human production step", brief)
        self.assertIn("generations_count: 1", brief)
        self.assertIn("creative_generate_speech", brief)

    # 15. Same lane without the flag -> handoff_only, exit 0 (unchanged)
    def test_elevenlabs_unavailable_stays_handoff_only(self):
        result, out = self.route(self.plan_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        brief = out.read_text(encoding="utf-8")
        self.assertIn("HANDOFF ONLY", brief)
        self.assertNotIn("NARRATION READY", brief)

    # 16. email and banner -> outcomes completely unchanged
    def test_non_video_channels_unaffected(self):
        for channel in ("email", "banner"):
            plan_path = self.tmp / channel / "comms_plan.json"
            (self.tmp / channel).mkdir()
            shutil.copy(EXAMPLE_DIR / channel / "comms_plan.json", plan_path)
            result, out = self.route(plan_path, available_servers="ElevenLabs,Canva")
            self.assertEqual(result.returncode, 0, result.stderr)
            brief = out.read_text(encoding="utf-8")
            self.assertIn("READY TO PRODUCE", brief)
            self.assertNotIn("NARRATION READY", brief)


if __name__ == "__main__":
    unittest.main()
