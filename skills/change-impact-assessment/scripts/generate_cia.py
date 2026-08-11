#!/usr/bin/env python3
"""
Generate a baseline Change Impact Assessment workbook from a structured JSON input.

Usage:
    python3 generate_cia.py cia_input.json -o "Change Impact Assessment.xlsx"
    python3 generate_cia.py cia_input.json --validate-only

Input contract: see ../reference/input-schema.md
Rating model:   see ../reference/rating-methodology.md

The workbook is built to stay live: weighted scores, rating bands, training effort,
heatmap counts and the training/comms roll-ups are all Excel formulas, so a CM lead
can adjust a dimension score in a validation workshop and watch the whole pack move.
Roll-up sheets key off Impact ID via INDEX/MATCH, so re-sorting the register is safe.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# --------------------------------------------------------------------------------------
# Rating model — mirrored in reference/rating-methodology.md and on the Cover sheet
# --------------------------------------------------------------------------------------

WEIGHTS = {
    "score_people": ("People & Role", 0.30),
    "score_process": ("Process", 0.25),
    "score_technology": ("Technology", 0.20),
    "score_policy": ("Policy & Control", 0.15),
    "score_data": ("Data & Reporting", 0.10),
}

BANDS = [  # (lower bound inclusive, label)
    (3.75, "Critical"),
    (2.75, "High"),
    (1.75, "Medium"),
    (0.00, "Low"),
]

RATINGS = ["Low", "Medium", "High", "Critical"]

ENUMS = {
    "change_type": [
        "Process",
        "System / Technology",
        "Policy & Control",
        "Role & Organisation",
        "Data & Reporting",
        "Ways of Working",
    ],
    "change_nature": ["New", "Modified", "Eliminated", "Automated", "Reassigned"],
    "resistance_risk": ["Low", "Medium", "High"],
    "training_required": ["Yes", "No"],
    "comms_required": ["Yes", "No"],
    "training_type": [
        "Classroom ILT",
        "Virtual ILT",
        "e-Learning",
        "Job Aid",
        "In-App Guidance",
        "Floorwalking / Hypercare",
        "Webinar",
        "Not Required",
    ],
    "confidence": ["High", "Medium", "Low"],
    "validation_status": ["Draft", "In Review", "Validated", "Baselined"],
    "rating_override": RATINGS,
}

COMMS_WAVES = [
    ("Awareness", -12, -8, "Something is coming, and why"),
    ("Understanding", -8, -4, "What specifically changes for you"),
    ("Readiness", -4, -1, "What you must do, and when"),
    ("Go-Live", 0, 2, "Where to get help"),
    ("Reinforcement", 2, 12, "It's working, and it's permanent"),
]

# --------------------------------------------------------------------------------------
# Register column definition
# --------------------------------------------------------------------------------------
# kind: text | wrap | int | num | formula
COLUMNS = [
    # -- Identification
    ("impact_id", "Impact ID", 10, "text", "Identification"),
    ("workstream", "Workstream (L1)", 22, "text", "Identification"),
    ("process_group", "Process Group (L2)", 24, "text", "Identification"),
    ("process_name", "Process / Sub-Process (L3)", 30, "text", "Identification"),
    ("process_ref", "Process Model Ref", 16, "text", "Identification"),
    # -- As-Is to To-Be
    ("as_is_process", "As-Is Process", 52, "wrap", "As-Is → To-Be"),
    ("as_is_system", "As-Is System / Tool", 22, "wrap", "As-Is → To-Be"),
    ("to_be_process", "To-Be Process", 52, "wrap", "As-Is → To-Be"),
    ("to_be_system", "To-Be System / Solution", 24, "wrap", "As-Is → To-Be"),
    # -- Characterisation
    ("change_type", "Change Type", 20, "text", "Characterisation"),
    ("change_nature", "Nature of Change", 16, "text", "Characterisation"),
    # -- Who is impacted
    ("stakeholder_group", "Impacted Stakeholder Group", 28, "text", "Who Is Impacted"),
    ("impacted_roles", "Impacted Role(s) / Persona", 30, "wrap", "Who Is Impacted"),
    ("geography", "Geography / Entity", 18, "text", "Who Is Impacted"),
    ("headcount_impacted", "People Impacted (#)", 13, "int", "Who Is Impacted"),
    # -- Scoring
    ("score_people", "People & Role (1-5)", 11, "int", "Impact Rating"),
    ("score_process", "Process (1-5)", 11, "int", "Impact Rating"),
    ("score_technology", "Technology (1-5)", 11, "int", "Impact Rating"),
    ("score_policy", "Policy & Control (1-5)", 11, "int", "Impact Rating"),
    ("score_data", "Data & Reporting (1-5)", 11, "int", "Impact Rating"),
    ("weighted_score", "Weighted Score", 12, "formula", "Impact Rating"),
    ("impact_rating", "CHANGE IMPACT RATING", 18, "formula", "Impact Rating"),
    # -- Analysis
    ("impact_rationale", "Impact Rationale", 55, "wrap", "Impact Analysis"),
    ("resistance_risk", "Anticipated Resistance", 15, "text", "Impact Analysis"),
    ("benefit_narrative", "Benefit / What's In It For Me", 45, "wrap", "Impact Analysis"),
    # -- Training
    ("training_required", "Training Required", 12, "text", "Training Response"),
    ("training_type", "Delivery Method", 20, "text", "Training Response"),
    ("training_module_ref", "Module Ref", 14, "text", "Training Response"),
    ("training_duration_hrs", "Duration (hrs)", 12, "num", "Training Response"),
    ("training_audience_size", "Audience (#)", 12, "int", "Training Response"),
    ("training_effort_hrs", "Total Effort (person-hrs)", 15, "formula", "Training Response"),
    ("training_timing", "Training Timing", 18, "text", "Training Response"),
    # -- Comms
    ("comms_required", "Comms Required", 12, "text", "Communication Response"),
    ("key_message", "Key Message", 60, "wrap", "Communication Response"),
    ("comms_channel", "Channel(s)", 30, "wrap", "Communication Response"),
    ("comms_timing", "Comms Timing / Wave", 26, "text", "Communication Response"),
    ("comms_owner", "Comms Owner / Sender", 24, "wrap", "Communication Response"),
    # -- Ownership & mitigation
    ("change_champion", "Change Champion / Business Owner", 26, "wrap", "Ownership & Mitigation"),
    ("mitigation_actions", "Additional Mitigation Actions", 45, "wrap", "Ownership & Mitigation"),
    ("dependencies", "Dependencies / Linked Impacts", 24, "wrap", "Ownership & Mitigation"),
    # -- Governance
    ("source_ref", "Source Document Ref", 18, "text", "Governance & Traceability"),
    ("confidence", "Confidence", 11, "text", "Governance & Traceability"),
    ("validation_status", "Validation Status", 15, "text", "Governance & Traceability"),
    ("notes", "Notes / Open Questions", 45, "wrap", "Governance & Traceability"),
]

REQUIRED_IMPACT_FIELDS = [
    "impact_id", "workstream", "process_group", "process_name",
    "as_is_process", "to_be_process", "change_type", "change_nature",
    "stakeholder_group", "score_people", "score_process", "score_technology",
    "score_policy", "score_data", "impact_rationale", "resistance_risk",
    "training_required", "comms_required", "source_ref", "confidence",
]
REQUIRED_META_FIELDS = [
    "program_name", "client", "solution_scope", "assessment_owner",
    "version", "assessment_date", "source_documents",
]

SCORE_FIELDS = list(WEIGHTS.keys())

HEADER_ROW = 4
GROUP_ROW = 3
DATA_START = 5
BUFFER_ROWS = 50  # blank pre-formatted rows so the CM lead can add impacts in-workbook

# --------------------------------------------------------------------------------------
# Styling
# --------------------------------------------------------------------------------------

NAVY = "1F3864"
SLATE = "2E4057"
LIGHT = "F2F5F9"
BORDER_GREY = "BFBFBF"

GROUP_FILLS = {
    "Identification": "1F3864",
    "As-Is → To-Be": "2E5A88",
    "Characterisation": "3D6E4F",
    "Who Is Impacted": "6B4E71",
    "Impact Rating": "8C3A2E",
    "Impact Analysis": "A8632C",
    "Training Response": "1F6F6B",
    "Communication Response": "4A5899",
    "Ownership & Mitigation": "5A5A5A",
    "Governance & Traceability": "3A3A3A",
}

RATING_FILLS = {
    "Low": PatternFill("solid", fgColor="D7EAD3"),
    "Medium": PatternFill("solid", fgColor="FFF2CC"),
    "High": PatternFill("solid", fgColor="FBD9C4"),
    "Critical": PatternFill("solid", fgColor="F4C2C2"),
}
RATING_FONTS = {
    "Low": Font(color="2C5F2D", bold=True, size=10),
    "Medium": Font(color="7F6000", bold=True, size=10),
    "High": Font(color="9C4221", bold=True, size=10),
    "Critical": Font(color="912018", bold=True, size=10),
}

THIN = Side(style="thin", color=BORDER_GREY)
CELL_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def col_letter(key):
    for i, (k, *_rest) in enumerate(COLUMNS, start=1):
        if k == key:
            return get_column_letter(i)
    raise KeyError(key)


REG = "'Impact Register'"


def style_title(ws, row, text, span, size=15):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(bold=True, size=size, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[row].height = 26 if size >= 14 else 20


def section_header(ws, row, text, span, fill=SLATE):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(bold=True, size=11, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=fill)
    c.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[row].height = 20


def table_header(ws, row, headers, widths=None):
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = Font(bold=True, size=10, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=SLATE)
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        c.border = CELL_BORDER
        if widths:
            ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
    ws.row_dimensions[row].height = 30


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------

def validate(data):
    errors, warnings = [], []

    meta = data.get("meta")
    if not isinstance(meta, dict):
        return ["`meta` object is missing."], []

    for f in REQUIRED_META_FIELDS:
        if not meta.get(f):
            errors.append(f"meta.{f} is required but missing or empty.")

    docs = meta.get("source_documents") or []
    known_refs = set()
    for i, d in enumerate(docs):
        ref = (d or {}).get("ref")
        if not ref:
            errors.append(f"meta.source_documents[{i}] has no `ref`.")
        else:
            if ref in known_refs:
                errors.append(f"Duplicate source document ref '{ref}'.")
            known_refs.add(ref)

    impacts = data.get("impacts")
    if not isinstance(impacts, list) or not impacts:
        errors.append("`impacts` must be a non-empty array.")
        return errors, warnings

    seen_ids = set()
    cited_refs = set()
    ws_ratings = defaultdict(list)

    for idx, imp in enumerate(impacts):
        tag = imp.get("impact_id") or f"impacts[{idx}]"

        for f in REQUIRED_IMPACT_FIELDS:
            val = imp.get(f)
            if val is None or (isinstance(val, str) and not val.strip()):
                errors.append(f"{tag}: required field `{f}` is missing or empty.")

        iid = imp.get("impact_id")
        if iid:
            if iid in seen_ids:
                errors.append(f"Duplicate impact_id '{iid}'.")
            seen_ids.add(iid)

        for f in SCORE_FIELDS:
            v = imp.get(f)
            if v is None:
                continue
            if isinstance(v, bool) or not isinstance(v, int):
                errors.append(f"{tag}: `{f}` must be an integer 1-5, got {v!r}.")
            elif not 1 <= v <= 5:
                errors.append(f"{tag}: `{f}` must be between 1 and 5, got {v}.")

        for f, allowed in ENUMS.items():
            v = imp.get(f)
            if v and v not in allowed:
                errors.append(
                    f"{tag}: `{f}` = {v!r} is not one of: {', '.join(allowed)}."
                )

        if imp.get("rating_override") and not (imp.get("rating_override_reason") or "").strip():
            errors.append(f"{tag}: `rating_override` is set but `rating_override_reason` is empty.")

        for ref in split_refs(imp.get("source_ref")):
            cited_refs.add(ref)
            if known_refs and ref not in known_refs:
                errors.append(
                    f"{tag}: source_ref '{ref}' is not declared in meta.source_documents."
                )

        # ---- warnings
        rating = computed_rating(imp)
        if imp.get("workstream"):
            ws_ratings[imp["workstream"]].append(rating)

        if imp.get("confidence") == "Low" and not (imp.get("notes") or "").strip():
            warnings.append(f"{tag}: Low confidence with no open question recorded in `notes`.")
        if imp.get("resistance_risk") == "High" and not (imp.get("mitigation_actions") or "").strip():
            warnings.append(f"{tag}: High anticipated resistance with no `mitigation_actions`.")
        if rating in ("High", "Critical") and not (imp.get("change_champion") or "").strip():
            warnings.append(f"{tag}: rated {rating} with no `change_champion` named.")
        if rating in ("High", "Critical") and not (imp.get("comms_owner") or "").strip():
            warnings.append(f"{tag}: rated {rating} with no `comms_owner` named.")
        if imp.get("training_required") == "Yes" and not imp.get("training_type"):
            warnings.append(f"{tag}: training required but no `training_type` set.")
        if imp.get("training_required") == "Yes" and not imp.get("training_duration_hrs"):
            warnings.append(f"{tag}: training required but no `training_duration_hrs` — effort cannot be rolled up.")
        if imp.get("comms_required") == "Yes" and not (imp.get("key_message") or "").strip():
            warnings.append(f"{tag}: comms required but no `key_message` drafted.")
        if rating in ("High", "Critical") and imp.get("training_required") == "No":
            warnings.append(f"{tag}: rated {rating} but no training planned — check the rating or the response.")

    for w, ratings in ws_ratings.items():
        if not any(r in ("High", "Critical") for r in ratings):
            warnings.append(
                f"Workstream '{w}' has no High or Critical impacts — confirm this is real, not under-assessed."
            )

    uncited = known_refs - cited_refs
    for ref in sorted(uncited):
        warnings.append(f"Source document '{ref}' is not cited by any impact — was it read?")

    return errors, warnings


def split_refs(value):
    if not value:
        return []
    parts = str(value).replace(",", ";").split(";")
    return [p.strip() for p in parts if p.strip()]


def weighted_score(imp):
    try:
        return round(sum(imp[f] * w for f, (_lbl, w) in WEIGHTS.items()), 2)
    except (KeyError, TypeError):
        return None


def computed_rating(imp):
    """Python-side mirror of the workbook formula, used for stats and warnings."""
    if imp.get("rating_override"):
        return imp["rating_override"]
    s = weighted_score(imp)
    if s is None:
        return None
    for lower, label in BANDS:
        if s >= lower:
            return label
    return "Low"


# --------------------------------------------------------------------------------------
# Sheet: Reference (dropdown source lists)
# --------------------------------------------------------------------------------------

REF_LISTS = [
    ("change_type", "Change Type", ENUMS["change_type"]),
    ("change_nature", "Nature of Change", ENUMS["change_nature"]),
    ("score", "Impact Score", ["1", "2", "3", "4", "5"]),
    ("rating", "Impact Rating", RATINGS),
    ("resistance", "Resistance", ENUMS["resistance_risk"]),
    ("training_type", "Delivery Method", ENUMS["training_type"]),
    ("yesno", "Yes / No", ["Yes", "No"]),
    ("confidence", "Confidence", ENUMS["confidence"]),
    ("status", "Validation Status", ENUMS["validation_status"]),
]


def build_reference(wb):
    ws = wb.create_sheet("Reference")
    style_title(ws, 1, "Reference Lists  —  source data for the register's dropdowns", len(REF_LISTS), size=12)
    ranges = {}
    for i, (key, label, values) in enumerate(REF_LISTS, start=1):
        letter = get_column_letter(i)
        ws.column_dimensions[letter].width = max(len(label) + 4, 18)
        c = ws.cell(row=2, column=i, value=label)
        c.font = Font(bold=True, size=10, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=SLATE)
        c.alignment = Alignment(horizontal="center")
        for j, v in enumerate(values):
            cell = ws.cell(row=3 + j, column=i, value=v)
            cell.font = Font(size=10)
            cell.alignment = Alignment(horizontal="center")
        ranges[key] = f"Reference!${letter}$3:${letter}${2 + len(values)}"
    ws.sheet_state = "visible"
    return ranges


# --------------------------------------------------------------------------------------
# Sheet: Impact Register
# --------------------------------------------------------------------------------------

def build_register(wb, data, ref_ranges):
    ws = wb.create_sheet("Impact Register")
    meta = data["meta"]
    impacts = data["impacts"]
    n = len(impacts)
    last_data = DATA_START + n - 1
    last_live = last_data + BUFFER_ROWS  # formulas + validation extend into blank rows

    ncols = len(COLUMNS)
    style_title(ws, 1, f"CHANGE IMPACT ASSESSMENT  —  {meta['program_name']}", ncols)
    sub = ws.cell(
        row=2, column=1,
        value=(f"{meta['client']}   |   {meta['version']}   |   Assessment date: {meta['assessment_date']}"
               f"   |   Owner: {meta['assessment_owner']}   |   {n} impacts"),
    )
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    sub.font = Font(size=10, italic=True, color=SLATE)
    sub.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[2].height = 18

    # -- group band
    start = 1
    while start <= ncols:
        group = COLUMNS[start - 1][4]
        end = start
        while end < ncols and COLUMNS[end][4] == group:
            end += 1
        ws.merge_cells(start_row=GROUP_ROW, start_column=start, end_row=GROUP_ROW, end_column=end)
        c = ws.cell(row=GROUP_ROW, column=start, value=group.upper())
        c.font = Font(bold=True, size=9, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=GROUP_FILLS[group])
        c.alignment = Alignment(horizontal="center", vertical="center")
        start = end + 1
    ws.row_dimensions[GROUP_ROW].height = 18

    # -- headers
    for i, (key, header, width, kind, group) in enumerate(COLUMNS, start=1):
        c = ws.cell(row=HEADER_ROW, column=i, value=header)
        c.font = Font(bold=True, size=10, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=SLATE)
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        c.border = CELL_BORDER
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.row_dimensions[HEADER_ROW].height = 42

    # -- data
    for r, imp in enumerate(impacts, start=DATA_START):
        for i, (key, header, width, kind, group) in enumerate(COLUMNS, start=1):
            cell = ws.cell(row=r, column=i)
            cell.border = CELL_BORDER
            cell.font = Font(size=10)
            if kind == "formula":
                continue  # written below, for data + buffer rows alike
            value = imp.get(key)
            if key == "training_audience_size" and value in (None, ""):
                value = imp.get("headcount_impacted")
            if key == "validation_status" and not value:
                value = "Draft"
            if key == "notes" and imp.get("rating_override"):
                override_note = (
                    f"RATING OVERRIDE → {imp['rating_override']}: {imp.get('rating_override_reason','')}"
                )
                value = f"{override_note}  |  {value}" if value else override_note
            cell.value = value
            if kind == "wrap":
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            elif kind in ("int", "num"):
                cell.alignment = Alignment(horizontal="center", vertical="top")
                cell.number_format = "#,##0" if kind == "int" else "0.0"
            else:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[r].height = 58

    # -- formulas + formatting across data and buffer rows
    p, q, rr, s, t = (col_letter(f) for f in SCORE_FIELDS)
    wsc = col_letter("weighted_score")
    rat = col_letter("impact_rating")
    dur = col_letter("training_duration_hrs")
    aud = col_letter("training_audience_size")
    eff = col_letter("training_effort_hrs")

    overrides = {DATA_START + i: imp.get("rating_override")
                 for i, imp in enumerate(impacts) if imp.get("rating_override")}

    for r in range(DATA_START, last_live + 1):
        ws[f"{wsc}{r}"] = (
            f"=IF(COUNT({p}{r}:{t}{r})<5,\"\","
            f"ROUND({p}{r}*{WEIGHTS['score_people'][1]}+{q}{r}*{WEIGHTS['score_process'][1]}"
            f"+{rr}{r}*{WEIGHTS['score_technology'][1]}+{s}{r}*{WEIGHTS['score_policy'][1]}"
            f"+{t}{r}*{WEIGHTS['score_data'][1]},2))"
        )
        ws[f"{wsc}{r}"].number_format = "0.00"
        ws[f"{wsc}{r}"].alignment = Alignment(horizontal="center", vertical="center")
        ws[f"{wsc}{r}"].font = Font(size=10, bold=True)

        if r in overrides:
            ws[f"{rat}{r}"] = overrides[r]
        else:
            ws[f"{rat}{r}"] = (
                f"=IF({wsc}{r}=\"\",\"\","
                f"IF({wsc}{r}>={BANDS[0][0]},\"{BANDS[0][1]}\","
                f"IF({wsc}{r}>={BANDS[1][0]},\"{BANDS[1][1]}\","
                f"IF({wsc}{r}>={BANDS[2][0]},\"{BANDS[2][1]}\",\"{BANDS[3][1]}\"))))"
            )
        ws[f"{rat}{r}"].alignment = Alignment(horizontal="center", vertical="center")
        ws[f"{rat}{r}"].font = Font(size=10, bold=True)

        ws[f"{eff}{r}"] = f"=IF(OR({dur}{r}=\"\",{aud}{r}=\"\"),\"\",{dur}{r}*{aud}{r})"
        ws[f"{eff}{r}"].number_format = "#,##0"
        ws[f"{eff}{r}"].alignment = Alignment(horizontal="center", vertical="center")

        for i in range(1, ncols + 1):
            c = ws.cell(row=r, column=i)
            c.border = CELL_BORDER
            if r > last_data:
                c.font = Font(size=10)
                if COLUMNS[i - 1][3] == "wrap":
                    c.alignment = Alignment(wrap_text=True, vertical="top")

    # zebra striping on populated rows
    stripe = PatternFill("solid", fgColor=LIGHT)
    for r in range(DATA_START, last_data + 1, 2):
        for i in range(1, ncols + 1):
            if get_column_letter(i) != rat:
                ws.cell(row=r, column=i).fill = stripe

    # -- conditional formatting on the rating column
    rng = f"{rat}{DATA_START}:{rat}{last_live}"
    for label in RATINGS:
        ws.conditional_formatting.add(
            rng,
            CellIsRule(operator="equal", formula=[f'"{label}"'],
                       fill=RATING_FILLS[label], font=RATING_FONTS[label]),
        )
    # resistance column gets the same treatment
    res = col_letter("resistance_risk")
    for label, fill_key in (("High", "Critical"), ("Medium", "Medium"), ("Low", "Low")):
        ws.conditional_formatting.add(
            f"{res}{DATA_START}:{res}{last_live}",
            CellIsRule(operator="equal", formula=[f'"{label}"'],
                       fill=RATING_FILLS[fill_key], font=RATING_FONTS[fill_key]),
        )
    # low confidence stands out — these are the validation-workshop rows
    conf = col_letter("confidence")
    ws.conditional_formatting.add(
        f"{conf}{DATA_START}:{conf}{last_live}",
        CellIsRule(operator="equal", formula=['"Low"'],
                   fill=RATING_FILLS["Critical"], font=RATING_FONTS["Critical"]),
    )

    # -- dropdowns
    dv_map = {
        "change_type": "change_type",
        "change_nature": "change_nature",
        "resistance_risk": "resistance",
        "training_type": "training_type",
        "training_required": "yesno",
        "comms_required": "yesno",
        "confidence": "confidence",
        "validation_status": "status",
        **{f: "score" for f in SCORE_FIELDS},
    }
    for field, ref_key in dv_map.items():
        dv = DataValidation(type="list", formula1=f"={ref_ranges[ref_key]}", allow_blank=True)
        dv.error = "Pick a value from the list — see the Reference sheet."
        dv.errorTitle = "Value not allowed"
        ws.add_data_validation(dv)
        letter = col_letter(field)
        dv.add(f"{letter}{DATA_START}:{letter}{last_live}")

    ws.freeze_panes = f"F{DATA_START}"
    ws.auto_filter.ref = f"A{HEADER_ROW}:{get_column_letter(ncols)}{last_live}"
    ws.sheet_view.zoomScale = 85
    ws.sheet_properties.tabColor = NAVY
    ws.print_title_rows = f"{GROUP_ROW}:{HEADER_ROW}"
    return last_data, last_live


# --------------------------------------------------------------------------------------
# Sheet: Cover
# --------------------------------------------------------------------------------------

def build_cover(wb, data, stats):
    ws = wb.create_sheet("Cover")
    meta = data["meta"]
    widths = [34, 30, 26, 26, 26, 26, 22]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    span = len(widths)

    style_title(ws, 1, "BASELINE CHANGE IMPACT ASSESSMENT", span, size=16)
    c = ws.cell(row=2, column=1, value=meta["program_name"])
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
    c.font = Font(size=12, bold=True, color=SLATE)
    c.alignment = Alignment(indent=1)
    ws.row_dimensions[2].height = 22

    row = 4
    section_header(ws, row, "ASSESSMENT DETAILS", span)
    row += 1
    details = [
        ("Client", meta["client"]),
        ("Solution scope", meta["solution_scope"]),
        ("Assessment owner", meta["assessment_owner"]),
        ("Version", meta["version"]),
        ("Assessment date", meta["assessment_date"]),
        ("Target go-live", meta.get("go_live_date", "Not stated")),
        ("Total impacts assessed", stats["total"]),
    ]
    for label, value in details:
        lc = ws.cell(row=row, column=1, value=label)
        lc.font = Font(bold=True, size=10)
        lc.fill = PatternFill("solid", fgColor=LIGHT)
        lc.border = CELL_BORDER
        vc = ws.cell(row=row, column=2, value=value)
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=span)
        vc.font = Font(size=10)
        vc.alignment = Alignment(vertical="center", wrap_text=True, indent=1)
        vc.border = CELL_BORDER
        row += 1

    row += 1
    section_header(ws, row, "IMPACT PROFILE", span)
    row += 1
    table_header(ws, row, ["Rating", "Impacts", "% of total", "People impacted",
                           "Training effort (person-hrs)", "Training effort (days)", ""])
    row += 1
    profile_start = row
    for label in RATINGS:
        d = stats["by_rating"][label]
        vals = [label, d["count"],
                (d["count"] / stats["total"]) if stats["total"] else 0,
                d["people"], d["effort"], round(d["effort"] / 7.5, 1), ""]
        for i, v in enumerate(vals, start=1):
            cell = ws.cell(row=row, column=i, value=v)
            cell.border = CELL_BORDER
            cell.font = Font(size=10)
            cell.alignment = Alignment(horizontal="center" if i > 1 else "left", indent=0 if i > 1 else 1)
            if i == 3:
                cell.number_format = "0%"
            elif i in (2, 4, 5):
                cell.number_format = "#,##0"
            elif i == 6:
                cell.number_format = "#,##0.0"
        ws.cell(row=row, column=1).fill = RATING_FILLS[label]
        ws.cell(row=row, column=1).font = RATING_FONTS[label]
        row += 1
    total_vals = ["TOTAL", stats["total"], 1.0, stats["people_total"],
                  stats["effort_total"], round(stats["effort_total"] / 7.5, 1), ""]
    for i, v in enumerate(total_vals, start=1):
        cell = ws.cell(row=row, column=i, value=v)
        cell.border = CELL_BORDER
        cell.font = Font(size=10, bold=True)
        cell.fill = PatternFill("solid", fgColor=LIGHT)
        cell.alignment = Alignment(horizontal="center" if i > 1 else "left", indent=0 if i > 1 else 1)
        if i == 3:
            cell.number_format = "0%"
        elif i in (2, 4, 5):
            cell.number_format = "#,##0"
        elif i == 6:
            cell.number_format = "#,##0.0"
    row += 2
    note = ws.cell(row=row, column=1, value=(
        "Person-hours converted to days at 7.5 productive hours per day. "
        "'People impacted' sums the headcount on each impact row, so a person affected by several "
        "impacts is counted more than once — read it as touchpoints, not unique headcount."))
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    note.font = Font(size=9, italic=True, color="666666")
    note.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    ws.row_dimensions[row].height = 28
    row += 2

    section_header(ws, row, "RATING METHODOLOGY", span)
    row += 1
    ws.cell(row=row, column=1, value=(
        "Each impact is scored 1-5 on five dimensions. The weighted score drives the rating band. "
        "Scores and ratings in the register are live formulas — change a dimension score in a "
        "validation workshop and the rating, heatmap and roll-ups all update.")).font = Font(size=10)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top", indent=1)
    ws.row_dimensions[row].height = 30
    row += 2

    table_header(ws, row, ["Dimension", "Weight", "What it measures", "", "", "", ""])
    row += 1
    dim_desc = {
        "score_people": "How much the job itself changes — tasks, decision rights, accountability, headcount",
        "score_process": "How much the flow, sequence, hand-offs or cycle time change",
        "score_technology": "How much the system the user touches changes",
        "score_policy": "How much the governing rules change — approvals, controls, compliance",
        "score_data": "How much the data the user creates, owns or consumes changes",
    }
    for f, (label, weight) in WEIGHTS.items():
        ws.cell(row=row, column=1, value=label).font = Font(size=10, bold=True)
        wc = ws.cell(row=row, column=2, value=weight)
        wc.number_format = "0%"
        wc.alignment = Alignment(horizontal="center")
        ws.cell(row=row, column=3, value=dim_desc[f]).font = Font(size=10)
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=span)
        ws.cell(row=row, column=3).alignment = Alignment(wrap_text=True, vertical="center", indent=1)
        for i in range(1, span + 1):
            ws.cell(row=row, column=i).border = CELL_BORDER
        ws.row_dimensions[row].height = 18
        row += 1
    row += 1

    table_header(ws, row, ["Weighted score", "Rating", "Response tier", "", "", "", ""])
    row += 1
    band_response = {
        "Low": "Awareness comms only. No dedicated training.",
        "Medium": "Job aid or e-learning, self-paced. Standard comms cadence.",
        "High": "ILT/VILT with hands-on practice. Sustained comms with a named business sponsor.",
        "Critical": "Full curriculum plus go-live hypercare. Sponsor-led, two-way engagement and an explicit resistance plan.",
    }
    band_ranges = ["1.00 – 1.74", "1.75 – 2.74", "2.75 – 3.74", "3.75 – 5.00"]
    for label, rng in zip(RATINGS, band_ranges):
        ws.cell(row=row, column=1, value=rng).font = Font(size=10)
        ws.cell(row=row, column=1).alignment = Alignment(horizontal="center")
        rc = ws.cell(row=row, column=2, value=label)
        rc.fill = RATING_FILLS[label]
        rc.font = RATING_FONTS[label]
        rc.alignment = Alignment(horizontal="center")
        ws.cell(row=row, column=3, value=band_response[label]).font = Font(size=10)
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=span)
        ws.cell(row=row, column=3).alignment = Alignment(wrap_text=True, vertical="center", indent=1)
        for i in range(1, span + 1):
            ws.cell(row=row, column=i).border = CELL_BORDER
        ws.row_dimensions[row].height = 20
        row += 1
    row += 2

    # -- comms wave calendar
    go_live = parse_date(meta.get("go_live_date"))
    section_header(ws, row, "COMMUNICATION WAVES", span)
    row += 1
    table_header(ws, row, ["Wave", "Window", "Dates", "Purpose", "", "", ""])
    row += 1
    for name, start_wk, end_wk, purpose in COMMS_WAVES:
        ws.cell(row=row, column=1, value=name).font = Font(size=10, bold=True)
        ws.cell(row=row, column=2, value=f"T{start_wk:+d} to T{end_wk:+d} weeks").font = Font(size=10)
        ws.cell(row=row, column=2).alignment = Alignment(horizontal="center")
        if go_live:
            d1 = go_live + timedelta(weeks=start_wk)
            d2 = go_live + timedelta(weeks=end_wk)
            dates = f"{d1:%d %b %Y} – {d2:%d %b %Y}"
        else:
            dates = "Set meta.go_live_date to calculate"
        ws.cell(row=row, column=3, value=dates).font = Font(size=10)
        ws.cell(row=row, column=3).alignment = Alignment(horizontal="center")
        ws.cell(row=row, column=4, value=purpose).font = Font(size=10)
        ws.merge_cells(start_row=row, start_column=4, end_row=row, end_column=span)
        ws.cell(row=row, column=4).alignment = Alignment(wrap_text=True, vertical="center", indent=1)
        for i in range(1, span + 1):
            ws.cell(row=row, column=i).border = CELL_BORDER
        ws.row_dimensions[row].height = 18
        row += 1
    row += 2

    section_header(ws, row, "HOW TO USE THIS PACK", span)
    row += 1
    usage = [
        "Impact Register — the baseline. One row per process change × stakeholder group. "
        "Filter by workstream, group or rating; adjust dimension scores in validation workshops and "
        "the rating recalculates. Fifty blank pre-formatted rows sit under the data for new impacts.",
        "Impact Heatmap — where the change lands, by stakeholder group and by workstream. "
        "All counts are live formulas over the register.",
        "Training Plan — every impact needing training, with effort roll-ups by delivery method and "
        "by audience. Use this to size the training budget and check no group has an impossible week.",
        "Comms Plan — key messages by audience and wave, with named senders.",
        "Traceability — the source documents behind the baseline, and how many impacts each supports. "
        "This is what turns a challenge in a validation workshop into a document review.",
        "THIS IS A BASELINE, NOT A CONCLUSION. Rows marked Low confidence are inferred and carry an open "
        "question in the Notes column — work those first with the business before baselining.",
    ]
    for u in usage:
        cell = ws.cell(row=row, column=1, value="•  " + u)
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
        cell.font = Font(size=10, bold=u.startswith("THIS IS A BASELINE"))
        cell.alignment = Alignment(wrap_text=True, vertical="top", indent=1)
        ws.row_dimensions[row].height = 30
        row += 1

    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = NAVY
    return ws


def parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------------------
# Sheet: Impact Heatmap
# --------------------------------------------------------------------------------------

def build_heatmap(wb, data, last_live):
    ws = wb.create_sheet("Impact Heatmap")
    impacts = data["impacts"]
    groups = sorted({i["stakeholder_group"] for i in impacts})
    workstreams = sorted({i["workstream"] for i in impacts})

    widths = [38, 12, 12, 12, 12, 14, 18, 20]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    span = len(widths)

    grp_col = f"{REG}!${col_letter('stakeholder_group')}${DATA_START}:${col_letter('stakeholder_group')}${last_live}"
    ws_col = f"{REG}!${col_letter('workstream')}${DATA_START}:${col_letter('workstream')}${last_live}"
    rat_col = f"{REG}!${col_letter('impact_rating')}${DATA_START}:${col_letter('impact_rating')}${last_live}"
    hc_col = f"{REG}!${col_letter('headcount_impacted')}${DATA_START}:${col_letter('headcount_impacted')}${last_live}"
    eff_col = f"{REG}!${col_letter('training_effort_hrs')}${DATA_START}:${col_letter('training_effort_hrs')}${last_live}"
    res_col = f"{REG}!${col_letter('resistance_risk')}${DATA_START}:${col_letter('resistance_risk')}${last_live}"

    style_title(ws, 1, "IMPACT HEATMAP  —  where the change actually lands", span, size=14)
    ws.cell(row=2, column=1, value=(
        "Every figure below is a live formula over the Impact Register. Re-score an impact there and "
        "this view updates.")).font = Font(size=9, italic=True, color="666666")
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)

    row = 4

    def matrix(title, keys, key_range, extra_cols=True):
        nonlocal row
        section_header(ws, row, title, span)
        row += 1
        headers = ["", "Low", "Medium", "High", "Critical", "Total", "People impacted",
                   "High-resistance impacts"]
        table_header(ws, row, headers, widths)
        header_row = row
        row += 1
        first = row
        for key in keys:
            kc = ws.cell(row=row, column=1, value=key)
            kc.font = Font(size=10, bold=True)
            kc.alignment = Alignment(vertical="center", wrap_text=True, indent=1)
            kc.border = CELL_BORDER
            for ci, label in enumerate(RATINGS, start=2):
                c = ws.cell(
                    row=row, column=ci,
                    value=f'=COUNTIFS({key_range},$A{row},{rat_col},{get_column_letter(ci)}${header_row})',
                )
                c.number_format = "#,##0;;–"
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.font = Font(size=10)
                c.border = CELL_BORDER
            tot = ws.cell(row=row, column=6, value=f"=SUM(B{row}:E{row})")
            tot.font = Font(size=10, bold=True)
            tot.alignment = Alignment(horizontal="center", vertical="center")
            tot.border = CELL_BORDER
            tot.number_format = "#,##0"
            ppl = ws.cell(row=row, column=7, value=f"=SUMIFS({hc_col},{key_range},$A{row})")
            ppl.number_format = "#,##0;;–"
            ppl.alignment = Alignment(horizontal="center", vertical="center")
            ppl.font = Font(size=10)
            ppl.border = CELL_BORDER
            res = ws.cell(row=row, column=8,
                          value=f'=COUNTIFS({key_range},$A{row},{res_col},"High")')
            res.number_format = "#,##0;;–"
            res.alignment = Alignment(horizontal="center", vertical="center")
            res.font = Font(size=10)
            res.border = CELL_BORDER
            ws.row_dimensions[row].height = 20
            row += 1
        # totals
        tc = ws.cell(row=row, column=1, value="TOTAL")
        tc.font = Font(size=10, bold=True)
        tc.fill = PatternFill("solid", fgColor=LIGHT)
        tc.border = CELL_BORDER
        tc.alignment = Alignment(indent=1)
        for ci in range(2, span + 1):
            L = get_column_letter(ci)
            c = ws.cell(row=row, column=ci, value=f"=SUM({L}{first}:{L}{row - 1})")
            c.font = Font(size=10, bold=True)
            c.fill = PatternFill("solid", fgColor=LIGHT)
            c.alignment = Alignment(horizontal="center")
            c.number_format = "#,##0"
            c.border = CELL_BORDER
        # colour the count cells by severity
        for ci, label in enumerate(RATINGS, start=2):
            L = get_column_letter(ci)
            ws.conditional_formatting.add(
                f"{L}{first}:{L}{row - 1}",
                CellIsRule(operator="greaterThan", formula=["0"],
                           fill=RATING_FILLS[label], font=RATING_FONTS[label]),
            )
        ws.conditional_formatting.add(
            f"H{first}:H{row - 1}",
            CellIsRule(operator="greaterThan", formula=["0"],
                       fill=RATING_FILLS["Critical"], font=RATING_FONTS["Critical"]),
        )
        row += 2

    matrix("BY STAKEHOLDER GROUP", groups, grp_col)
    matrix("BY WORKSTREAM", workstreams, ws_col)

    # -- training load by group, the "impossible week" check
    section_header(ws, row, "TRAINING LOAD BY STAKEHOLDER GROUP", span)
    row += 1
    table_header(ws, row, ["Stakeholder group", "Impacts needing training", "Total effort (person-hrs)",
                           "Effort (days)", "", "", "", ""], widths)
    row += 1
    first = row
    trn_col = f"{REG}!${col_letter('training_required')}${DATA_START}:${col_letter('training_required')}${last_live}"
    for g in groups:
        ws.cell(row=row, column=1, value=g).font = Font(size=10, bold=True)
        ws.cell(row=row, column=1).alignment = Alignment(vertical="center", wrap_text=True, indent=1)
        ws.cell(row=row, column=2, value=f'=COUNTIFS({grp_col},$A{row},{trn_col},"Yes")')
        ws.cell(row=row, column=3, value=f'=SUMIFS({eff_col},{grp_col},$A{row})')
        ws.cell(row=row, column=4, value=f"=IF(C{row}=0,0,ROUND(C{row}/7.5,1))")
        for i in range(1, 5):
            c = ws.cell(row=row, column=i)
            c.border = CELL_BORDER
            if i > 1:
                c.font = Font(size=10)
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.number_format = "#,##0" if i < 4 else "#,##0.0"
        ws.row_dimensions[row].height = 20
        row += 1
    ws.cell(row=row, column=1, value="TOTAL").font = Font(size=10, bold=True)
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=LIGHT)
    ws.cell(row=row, column=1).alignment = Alignment(indent=1)
    for i in range(2, 5):
        L = get_column_letter(i)
        c = ws.cell(row=row, column=i, value=f"=SUM({L}{first}:{L}{row - 1})")
        c.font = Font(size=10, bold=True)
        c.fill = PatternFill("solid", fgColor=LIGHT)
        c.alignment = Alignment(horizontal="center")
        c.number_format = "#,##0" if i < 4 else "#,##0.0"
    for i in range(1, 5):
        ws.cell(row=row, column=i).border = CELL_BORDER

    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "8C3A2E"


# --------------------------------------------------------------------------------------
# Roll-up sheets (Training Plan / Comms Plan) — INDEX/MATCH keyed on Impact ID
# --------------------------------------------------------------------------------------

def lookup(field, id_cell, last_live):
    src = f"{REG}!${col_letter(field)}${DATA_START}:${col_letter(field)}${last_live}"
    ids = f"{REG}!${col_letter('impact_id')}${DATA_START}:${col_letter('impact_id')}${last_live}"
    return f'=IFERROR(INDEX({src},MATCH({id_cell},{ids},0)),"")'


def build_rollup(wb, data, last_live, *, sheet_name, title, blurb, filter_field,
                 fields, widths, tab_color, summary=None):
    ws = wb.create_sheet(sheet_name)
    impacts = [i for i in data["impacts"] if i.get(filter_field) == "Yes"]
    span = len(widths)
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    style_title(ws, 1, title, span, size=14)
    note = ws.cell(row=2, column=1, value=blurb)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
    note.font = Font(size=9, italic=True, color="666666")
    note.alignment = Alignment(wrap_text=True, vertical="center", indent=1)

    row = 4
    if summary:
        row = summary(ws, row, span, last_live)
        row += 1

    section_header(ws, row, f"DETAIL — {len(impacts)} impacts", span)
    row += 1
    table_header(ws, row, [h for _f, h in fields], widths)
    row += 1
    first = row
    for imp in impacts:
        ws.cell(row=row, column=1, value=imp["impact_id"]).font = Font(size=10, bold=True)
        for ci, (field, _h) in enumerate(fields[1:], start=2):
            c = ws.cell(row=row, column=ci, value=lookup(field, f"$A{row}", last_live))
            c.font = Font(size=10)
            if field in ("training_duration_hrs", "training_audience_size", "training_effort_hrs"):
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.number_format = "#,##0.0" if field == "training_duration_hrs" else "#,##0"
            elif field == "impact_rating":
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.font = Font(size=10, bold=True)
            else:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        for i in range(1, span + 1):
            ws.cell(row=row, column=i).border = CELL_BORDER
        ws.row_dimensions[row].height = 46
        row += 1

    rating_idx = next((i for i, (f, _h) in enumerate(fields, start=1) if f == "impact_rating"), None)
    if rating_idx and row > first:
        L = get_column_letter(rating_idx)
        for label in RATINGS:
            ws.conditional_formatting.add(
                f"{L}{first}:{L}{row - 1}",
                CellIsRule(operator="equal", formula=[f'"{label}"'],
                           fill=RATING_FILLS[label], font=RATING_FONTS[label]),
            )

    ws.freeze_panes = f"A{first}"
    ws.auto_filter.ref = f"A{first - 1}:{get_column_letter(span)}{max(row - 1, first)}"
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = tab_color


def training_summary(data, last_live):
    def _summary(ws, row, span, _ll):
        eff = f"{REG}!${col_letter('training_effort_hrs')}${DATA_START}:${col_letter('training_effort_hrs')}${last_live}"
        typ = f"{REG}!${col_letter('training_type')}${DATA_START}:${col_letter('training_type')}${last_live}"
        section_header(ws, row, "EFFORT BY DELIVERY METHOD", span)
        row += 1
        table_header(ws, row, ["Delivery method", "Impacts", "Total effort (person-hrs)",
                               "Effort (days)"] + [""] * (span - 4),
                     ws_widths(ws, span))
        row += 1
        first = row
        for method in ENUMS["training_type"]:
            if method == "Not Required":
                continue
            ws.cell(row=row, column=1, value=method).font = Font(size=10, bold=True)
            ws.cell(row=row, column=1).alignment = Alignment(vertical="center", indent=1)
            ws.cell(row=row, column=2, value=f'=COUNTIF({typ},$A{row})')
            ws.cell(row=row, column=3, value=f'=SUMIF({typ},$A{row},{eff})')
            ws.cell(row=row, column=4, value=f"=IF(C{row}=0,0,ROUND(C{row}/7.5,1))")
            for i in range(1, 5):
                c = ws.cell(row=row, column=i)
                c.border = CELL_BORDER
                if i > 1:
                    c.font = Font(size=10)
                    c.alignment = Alignment(horizontal="center", vertical="center")
                    c.number_format = "#,##0" if i < 4 else "#,##0.0"
            ws.row_dimensions[row].height = 18
            row += 1
        ws.cell(row=row, column=1, value="TOTAL").font = Font(size=10, bold=True)
        ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=LIGHT)
        ws.cell(row=row, column=1).alignment = Alignment(indent=1)
        for i in range(2, 5):
            L = get_column_letter(i)
            c = ws.cell(row=row, column=i, value=f"=SUM({L}{first}:{L}{row - 1})")
            c.font = Font(size=10, bold=True)
            c.fill = PatternFill("solid", fgColor=LIGHT)
            c.alignment = Alignment(horizontal="center")
            c.number_format = "#,##0" if i < 4 else "#,##0.0"
        for i in range(1, 5):
            ws.cell(row=row, column=i).border = CELL_BORDER
        row += 2
        tip = ws.cell(row=row, column=1, value=(
            "Days assume 7.5 productive hours. This is business time away from the desk — the number "
            "to take to the sponsor when agreeing release of people for training."))
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
        tip.font = Font(size=9, italic=True, color="666666")
        tip.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
        return row + 1
    return _summary


def comms_summary(data, last_live):
    def _summary(ws, row, span, _ll):
        timing = f"{REG}!${col_letter('comms_timing')}${DATA_START}:${col_letter('comms_timing')}${last_live}"
        rat = f"{REG}!${col_letter('impact_rating')}${DATA_START}:${col_letter('impact_rating')}${last_live}"
        section_header(ws, row, "MESSAGES BY WAVE", span)
        row += 1
        table_header(ws, row, ["Wave", "Messages", "of which High/Critical", "Purpose"] + [""] * (span - 4),
                     ws_widths(ws, span))
        row += 1
        for name, s_wk, e_wk, purpose in COMMS_WAVES:
            ws.cell(row=row, column=1, value=name).font = Font(size=10, bold=True)
            ws.cell(row=row, column=1).alignment = Alignment(vertical="center", indent=1)
            ws.cell(row=row, column=2, value=f'=COUNTIF({timing},"*"&$A{row}&"*")')
            ws.cell(row=row, column=3, value=(
                f'=COUNTIFS({timing},"*"&$A{row}&"*",{rat},"High")'
                f'+COUNTIFS({timing},"*"&$A{row}&"*",{rat},"Critical")'))
            ws.cell(row=row, column=4, value=f"{purpose}  (T{s_wk:+d} to T{e_wk:+d} weeks)")
            for i in range(1, 5):
                c = ws.cell(row=row, column=i)
                c.border = CELL_BORDER
                if i in (2, 3):
                    c.font = Font(size=10)
                    c.alignment = Alignment(horizontal="center", vertical="center")
                    c.number_format = "#,##0"
                elif i == 4:
                    c.font = Font(size=10)
                    c.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
            ws.row_dimensions[row].height = 18
            row += 1
        row += 1
        tip = ws.cell(row=row, column=1, value=(
            "Wave counts match on the wave name appearing in the register's Comms Timing column. "
            "High and Critical impacts should appear in at least three waves — a single email in the "
            "Readiness window is not a communication plan."))
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
        tip.font = Font(size=9, italic=True, color="666666")
        tip.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
        return row + 1
    return _summary


def ws_widths(ws, span):
    return [ws.column_dimensions[get_column_letter(i)].width or 15 for i in range(1, span + 1)]


# --------------------------------------------------------------------------------------
# Sheet: Traceability
# --------------------------------------------------------------------------------------

def build_traceability(wb, data, last_live):
    ws = wb.create_sheet("Traceability")
    meta = data["meta"]
    widths = [12, 26, 48, 16, 34, 16]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    span = len(widths)

    style_title(ws, 1, "SOURCE TRACEABILITY", span, size=14)
    note = ws.cell(row=2, column=1, value=(
        "Every impact cites the documents it was derived from. When a business owner challenges a row in "
        "validation, this is what turns 'we disagree' into 'let's look at what the spec says'."))
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
    note.font = Font(size=9, italic=True, color="666666")
    note.alignment = Alignment(wrap_text=True, vertical="center", indent=1)

    row = 4
    section_header(ws, row, "SOURCE DOCUMENTS", span)
    row += 1
    table_header(ws, row, ["Ref", "Type", "Title", "Date", "Author / Participants",
                           "Impacts derived"], widths)
    row += 1
    src_col = f"{REG}!${col_letter('source_ref')}${DATA_START}:${col_letter('source_ref')}${last_live}"
    for d in meta.get("source_documents", []):
        vals = [d.get("ref", ""), d.get("type", ""), d.get("title", ""),
                d.get("date", ""), d.get("author_or_participants", "")]
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=i, value=v)
            c.font = Font(size=10, bold=(i == 1))
            c.alignment = Alignment(wrap_text=True, vertical="center", indent=1)
            c.border = CELL_BORDER
        cnt = ws.cell(row=row, column=6, value=f'=COUNTIF({src_col},"*"&$A{row}&"*")')
        cnt.font = Font(size=10, bold=True)
        cnt.alignment = Alignment(horizontal="center", vertical="center")
        cnt.number_format = "#,##0"
        cnt.border = CELL_BORDER
        ws.row_dimensions[row].height = 28
        row += 1
    ws.conditional_formatting.add(
        f"F6:F{row - 1}",
        CellIsRule(operator="equal", formula=["0"],
                   fill=RATING_FILLS["Critical"], font=RATING_FONTS["Critical"]),
    )
    row += 2

    # -- open questions for the validation workshop
    open_rows = [i for i in data["impacts"]
                 if i.get("confidence") == "Low" or (i.get("notes") or "").strip()]
    section_header(ws, row, f"OPEN QUESTIONS FOR VALIDATION — {len(open_rows)} items", span)
    row += 1
    table_header(ws, row, ["Impact ID", "Stakeholder group", "Open question / note",
                           "Confidence", "Process", "Status"], widths)
    row += 1
    first = row
    for imp in open_rows:
        ws.cell(row=row, column=1, value=imp["impact_id"]).font = Font(size=10, bold=True)
        for ci, field in enumerate(
                ["stakeholder_group", "notes", "confidence", "process_name", "validation_status"], start=2):
            c = ws.cell(row=row, column=ci, value=lookup(field, f"$A{row}", last_live))
            c.font = Font(size=10)
            c.alignment = Alignment(wrap_text=True, vertical="top",
                                    horizontal="center" if field in ("confidence", "validation_status") else "general")
        for i in range(1, span + 1):
            ws.cell(row=row, column=i).border = CELL_BORDER
        ws.row_dimensions[row].height = 42
        row += 1
    if row > first:
        ws.conditional_formatting.add(
            f"D{first}:D{row - 1}",
            CellIsRule(operator="equal", formula=['"Low"'],
                       fill=RATING_FILLS["Critical"], font=RATING_FONTS["Critical"]),
        )
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "3A3A3A"


# --------------------------------------------------------------------------------------
# Stats + orchestration
# --------------------------------------------------------------------------------------

def compute_stats(data):
    impacts = data["impacts"]
    by_rating = {r: {"count": 0, "people": 0, "effort": 0.0} for r in RATINGS}
    people_total = effort_total = 0
    for imp in impacts:
        rating = computed_rating(imp) or "Low"
        hc = imp.get("headcount_impacted") or 0
        aud = imp.get("training_audience_size")
        aud = hc if aud in (None, "") else aud
        dur = imp.get("training_duration_hrs") or 0
        effort = (dur or 0) * (aud or 0)
        by_rating[rating]["count"] += 1
        by_rating[rating]["people"] += hc
        by_rating[rating]["effort"] += effort
        people_total += hc
        effort_total += effort
    return {
        "total": len(impacts),
        "by_rating": by_rating,
        "people_total": people_total,
        "effort_total": effort_total,
        "by_group": Counter(i["stakeholder_group"] for i in impacts),
    }


def build_workbook(data, out_path):
    wb = Workbook()
    wb.remove(wb.active)

    stats = compute_stats(data)
    ref_ranges = build_reference(wb)
    _last_data, last_live = build_register(wb, data, ref_ranges)
    build_cover(wb, data, stats)
    build_heatmap(wb, data, last_live)

    build_rollup(
        wb, data, last_live,
        sheet_name="Training Plan",
        title="TRAINING PLAN  —  derived from the impact register",
        blurb=("Every impact flagged as needing training. Effort = duration × audience, calculated live "
               "from the register, so re-scoping a course updates the budget figure here."),
        filter_field="training_required",
        fields=[
            ("impact_id", "Impact ID"),
            ("stakeholder_group", "Audience"),
            ("process_name", "Process"),
            ("impact_rating", "Impact Rating"),
            ("training_type", "Delivery Method"),
            ("training_module_ref", "Module Ref"),
            ("training_duration_hrs", "Duration (hrs)"),
            ("training_audience_size", "Audience (#)"),
            ("training_effort_hrs", "Effort (person-hrs)"),
            ("training_timing", "Timing"),
            ("to_be_process", "What they must be able to do"),
            ("change_champion", "Business Owner"),
        ],
        widths=[11, 26, 28, 13, 19, 13, 11, 11, 14, 17, 50, 24],
        tab_color="1F6F6B",
        summary=training_summary(data, last_live),
    )

    build_rollup(
        wb, data, last_live,
        sheet_name="Comms Plan",
        title="COMMUNICATION PLAN  —  derived from the impact register",
        blurb=("Key messages by audience and wave. Sender matters more than channel: people accept the "
               "organisational rationale from a senior sponsor, and personal impact from their own line manager."),
        filter_field="comms_required",
        fields=[
            ("impact_id", "Impact ID"),
            ("stakeholder_group", "Audience"),
            ("impact_rating", "Impact Rating"),
            ("resistance_risk", "Resistance"),
            ("key_message", "Key Message"),
            ("benefit_narrative", "Benefit / WIIFM"),
            ("comms_channel", "Channel(s)"),
            ("comms_timing", "Wave / Timing"),
            ("comms_owner", "Owner / Sender"),
            ("mitigation_actions", "Mitigation Actions"),
        ],
        widths=[11, 26, 13, 12, 58, 42, 28, 26, 24, 42],
        tab_color="4A5899",
        summary=comms_summary(data, last_live),
    )

    build_traceability(wb, data, last_live)

    wb.move_sheet("Cover", offset=-wb.sheetnames.index("Cover"))
    order = ["Cover", "Impact Register", "Impact Heatmap", "Training Plan",
             "Comms Plan", "Traceability", "Reference"]
    wb._sheets = [wb[name] for name in order if name in wb.sheetnames]
    wb.active = 0
    wb.save(out_path)
    return stats


def main():
    ap = argparse.ArgumentParser(description="Generate a baseline Change Impact Assessment workbook.")
    ap.add_argument("input", help="Path to cia_input.json")
    ap.add_argument("-o", "--output", default="Change Impact Assessment.xlsx")
    ap.add_argument("--validate-only", action="store_true", help="Validate without writing the workbook")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        data = json.load(fh)

    errors, warnings = validate(data)

    if errors:
        print(f"\n✗ {len(errors)} error(s) — workbook not generated:\n")
        for e in errors:
            print(f"  • {e}")
        print()
        return 1

    if warnings:
        print(f"\n⚠  {len(warnings)} warning(s) — review before baselining:\n")
        for w in warnings:
            print(f"  • {w}")
        print()
    else:
        print("\n✓ No validation warnings.\n")

    if args.validate_only:
        print("Validation only — no workbook written.")
        return 0

    stats = build_workbook(data, args.output)
    print(f"✓ Wrote {args.output}")
    print(f"  {stats['total']} impacts  |  " + "  ".join(
        f"{r}: {stats['by_rating'][r]['count']}" for r in RATINGS))
    print(f"  {stats['people_total']:,} impact touchpoints  |  "
          f"{stats['effort_total']:,.0f} training person-hours "
          f"({stats['effort_total'] / 7.5:,.0f} days)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
