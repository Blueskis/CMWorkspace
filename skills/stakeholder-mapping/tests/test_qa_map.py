#!/usr/bin/env python3
"""Tests for qa_map.py (Q1-Q7 in the agreed test list, plus source and CLI checks).

    python skills/stakeholder-mapping/tests/test_qa_map.py [-v]
"""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _helpers import CONTEXT, SKILL, base_extraction
import build_map
import qa_map

SCRIPT = SKILL / "scripts" / "qa_map.py"


def clean_map():
    """A map that satisfies every rule, aviation lens included."""
    ex = base_extraction()
    ex["groups"] += [
        {"id": "G-REG", "name": "CAAS (regulator)", "business_unit": "External", "tier": 5,
         "sentiment": "Neutral", "evidence": ["E1"]},
        {"id": "G-ENG", "name": "Licensed B1/B2 engineers", "business_unit": "Operations", "tier": 3,
         "sentiment": "Skeptic", "evidence": ["E2"]},
        {"id": "G-QA", "name": "Quality & Safety", "business_unit": "Operations", "tier": 2,
         "sentiment": "Advocate", "evidence": ["E2"]},
        {"id": "G-SHIFT", "name": "Shift supervisors", "business_unit": "Operations", "tier": 3,
         "sentiment": "Neutral", "evidence": ["E2"]},
        {"id": "G-UNION", "name": "Union branch", "business_unit": "External", "tier": 5,
         "sentiment": "Neutral", "evidence": ["E2"]},
    ]
    for gid in ("G-REG", "G-ENG", "G-QA", "G-SHIFT", "G-UNION"):
        ex["relationships"].append({"id": f"RX-{gid}", "from": gid, "to": "G-OPS", "kind": "formal",
                                    "type": "governs", "strength": 1, "confidence": "Medium",
                                    "evidence": ["E1"]})
    m, _ = build_map.build(ex, CONTEXT)
    return m


def codes(items):
    return [i["code"] for i in items]


