"""Parity and behaviour tests for the Copilot pack (test cases A1-A4, B5-B11).

Each scenario runs the skill's engine.js, pastes the engine's own TSV blocks
into a copy of the workbook exactly as a person would, recalculates it in
LibreOffice, and checks the workbook's numbers against the engine's. If the
two disagree, one of them has drifted from estimator.html.

Run:  python3 -m unittest discover -s skills/cm-effort-estimator/copilot/tests
Needs node, openpyxl and LibreOffice. The recalculation helper is the xlsx
skill's recalc.py; point XLSX_RECALC at it if it lives somewhere else.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent
ENGINE = PACK / "skill" / "cm-effort-estimator" / "scripts" / "engine.js"
WORKBOOK = PACK / "dist" / "CM-Effort-Estimator.xlsx"
RECALC = Path(os.environ.get("XLSX_RECALC", "/mnt/skills/public/xlsx/scripts/recalc.py"))

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover
    load_workbook = None


def run(cmd, payload=None):
    out = subprocess.run(["node", str(ENGINE), cmd], input=json.dumps(payload or {}),
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def cell_value(raw):
    if raw == "":
        return None
    try:
        f = float(raw)
        return int(f) if f.is_integer() else f
    except ValueError:
        return raw


def paste(wb, anchor, tsv):
    sheet, ref = anchor.split("!")
    ws = wb[sheet]
    col0 = ord(ref[0]) - 64
    row0 = int(ref[1:])
    for i, line in enumerate(tsv.split("\n") if tsv else []):
        for j, raw in enumerate(line.split("\t")):
            ws.cell(row=row0 + i, column=col0 + j, value=cell_value(raw))


def fill_and_recalc(out, extra_adjustments=()):
    """Export, paste every TSV block, optionally add Proposed rows, recalc, return values."""
    exported = run("export", {"state": out["state"]})
    report = exported["report"]
    tmp = Path(tempfile.mkdtemp())
    path = tmp / "estimate.xlsx"
    shutil.copy(WORKBOOK, path)
    wb = load_workbook(path)
    for anchor, block in exported["blocks"].items():
        paste(wb, anchor, block)
    n = len(report["judgement"]["log"])
    ws = wb["Adjustments"]
    for k, row in enumerate(extra_adjustments):
        for j, v in enumerate(row):
            ws.cell(row=6 + n + k, column=1 + j, value=v)
    wb.save(path)
    res = subprocess.run([sys.executable, str(RECALC), str(path), "300"], capture_output=True, text=True,
                         cwd=str(RECALC.parent))
    status = json.loads(res.stdout)
    assert status.get("status") == "success", status
    vals = load_workbook(path, data_only=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return vals


def summary(vals):
    s = vals["Summary"]
    return {"baseline": s["B5"].value, "current": s["C5"].value, "preview": s["D5"].value,
            "client": s["C8"].value, "options": s["C9"].value, "fte": s["C10"].value,
            "deliverables": s["C12"].value, "warning": s["B16"].value or "",
            "ranks": {s.cell(row=r, column=1).value: s.cell(row=r, column=2).value for r in range(24, 31)}}


def line_mandays(vals):
    ws = vals["Lines"]
    out = {}
    for r in range(6, 112):
        if ws.cell(row=r, column=18).value == "Y" and ws.cell(row=r, column=19).value != "Y":
            out[ws.cell(row=r, column=1).value] = round(ws.cell(row=r, column=17).value or 0, 1)
    return out


SAMPLES = None


def samples():
    global SAMPLES
    if SAMPLES is None:
        SAMPLES = run("data")["samples"]
    return SAMPLES


def analysed(sample="publicAuthority", scope="global"):
    return run("analyse", {"rfpText": samples()[sample], "scopeType": scope, "client": "Test"})


@unittest.skipUnless(load_workbook and RECALC.exists() and shutil.which("soffice") and shutil.which("node"),
                     "needs openpyxl, LibreOffice, node and recalc.py")
class WorkbookParity(unittest.TestCase):

    def assertClose(self, a, b, msg=""):
        self.assertLessEqual(abs((a or 0) - (b or 0)), 0.1, f"{msg}: workbook {a} vs engine {b}")

    def assertParity(self, out, vals):
        rep = out["report"]
        s = summary(vals)
        self.assertClose(s["current"], rep["totals"]["ourMandays"], "total")
        self.assertClose(s["baseline"], rep["judgement"]["baseline"], "baseline")
        self.assertClose(s["client"], rep["totals"]["clientMandays"], "client effort")
        self.assertClose(s["options"], rep["totals"]["optionsMandays"], "options")
        self.assertClose(s["fte"], rep["totals"]["averageFte"], "FTE")
        self.assertEqual(s["deliverables"], rep["totals"]["deliverables"], "deliverable count")
        for r in rep["byRank"]:
            self.assertClose(s["ranks"].get(r["rank"]), r["mandays"], f"rank {r['rank']}")
        engine_lines = {l["id"]: l["mandays"] for l in rep["lines"] if not l["custom"]}
        wb_lines = line_mandays(vals)
        self.assertEqual(set(wb_lines), set(engine_lines), "same lines in the estimate")
        for k, v in engine_lines.items():
            self.assertClose(wb_lines[k], v, k)

    # A1
    def test_A1_public_authority_sample_matches(self):
        out = analysed()
        self.assertParity(out, fill_and_recalc(out))

    def test_A1b_transport_sample_both_streams_matches(self):
        out = analysed("transport", "both")
        out = run("set", {"state": out["state"], "changes": {
            "deliveryMode": "physical", "involvement": {"local": 60}, "reviewCycles": 2, "contingency": 10,
            "lines": {"global:eu_training": {"mode": "virtual"}, "local:ilt_materials": {"level": "Complex"}}}})
        self.assertParity(out, fill_and_recalc(out))

    # A3
    def test_A3_minimal_drivers_finite_and_matching(self):
        out = run("estimate", {"state": None, "scopeType": "global"})
        ones = {k: 1 for k in ["headcount", "units", "geos", "languages", "waves", "months", "modules",
                               "sessionSize", "hypercareMonths", "complexity"]}
        out = run("set", {"state": out["state"], "changes": {"drivers": ones}})
        self.assertGreater(out["report"]["totals"]["ourMandays"], 0)
        self.assertParity(out, fill_and_recalc(out))

    # A4
    def test_A4_waves_move_only_wave_lines_in_both_engines(self):
        out = analysed()
        before = {l["id"]: l["qty"] for l in out["report"]["lines"]}
        after_out = run("set", {"state": out["state"], "changes": {"drivers": {"waves": 5}}})
        after = {l["id"]: l["qty"] for l in after_out["report"]["lines"]}
        changed = {k for k in before if before[k] != after.get(k)}
        self.assertIn("global:readiness_assess", changed)
        self.assertNotIn("global:cm_plan", changed)
        self.assertParity(after_out, fill_and_recalc(after_out))

    # B5-B8, custom lines and the full judgement log
    def test_B5_to_B8_judgement_log_matches(self):
        out = analysed()
        out = run("set", {"state": out["state"], "changes": {"addLines": [
            {"id": "custom_1", "stream": "global", "name": "Union briefing pack", "archetype": "Decks & Visual Assets",
             "level": "Standard", "qty": 3}]}})
        props = [
            {"op": "set_driver", "target": "waves", "value": 5, "rationale": "Five onboarding waves", "confidence": "high"},
            {"op": "set_driver", "target": "maturity", "value": "low", "rationale": "No change lead"},
            {"op": "set_line_level", "target": "global:impact_assessment", "value": "Complex", "rationale": "Three unions"},
            {"op": "set_line_qty", "target": "custom_1", "value": 7, "rationale": "One pack per union"},
            {"op": "set_line_include", "target": "global:sharepoint_site", "value": False, "rationale": "Client builds the site"},
            {"op": "set_global", "target": "contingency", "value": 10, "rationale": "Volatile scope"},
            {"op": "add_line", "target": "global", "value": {"name": "Ministry gate packs", "qty": 4, "level": "Complex",
                                                             "archetype": "Decks & Visual Assets"}, "rationale": "Sign-off at every gate"},
            {"op": "set_line_qty", "target": "global:impact_assessment", "value": 6, "rationale": "Six business areas"},
        ]
        acc = run("accept", {"state": out["state"], "proposals": props})
        self.assertTrue(all(r["ok"] for r in acc["results"]), acc["results"])
        log = acc["report"]["judgement"]["log"]
        rev = run("revert", {"state": acc["state"], "ids": [log[1]["id"]]})   # maturity reverted
        proposed = [{"op": "set_driver", "target": "units", "value": 7, "rationale": "Seven units"},
                    {"op": "set_global", "target": "reviewCycles", "value": 2, "rationale": "Two review rounds"}]
        pv = run("preview", {"state": rev["state"], "proposals": proposed})
        extra = [[f"p{i}", p["op"], p["target"], p["value"], p["rationale"], "medium", "Proposed", 0]
                 for i, p in enumerate(proposed)]
        vals = fill_and_recalc(rev, extra)
        self.assertParity(rev, vals)
        s = summary(vals)
        self.assertClose(s["preview"], pv["ifAllAccepted"], "preview total")             # B5
        self.assertClose(s["current"], rev["report"]["totals"]["ourMandays"], "current")  # B6/B7/B8

    # B9, B10
    def test_B9_B10_invalid_and_out_of_scope_rows_are_refused(self):
        out = analysed()
        bad = [["x1", "set_global", "involvement.global", 140, "too high", "low", "Accepted", 0],
               ["x2", "set_global", "taskHours", 30, "admin", "low", "Accepted", 0],
               ["x3", "set_line_qty", "global:not_a_line", 3, "nope", "low", "Accepted", 0],
               ["x4", "set_driver", "waves", 9, "", "low", "Accepted", 0]]
        vals = fill_and_recalc(out, bad)
        checks = [vals["Adjustments"].cell(row=6 + i, column=9).value for i in range(4)]
        self.assertTrue(checks[0].startswith("Invalid"), checks[0])
        self.assertTrue(checks[1].startswith("Out of scope"), checks[1])
        self.assertTrue(checks[2].startswith("Invalid"), checks[2])
        self.assertTrue(checks[3].startswith("Invalid"), checks[3])
        self.assertClose(summary(vals)["current"], out["report"]["totals"]["ourMandays"], "refused rows move nothing")

    # Agent test 20: a saved workbook restarts a new chat at the same total
    def test_20_resume_from_the_workbook_state_sheet(self):
        out = analysed()
        acc = run("accept", {"state": out["state"], "proposals": [
            {"op": "set_driver", "target": "waves", "value": 4, "rationale": "Four waves"}]})
        vals = fill_and_recalc(acc)
        resumed = run("estimate", {"state": json.loads(vals["State"]["A6"].value)})
        self.assertEqual(resumed["report"]["totals"]["ourMandays"], acc["report"]["totals"]["ourMandays"])
        self.assertClose(summary(vals)["current"], resumed["report"]["totals"]["ourMandays"], "workbook vs resumed")

    # B11
    def test_B11_warning_past_forty_percent(self):
        out = analysed()
        acc = run("accept", {"state": out["state"], "proposals": [
            {"op": "set_driver", "target": "waves", "value": 12, "rationale": "Twelve waves"},
            {"op": "set_driver", "target": "units", "value": 20, "rationale": "Twenty units"}]})
        self.assertTrue(acc["report"]["judgement"]["warning"])
        vals = fill_and_recalc(acc)
        self.assertIn("more than 40%", summary(vals)["warning"])


class EngineCli(unittest.TestCase):
    """Behaviour the agent relies on, independent of the workbook."""

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_selftest(self):
        self.assertTrue(run("selftest")["ok"])

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_unstated_drivers_are_reported_not_invented(self):
        out = analysed()
        not_stated = {d["driver"] for d in out["notStated"]}
        self.assertIn("headcount", not_stated)
        src = {d["key"]: d["source"] for d in out["report"]["drivers"]}
        self.assertEqual(src["headcount"], "default assumed")
        self.assertEqual(src["sessionSize"], "read from RFP")

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_client_terms_and_options_carried(self):
        out = analysed()
        sig = {s["catalogueId"]: s for s in out["signalled"]}
        self.assertEqual(sig["sustenance_plan"]["clientTerm"].lower(), "change sustenance plan")
        self.assertTrue(sig["sustenance_plan"]["optional"])

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_state_round_trips_to_the_same_total(self):
        out = analysed()
        acc = run("accept", {"state": out["state"], "proposals": [
            {"op": "add_line", "target": "global", "value": {"name": "Gate packs", "qty": 2}, "rationale": "Gates"}]})
        again = run("estimate", {"state": json.loads(json.dumps(acc["state"]))})
        self.assertEqual(again["report"]["totals"]["ourMandays"], acc["report"]["totals"]["ourMandays"])

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_explain_gives_the_engines_own_working(self):
        out = analysed()
        ex = run("explain", {"state": out["state"], "ids": ["global:impact_assessment", "global:nope"]})
        self.assertTrue(ex["results"][0]["ok"])
        self.assertIn("library task", ex["results"][0]["working"])
        line = next(l for l in out["report"]["lines"] if l["id"] == "global:impact_assessment")
        self.assertTrue(ex["results"][0]["working"].endswith(f"= {line['mandays']} mandays"))
        self.assertFalse(ex["results"][1]["ok"])

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_unknown_command_fails_loudly(self):
        res = subprocess.run(["node", str(ENGINE), "price"], input="{}", capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("unknown command", res.stdout)


if __name__ == "__main__":
    unittest.main()
