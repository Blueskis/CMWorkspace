#!/usr/bin/env python3
"""Every shipped example must build, pass QA with no hard failures, name no group the lens
expects but is missing, and survive pseudonymisation with no leaked names.

    python skills/stakeholder-mapping/tests/test_examples.py [-v]
"""

import json
import unittest

from _helpers import SKILL
import build_map
import qa_map

EXAMPLES = SKILL / "examples"
FOLDERS = ["airline", "healthcare", "financial-services", "aviation-mro"]
LENS = {"airline": "aviation", "healthcare": "healthcare", "financial-services": "financial_services",
        "aviation-mro": "aviation"}


def load(folder, name):
    return json.loads((EXAMPLES / folder / name).read_text(encoding="utf-8"))


class ExampleTests(unittest.TestCase):
    def test_each_example_builds_and_passes_qa(self):
        for f in FOLDERS:
            with self.subTest(example=f):
                m, _ = build_map.build(load(f, "extraction.json"), load(f, "context.json"), as_of="2026-09-18")
                r = qa_map.audit(m, sources=load(f, "sources.json"))
                self.assertEqual(r["hard"], [], r["hard"])
                self.assertEqual(r["lens"], LENS[f])
                missing = [w for w in r["warnings"] if w["code"] == "expected_group_missing"]
                self.assertEqual(missing, [], missing)

    def test_each_example_is_a_real_network_not_a_tree(self):
        for f in FOLDERS:
            with self.subTest(example=f):
                m, _ = build_map.build(load(f, "extraction.json"), load(f, "context.json"))
                kinds = [r["kind"] for r in m["relationships"]]
                self.assertGreaterEqual(kinds.count("informal"), 10)
                self.assertGreaterEqual(len(m["groups"]), 18)
                self.assertGreaterEqual(len(m["individuals"]), 6)
                # at least one informal tie that crosses a formal reporting line
                evidence = {e["id"]: e for e in m["evidence"]}
                self.assertTrue(any(evidence[e]["attribution"] in ("testimony",) for r in m["relationships"]
                                    if r["kind"] == "informal" for e in r["evidence"]))

    def test_each_example_quotes_appear_in_its_source_documents(self):
        for f in FOLDERS:
            with self.subTest(example=f):
                docs = "\n".join(p.read_text(encoding="utf-8") for p in (EXAMPLES / f / "source_documents").iterdir()
                                 if p.suffix in (".md", ".vtt"))
                flat = " ".join(docs.split())
                for e in load(f, "extraction.json")["evidence"]:
                    if e["attribution"] == "document":
                        continue
                    self.assertIn(" ".join(e["quote"].split()), flat, f"{f} {e['id']}")

    def test_each_example_pseudonymises_without_a_leak(self):
        for f in FOLDERS:
            with self.subTest(example=f):
                m, key = build_map.build(load(f, "extraction.json"), load(f, "context.json"), pseudonymise=True)
                r = qa_map.audit(m, key=key)
                self.assertEqual(r["hard"], [], r["hard"])


if __name__ == "__main__":
    unittest.main()
