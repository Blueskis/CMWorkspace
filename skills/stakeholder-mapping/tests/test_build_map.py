#!/usr/bin/env python3
"""Tests for build_map.py (B1-B10 in the agreed test list, plus guards).

    python skills/stakeholder-mapping/tests/test_build_map.py [-v]
"""

import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from _helpers import CONTEXT, SKILL, base_extraction, chain_extraction
import build_map

SCRIPT = SKILL / "scripts" / "build_map.py"
by_id = lambda items: {i["id"]: i for i in items}


class BuildTests(unittest.TestCase):
    def test_b1_valid_extraction_builds_with_metrics(self):
        m, _ = build_map.build(base_extraction(), CONTEXT, as_of="2026-09-01")
        self.assertEqual({g["id"] for g in m["groups"]}, {"G-EXEC", "G-FIN", "G-OPS"})
        self.assertEqual(len(m["relationships"]), 3)
        self.assertEqual(sum(r["kind"] == "informal" for r in m["relationships"]), 1)
        g = by_id(m["groups"])["G-OPS"]
        self.assertEqual(g["metrics"]["informal_degree"], 1)
        self.assertEqual(g["metrics"]["formal_degree"], 2)
        self.assertEqual(g["last_updated"], "2026-09-01")
        self.assertEqual(m["meta"]["org_context"]["industry"], "Aviation MRO")
        self.assertFalse(m["meta"]["pseudonymised"])

    def test_b2_same_person_in_two_interviews_is_one_individual(self):
        ex = base_extraction()
        ex["individuals"].append({"id": "P-AKT", "group": "G-OPS", "name": "A.K. Tan",
                                  "title": "Senior Planner", "evidence": ["E3"]})
        ex["evidence"].append({"id": "E3", "source": "INT-02", "quote": "AK keeps the backlog.",
                               "speaker": "Planner", "attribution": "claim"})
        ex["relationships"].append({"id": "R4", "from": "P-AKT", "to": "G-EXEC", "kind": "informal",
                                    "type": "trusts", "strength": 1, "confidence": "Low",
                                    "evidence": ["E3"]})
        m, _ = build_map.build(ex, CONTEXT)
        self.assertEqual(len(m["individuals"]), 1)
        p = m["individuals"][0]
        self.assertEqual(p["id"], "P-TAN")
        self.assertEqual(set(p["evidence"]), {"E2", "E3"})
        self.assertIn("A.K. Tan", p["aliases"])
        self.assertEqual(by_id(m["relationships"])["R4"]["from"], "P-TAN")
        self.assertEqual(m["meta"]["merged_individuals"][0]["dropped"], "P-AKT")

    def test_b2b_similar_but_different_people_are_not_merged(self):
        ex = base_extraction()
        ex["individuals"][0]["name"] = "Ah Kow Tan"
        ex["individuals"].append({"id": "P-OTH", "group": "G-OPS", "name": "Ah Kee Tan",
                                  "title": "Senior Planner", "evidence": ["E2"]})
        m, _ = build_map.build(ex, CONTEXT)
        self.assertEqual(len(m["individuals"]), 2)

    def test_b3_dangling_reference_fails_and_names_the_id(self):
        ex = base_extraction()
        ex["relationships"][0]["to"] = "G-NOPE"
        with self.assertRaises(build_map.MapError) as cm:
            build_map.build(ex, CONTEXT)
        self.assertIn("G-NOPE", "\n".join(cm.exception.errors))

    def test_b3_cli_writes_nothing_on_failure(self):
        ex = base_extraction()
        ex["relationships"][0]["to"] = "G-NOPE"
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "ex.json").write_text(json.dumps(ex))
            (t / "ctx.json").write_text(json.dumps(CONTEXT))
            r = subprocess.run([sys.executable, str(SCRIPT), str(t / "ex.json"), str(t / "ctx.json"),
                                "-o", str(t / "map.json")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("G-NOPE", r.stderr)
            self.assertFalse((t / "map.json").exists())

    def test_b4_informal_relationship_needs_evidence(self):
        ex = base_extraction()
        ex["relationships"][2]["evidence"] = []
        with self.assertRaises(build_map.MapError) as cm:
            build_map.build(ex, CONTEXT)
        self.assertIn("R3", "\n".join(cm.exception.errors))

    def test_b5_empty_extraction_fails(self):
        with self.assertRaises(build_map.MapError) as cm:
            build_map.build({"groups": [], "individuals": [], "relationships": [], "evidence": []},
                            CONTEXT)
        self.assertIn("no groups", "\n".join(cm.exception.errors).lower())

    def test_invalid_enum_values_are_rejected(self):
        ex = base_extraction()
        ex["groups"][0]["sentiment"] = "Furious"
        ex["relationships"][2]["type"] = "approves"  # a formal type on an informal tie
        with self.assertRaises(build_map.MapError) as cm:
            build_map.build(ex, CONTEXT)
        msg = "\n".join(cm.exception.errors)
        self.assertIn("Furious", msg)
        self.assertIn("R3", msg)

    def test_b6_pseudonymise_leaves_no_real_name_anywhere(self):
        ex = base_extraction()
        ex["groups"][2]["summary"] = "Led informally by Tan, who the planners trust."
        m, key = build_map.build(ex, CONTEXT, pseudonymise=True)
        dump = json.dumps(m)
        for leak in (r"\bAh Kow\b", r"\bKow\b", r"\bTan\b", r"P-TAN"):
            self.assertIsNone(re.search(leak, dump, re.I), leak)
        self.assertTrue(m["meta"]["pseudonymised"])
        p = m["individuals"][0]
        self.assertRegex(p["name"], r"^Person-\d+$")
        self.assertEqual(p["id"], p["name"])
        self.assertEqual(key[p["id"]]["name"], "Tan, Ah Kow")
        self.assertEqual(p["group"], "G-OPS")

    def test_b6b_pseudonym_aliases_are_stable_between_runs(self):
        _, k1 = build_map.build(base_extraction(), CONTEXT, pseudonymise=True)
        _, k2 = build_map.build(base_extraction(), CONTEXT, pseudonymise=True)
        self.assertEqual(k1, k2)

    def test_b7_merge_preserves_ids_and_touches_only_changed_items(self):
        first, _ = build_map.build(base_extraction(), CONTEXT, as_of="2026-09-01")
        new = {"groups": [{"id": "G-FIN", "name": "Finance", "summary": "Also owns vendor payments.",
                           "evidence": ["E9"]}],
               "individuals": [{"id": "P-LIM", "group": "G-FIN", "name": "Lim Mei Ling",
                                "title": "Finance Manager", "evidence": ["E9"]}],
               "relationships": [],
               "evidence": [{"id": "E9", "source": "INT-04", "quote": "Finance also pays vendors.",
                             "speaker": "Finance Manager", "attribution": "testimony"}]}
        m, _ = build_map.build(new, CONTEXT, previous=first, as_of="2026-10-01")
        g = by_id(m["groups"])
        self.assertEqual(g["G-OPS"]["last_updated"], "2026-09-01")
        self.assertEqual(g["G-EXEC"]["last_updated"], "2026-09-01")
        self.assertEqual(g["G-FIN"]["last_updated"], "2026-10-01")
        self.assertEqual(g["G-FIN"]["summary"], "Also owns vendor payments.")
        self.assertEqual(g["G-FIN"]["headcount"], 20)  # untouched fields survive
        self.assertIn("E1", g["G-FIN"]["evidence"])
        self.assertIn("E9", g["G-FIN"]["evidence"])
        self.assertEqual({i["id"] for i in m["individuals"]}, {"P-TAN", "P-LIM"})
        self.assertEqual(len(m["relationships"]), 3)

    def test_b7b_merge_refuses_a_pseudonymised_previous_map(self):
        first, _ = build_map.build(base_extraction(), CONTEXT, pseudonymise=True)
        with self.assertRaises(build_map.MapError):
            build_map.build(base_extraction(), CONTEXT, previous=first)

    def test_b8_contradicting_sentiment_keeps_both_evidence_and_goes_low(self):
        first, _ = build_map.build(base_extraction(), CONTEXT, as_of="2026-09-01")
        new = {"groups": [{"id": "G-OPS", "name": "Plant Maintenance Planners",
                           "sentiment": "Skeptic", "evidence": ["E9"]}],
               "individuals": [], "relationships": [],
               "evidence": [{"id": "E9", "source": "INT-05", "quote": "The planners will not use it.",
                             "speaker": "Planning Manager", "attribution": "testimony"}]}
        m, _ = build_map.build(new, CONTEXT, previous=first, as_of="2026-10-01")
        g = by_id(m["groups"])["G-OPS"]
        self.assertTrue({"E2", "E9"} <= set(g["evidence"]))
        self.assertEqual(g["confidence"], "Low")
        self.assertEqual(len(g["conflicts"]), 1)
        self.assertEqual((g["conflicts"][0]["previous"], g["conflicts"][0]["new"]),
                         ("Advocate", "Skeptic"))
        # a later merge that adds nothing keeps the open conflict
        again, _ = build_map.build({"groups": [], "individuals": [], "relationships": [],
                                    "evidence": []}, CONTEXT, previous=m, as_of="2026-11-01")
        self.assertEqual(len(by_id(again["groups"])["G-OPS"]["conflicts"]), 1)

    def test_b9_high_betweenness_suggests_broker_without_overwriting_label(self):
        m, _ = build_map.build(chain_extraction(5, ona_middle="Energiser"), CONTEXT)
        mid = by_id(m["groups"])["G2"]
        self.assertEqual(mid["metrics"]["suggested_ona_role"], "Broker")
        self.assertEqual(mid["ona_role"], "Energiser")
        self.assertEqual(by_id(m["groups"])["G0"]["metrics"]["suggested_ona_role"], "Peripheral")

    def test_b9b_a_formal_hub_is_not_suggested_as_a_broker_once_informal_ties_exist(self):
        ex = chain_extraction(5)
        ex["evidence"].append({"id": "E1", "source": "S", "quote": "q", "speaker": "", "attribution": "testimony"})
        ex["relationships"].append({"id": "RI", "from": "G0", "to": "G4", "kind": "informal",
                                    "type": "consults", "strength": 1, "confidence": "Low", "evidence": ["E1"]})
        m, _ = build_map.build(ex, CONTEXT)
        g = by_id(m["groups"])
        self.assertIsNone(g["G2"]["metrics"]["suggested_ona_role"])  # formal-only middle node
        self.assertIn("informal_betweenness", g["G2"]["metrics"])

    def test_b10_two_hundred_groups_build_fast(self):
        ex = chain_extraction(200)
        t0 = time.time()
        m, _ = build_map.build(ex, CONTEXT)
        self.assertLess(time.time() - t0, 5)
        self.assertEqual(len(m["groups"]), 200)


if __name__ == "__main__":
    unittest.main()