class QaTests(unittest.TestCase):
    def test_q7_clean_map_passes(self):
        r = qa_map.audit(clean_map())
        self.assertEqual(r["hard"], [], r["hard"])
        self.assertEqual(r["warnings"], [], r["warnings"])

    def test_q1_org_chart_unit_with_no_group_is_a_hard_fail(self):
        m = clean_map()
        m["meta"]["org_context"]["org_chart_units"].append("Procurement")
        r = qa_map.audit(m)
        self.assertIn("unit_uncovered", codes(r["hard"]))
        self.assertIn("Procurement", json.dumps(r["hard"]))

    def test_q1b_unit_listed_under_a_groups_org_units_counts_as_covered(self):
        m = clean_map()
        m["meta"]["org_context"]["org_chart_units"].append("Procurement")
        m["groups"][1]["org_units"] = ["Procurement"]
        self.assertNotIn("unit_uncovered", codes(qa_map.audit(m)["hard"]))

    def test_q2_pseudonymised_map_with_a_real_name_is_a_hard_fail(self):
        m, key = build_map.build(base_extraction(), CONTEXT, pseudonymise=True)
        self.assertNotIn("pseudonym_leak", codes(qa_map.audit(m, key=key)["hard"]))
        m["evidence"][1]["quote"] = "Ah Kow said the planners check with Finance."
        self.assertIn("pseudonym_leak", codes(qa_map.audit(m, key=key)["hard"]))

    def test_q2b_pseudonymised_map_with_a_named_individual_fails_without_a_key(self):
        m, _ = build_map.build(base_extraction(), CONTEXT, pseudonymise=True)
        m["individuals"][0]["name"] = "Tan Ah Kow"
        self.assertIn("pseudonym_leak", codes(qa_map.audit(m)["hard"]))

    def test_q3_high_confidence_informal_tie_on_hearsay_only_warns(self):
        m = clean_map()
        m["evidence"][1]["attribution"] = "hearsay"
        for r in m["relationships"]:
            if r["id"] == "R3":
                r["confidence"] = "High"
        self.assertIn("hearsay_high_confidence", codes(qa_map.audit(m)["warnings"]))

    def test_q4_group_without_sentiment_evidence_warns(self):
        m = clean_map()
        m["groups"][1]["sentiment"] = "Unknown"
        m["groups"][1]["evidence"] = []
        w = qa_map.audit(m)["warnings"]
        self.assertIn("no_sentiment_evidence", codes(w))
        self.assertIn("G-FIN", json.dumps(w))

    def test_q5_expected_industry_group_missing_warns_and_invents_nothing(self):
        m = clean_map()
        m["groups"] = [g for g in m["groups"] if g["id"] != "G-REG"]
        m["relationships"] = [r for r in m["relationships"] if "G-REG" not in (r["from"], r["to"])]
        before = copy.deepcopy(m)
        r = qa_map.audit(m)
        w = [x for x in r["warnings"] if x["code"] == "expected_group_missing"]
        self.assertEqual(len(w), 1)
        self.assertIn("regulator", w[0]["message"].lower())
        self.assertEqual(m, before)

    def test_q5b_unknown_industry_skips_the_lens(self):
        m = clean_map()
        m["meta"]["org_context"]["industry"] = "Artisanal cheese"
        m["groups"] = m["groups"][:3]
        m["relationships"] = [r for r in m["relationships"] if r["id"] in ("R1", "R2", "R3")]
        self.assertNotIn("expected_group_missing", codes(qa_map.audit(m)["warnings"]))

    def test_q6_group_with_no_relationships_warns(self):
        m = clean_map()
        m["groups"].append({"id": "G-LONE", "name": "Lonely", "business_unit": "X", "tier": 3,
                            "sentiment": "Neutral", "evidence": ["E1"], "metrics": {"degree": 0}})
        w = qa_map.audit(m)["warnings"]
        self.assertIn("isolated_group", codes(w))
        self.assertIn("G-LONE", json.dumps(w))

    def test_dangling_reference_in_a_hand_edited_map_is_a_hard_fail(self):
        m = clean_map()
        m["relationships"][0]["to"] = "G-NOPE"
        self.assertIn("dangling_reference", codes(qa_map.audit(m)["hard"]))

    def test_informal_tie_without_evidence_in_a_hand_edited_map_is_a_hard_fail(self):
        m = clean_map()
        for r in m["relationships"]:
            if r["id"] == "R3":
                r["evidence"] = []
        self.assertIn("informal_no_evidence", codes(qa_map.audit(m)["hard"]))

    def test_open_conflict_warns(self):
        m = clean_map()
        m["groups"][0]["conflicts"] = [{"field": "sentiment", "previous": "Advocate", "new": "Skeptic"}]
        self.assertIn("open_conflict", codes(qa_map.audit(m)["warnings"]))

    def test_q8_evidence_source_missing_from_sources_manifest_warns(self):
        m = clean_map()
        r = qa_map.audit(m, sources=[{"id": "ORG-01"}])
        self.assertIn("unknown_source", codes(r["warnings"]))
        self.assertIn("INT-01", json.dumps(r["warnings"]))

    def test_cli_exit_codes_and_report(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            m = clean_map()
            (t / "ok.json").write_text(json.dumps(m))
            r = subprocess.run([sys.executable, str(SCRIPT), str(t / "ok.json"), "-o", str(t / "qa.md")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("PASS", (t / "qa.md").read_text())
            m["meta"]["org_context"]["org_chart_units"].append("Procurement")
            (t / "bad.json").write_text(json.dumps(m))
            r = subprocess.run([sys.executable, str(SCRIPT), str(t / "bad.json"), "-o", str(t / "qa2.md")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("FAIL", (t / "qa2.md").read_text())


if __name__ == "__main__":
    unittest.main()
