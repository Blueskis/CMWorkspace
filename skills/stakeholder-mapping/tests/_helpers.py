"""Shared fixtures for the stakeholder-mapping tests."""

import copy
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

CONTEXT = {
    "client": "Northwind MRO",
    "programme": "S/4HANA Plant Maintenance rollout",
    "industry": "Aviation MRO",
    "business_model": "Line and base maintenance for regional carriers",
    "org_chart_units": ["Executive Committee", "Finance", "Plant Maintenance Planners"],
}


def base_extraction():
    return copy.deepcopy({
        "groups": [
            {"id": "G-EXEC", "name": "Executive Committee", "business_unit": "Corporate",
             "tier": 0, "headcount": 6, "sentiment": "Advocate", "influence": 5, "interest": 4,
             "summary": "Sponsors the programme.", "evidence": ["E1"]},
            {"id": "G-FIN", "name": "Finance", "business_unit": "Corporate",
             "tier": 2, "headcount": 20, "sentiment": "Neutral", "influence": 3, "interest": 3,
             "summary": "Owns cost centres and approvals.", "evidence": ["E1"]},
            {"id": "G-OPS", "name": "Plant Maintenance Planners", "business_unit": "Operations",
             "tier": 3, "headcount": 45, "sentiment": "Advocate", "influence": 3, "interest": 5,
             "summary": "Plan work orders for the hangars.", "evidence": ["E1", "E2"],
             "open_questions": ["Who covers planning during cutover?"]},
        ],
        "individuals": [
            {"id": "P-TAN", "group": "G-OPS", "name": "Tan, Ah Kow", "title": "Senior Planner",
             "sentiment": "Advocate", "influence": 4, "evidence": ["E2"]},
        ],
        "relationships": [
            {"id": "R1", "from": "G-OPS", "to": "G-EXEC", "kind": "formal", "type": "reports_to",
             "strength": 2, "confidence": "High", "evidence": ["E1"]},
            {"id": "R2", "from": "G-FIN", "to": "G-OPS", "kind": "formal", "type": "approves",
             "strength": 2, "confidence": "High", "evidence": ["E1"]},
            {"id": "R3", "from": "G-OPS", "to": "G-FIN", "kind": "informal", "type": "consults",
             "strength": 2, "confidence": "Medium", "evidence": ["E2"]},
        ],
        "evidence": [
            {"id": "E1", "source": "ORG-01", "quote": "Org chart v3.", "speaker": "",
             "attribution": "document"},
            {"id": "E2", "source": "INT-01",
             "quote": "Ah Kow said the planners check with Finance before anything big.",
             "speaker": "Planning Manager", "attribution": "testimony"},
        ],
    })


def chain_extraction(n=5, ona_middle=None):
    """n groups in a path G0-G1-...; the middle one has the highest betweenness."""
    groups, rels = [], []
    for i in range(n):
        groups.append({"id": f"G{i}", "name": f"Group {i}", "business_unit": "BU",
                       "tier": 2, "headcount": 10, "sentiment": "Neutral"})
        if i:
            rels.append({"id": f"R{i}", "from": f"G{i-1}", "to": f"G{i}", "kind": "formal",
                         "type": "hands_off_to", "strength": 1, "confidence": "Medium"})
    if ona_middle:
        groups[n // 2]["ona_role"] = ona_middle
    return {"groups": groups, "individuals": [], "relationships": rels, "evidence": []}
