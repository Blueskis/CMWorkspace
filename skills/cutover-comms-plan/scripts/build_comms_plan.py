#!/usr/bin/env python3
"""Build a cutover communications plan workbook from a JSON spec.

Two modes:

  1. Default   - generates a formatted workbook from scratch (Comms Plan /
                 Plan Info / Reference sheets, dropdowns, filters).
  2. Template  - populates a copy of an existing .xlsx template, matching the
                 spec's fields to whatever headers the template already uses
                 and preserving its formatting.

Usage:
    python3 build_comms_plan.py --spec spec.json --out plan.xlsx
    python3 build_comms_plan.py --spec spec.json --out plan.xlsx \
        --template client_template.xlsx [--sheet "Comms Plan"] [--header-row 3]
    python3 build_comms_plan.py --list-fields

Requires openpyxl (pip install openpyxl).
"""

import argparse
import json
import re
import sys
from copy import copy
from datetime import date, datetime

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:  # pragma: no cover
    sys.exit("openpyxl is required. Install it with: pip install openpyxl")


# --------------------------------------------------------------------------
# Canonical schema
# --------------------------------------------------------------------------
# (spec key, output header, column width, synonyms used to match template headers)
FIELDS = [
    ("id", "Comms ID", 10,
     ["id", "ref", "no", "num", "number", "item", "comm id", "comms id", "message id"]),
    ("milestone", "Cutover Milestone", 18,
     ["milestone", "timing", "phase", "when", "cutover milestone", "trigger",
      "t-minus", "stage", "sequence"]),
    ("send_date", "Planned Send Date", 16,
     ["date", "send date", "planned date", "planned send date", "issue date",
      "target date", "distribution date", "scheduled date"]),
    ("title", "Comms Title", 34,
     ["title", "subject", "name", "comms title", "message", "headline",
      "communication", "description"]),
    ("purpose", "Purpose", 46,
     ["purpose", "objective", "why", "intent", "goal", "key message",
      "purpose / key message", "rationale"]),
    ("audience", "Audience", 30,
     ["audience", "target audience", "recipients", "who", "stakeholder",
      "stakeholders", "to", "audience group"]),
    ("channel", "Channel", 22,
     ["channel", "medium", "method", "vehicle", "delivery", "delivery method",
      "channel / medium"]),
    ("sender", "Sender (From)", 24,
     ["sender", "from", "issued by", "signed by", "sent by", "sender (from)",
      "on behalf of", "voice"]),
    ("owner", "Owner (Drafts/Sends)", 24,
     ["owner", "author", "drafter", "responsible", "prepared by", "accountable",
      "owner (drafts/sends)", "raci - r"]),
    ("approver", "Approver", 24,
     ["approver", "approval", "sign off", "sign-off", "signoff", "reviewed by",
      "approved by", "endorser"]),
    ("dependencies", "Dependencies", 38,
     ["dependency", "dependencies", "depends on", "pre-requisite", "prerequisite",
      "prerequisites", "inputs", "blockers", "linked activity"]),
    ("content_link", "Comms Content Link", 26,
     ["content", "content link", "comms content", "comms content link", "link",
      "collateral", "artefact", "artifact", "material", "draft link",
      "document link", "attachment"]),
    ("status", "Status", 14,
     ["status", "state", "progress", "rag"]),
    ("notes", "Notes", 32,
     ["notes", "comments", "remarks", "additional info"]),
]

FIELD_KEYS = [f[0] for f in FIELDS]
HEADERS = {f[0]: f[1] for f in FIELDS}
WIDTHS = {f[0]: f[2] for f in FIELDS}
DATE_FIELDS = {"send_date"}

# Fields that must exist as a column in the output even if a template lacks them.
REQUIRED_COLUMNS = ["purpose", "audience", "channel", "sender", "owner",
                    "approver", "dependencies", "content_link"]

CHANNEL_OPTIONS = [
    "Email", "Email (all-user)", "Teams/Slack post", "Teams/Slack channel",
    "Intranet article", "Manager cascade", "Town hall / all-hands",
    "Service desk banner", "In-app / system banner", "SMS / push",
    "Customer notice", "Vendor notice", "Poster / digital signage",
]

STATUS_OPTIONS = [
    "Not started", "Drafting", "In review", "Approved", "Scheduled", "Sent",
    "Cancelled",
]

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
TITLE_FONT = Font(bold=True, size=13, color="1F3864")
LABEL_FONT = Font(bold=True, size=10)
BODY_FONT = Font(size=10)
LINK_FILL = PatternFill("solid", fgColor="FFF2CC")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def normalize(text):
    """Lowercase, strip punctuation/whitespace for fuzzy header matching."""
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def coerce_date(value):
    """Return a date object for ISO-ish strings, else the original value."""
    if isinstance(value, (datetime, date)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return value  # free text like "Cutover day, 06:00" is legitimate


def load_spec(path):
    with open(path, encoding="utf-8") as handle:
        spec = json.load(handle)
    if not isinstance(spec, dict):
        sys.exit("Spec must be a JSON object.")
    comms = spec.get("comms")
    if not isinstance(comms, list) or not comms:
        sys.exit("Spec must contain a non-empty 'comms' array.")
    unknown = {k for row in comms if isinstance(row, dict) for k in row} - set(FIELD_KEYS)
    if unknown:
        print(f"  ! Ignoring unrecognised comms keys: {', '.join(sorted(unknown))}",
              file=sys.stderr)
    return spec


def cell_value(field, row):
    value = row.get(field, "")
    if value is None:
        return ""
    if field in DATE_FIELDS:
        return coerce_date(value)
    return value


# --------------------------------------------------------------------------
# Mode 1: build from scratch
# --------------------------------------------------------------------------
def build_from_scratch(spec, out_path):
    workbook = Workbook()
    plan = workbook.active
    plan.title = "Comms Plan"

    for index, key in enumerate(FIELD_KEYS, start=1):
        cell = plan.cell(row=1, column=index, value=HEADERS[key])
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = BORDER
        plan.column_dimensions[get_column_letter(index)].width = WIDTHS[key]
    plan.row_dimensions[1].height = 30

    for offset, row in enumerate(spec["comms"]):
        excel_row = offset + 2
        for index, key in enumerate(FIELD_KEYS, start=1):
            cell = plan.cell(row=excel_row, column=index, value=cell_value(key, row))
            cell.font = BODY_FONT
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if key in DATE_FIELDS and isinstance(cell.value, (datetime, date)):
                cell.number_format = "dd-mmm-yyyy"
            if key == "content_link":
                # Deliberately blank on generation - future linkage to content.
                cell.fill = LINK_FILL

    last_row = len(spec["comms"]) + 1
    plan.freeze_panes = "D2"
    plan.auto_filter.ref = f"A1:{get_column_letter(len(FIELD_KEYS))}{last_row}"

    _build_plan_info(workbook, spec)
    reference = _build_reference(workbook)
    _add_validations(plan, reference, last_row)

    workbook.save(out_path)
    return last_row - 1


def _build_plan_info(workbook, spec):
    sheet = workbook.create_sheet("Plan Info")
    sheet.column_dimensions["A"].width = 30
    sheet.column_dimensions["B"].width = 78

    sheet["A1"] = spec.get("project") or "Cutover Communications Plan"
    sheet["A1"].font = TITLE_FONT

    rows = [
        ("Cutover type", spec.get("cutover_type", "")),
        ("Complexity tier", spec.get("complexity_tier", "")),
        ("Go-live date", spec.get("go_live_date", "")),
        ("Cutover window", spec.get("cutover_window", "")),
        ("Number of comms", len(spec["comms"])),
        ("Cadence rule applied", spec.get("cadence_rule", "")),
        ("Complexity modifiers applied", spec.get("modifiers", "")),
        ("Prepared by", spec.get("prepared_by", "")),
        ("Version", spec.get("version", "0.1 Draft")),
        ("Last updated", spec.get("last_updated", date.today().isoformat())),
        ("Notes", spec.get("notes", "")),
    ]
    for offset, (label, value) in enumerate(rows, start=3):
        if isinstance(value, list):
            value = "; ".join(str(item) for item in value)
        sheet.cell(row=offset, column=1, value=label).font = LABEL_FONT
        cell = sheet.cell(row=offset, column=2, value=value)
        cell.font = BODY_FONT
        cell.alignment = Alignment(vertical="top", wrap_text=True)


def _build_reference(workbook):
    sheet = workbook.create_sheet("Reference")
    sheet.column_dimensions["A"].width = 26
    sheet.column_dimensions["B"].width = 62
    sheet.column_dimensions["D"].width = 26
    sheet.column_dimensions["F"].width = 20

    sheet["A1"] = "Column dictionary"
    sheet["A1"].font = TITLE_FONT
    definitions = {
        "id": "Unique reference for the comms line item.",
        "milestone": "Cutover milestone the comms is anchored to (T-14, T-1, Cutover begins, Go-live, T+7).",
        "send_date": "Actual calendar date/time the comms goes out.",
        "title": "Working title or subject line.",
        "purpose": "What this comms is for - the decision, action, or awareness it drives.",
        "audience": "Who receives it. One audience group per line where the message differs.",
        "channel": "How it is delivered.",
        "sender": "Whose name it goes out under - the voice with the authority the message needs.",
        "owner": "Who drafts, schedules and sends it. Accountable for delivery.",
        "approver": "Who signs off before it goes out. Should not be the same person as the owner.",
        "dependencies": "What must be true or done first (go/no-go outcome, runbook step, distribution list, translations).",
        "content_link": "BLANK BY DESIGN - link to the drafted content once it exists.",
        "status": "Drafting/approval progress.",
        "notes": "Anything else.",
    }
    for offset, key in enumerate(FIELD_KEYS, start=3):
        sheet.cell(row=offset, column=1, value=HEADERS[key]).font = LABEL_FONT
        cell = sheet.cell(row=offset, column=2, value=definitions[key])
        cell.font = BODY_FONT
        cell.alignment = Alignment(vertical="top", wrap_text=True)

    sheet["D1"] = "Channel list"
    sheet["D1"].font = TITLE_FONT
    for offset, option in enumerate(CHANNEL_OPTIONS, start=3):
        sheet.cell(row=offset, column=4, value=option).font = BODY_FONT

    sheet["F1"] = "Status list"
    sheet["F1"].font = TITLE_FONT
    for offset, option in enumerate(STATUS_OPTIONS, start=3):
        sheet.cell(row=offset, column=6, value=option).font = BODY_FONT

    return sheet


def _add_validations(plan, reference, last_row):
    """Attach dropdowns to Channel and Status, sourced from the Reference sheet."""
    validation_rows = max(last_row, 200)
    specs = [
        ("channel", "D", len(CHANNEL_OPTIONS)),
        ("status", "F", len(STATUS_OPTIONS)),
    ]
    for key, ref_col, count in specs:
        column = get_column_letter(FIELD_KEYS.index(key) + 1)
        formula = f"='{reference.title}'!${ref_col}$3:${ref_col}${count + 2}"
        validation = DataValidation(type="list", formula1=formula, allow_blank=True)
        validation.error = "Pick a value from the Reference sheet list."
        validation.errorTitle = "Value not in list"
        plan.add_data_validation(validation)
        validation.add(f"{column}2:{column}{validation_rows}")


# --------------------------------------------------------------------------
# Mode 2: populate an existing template
# --------------------------------------------------------------------------
def find_header_row(sheet, forced=None, scan_rows=20):
    """Return (header_row_index, {field_key: column_index})."""
    best = (0, None, {})
    candidates = [forced] if forced else range(1, min(scan_rows, sheet.max_row or 1) + 1)
    for row_index in candidates:
        mapping = {}
        for column_index in range(1, (sheet.max_column or 1) + 1):
            header = normalize(sheet.cell(row=row_index, column=column_index).value)
            if not header:
                continue
            key = match_header(header)
            if key and key not in mapping:
                mapping[key] = column_index
        if len(mapping) > best[0]:
            best = (len(mapping), row_index, mapping)
    if forced:
        return forced, best[2]
    if best[0] < 3:
        return None, {}
    return best[1], best[2]


def match_header(normalized_header):
    """Map a normalized template header to a canonical field key."""
    for key, _, _, synonyms in FIELDS:
        if normalized_header in (normalize(s) for s in synonyms):
            return key
    # Fall back to substring containment, longest synonym first for precision.
    scored = []
    for key, _, _, synonyms in FIELDS:
        for synonym in synonyms:
            token = normalize(synonym)
            if token and token in normalized_header:
                scored.append((len(token), key))
    if scored:
        scored.sort(reverse=True)
        return scored[0][1]
    return None


def build_from_template(spec, template_path, out_path, sheet_name=None, header_row=None):
    workbook = load_workbook(template_path)
    if sheet_name:
        if sheet_name not in workbook.sheetnames:
            sys.exit(f"Sheet '{sheet_name}' not found. Sheets: {workbook.sheetnames}")
        sheet = workbook[sheet_name]
    else:
        sheet = workbook.worksheets[0]

    header_row, mapping = find_header_row(sheet, forced=header_row)
    if not header_row or not mapping:
        sys.exit(
            "Could not identify a header row in the template. Re-run with "
            "--sheet and --header-row to point at it explicitly."
        )

    print(f"  Template sheet : {sheet.title} (header row {header_row})")
    matched = ", ".join(sorted(mapping))
    print(f"  Matched columns: {matched}")

    # Any required column the template lacks gets appended so no data is lost.
    next_column = (sheet.max_column or len(mapping)) + 1
    for key in REQUIRED_COLUMNS:
        if key in mapping:
            continue
        if not any(str(row.get(key, "")).strip() for row in spec["comms"]) \
                and key != "content_link":
            continue
        cell = sheet.cell(row=header_row, column=next_column, value=HEADERS[key])
        template_header = sheet.cell(row=header_row, column=1)
        if template_header.has_style:
            cell._style = copy(template_header._style)
        sheet.column_dimensions[get_column_letter(next_column)].width = WIDTHS[key]
        mapping[key] = next_column
        print(f"  + Added missing column '{HEADERS[key]}' at "
              f"{get_column_letter(next_column)}{header_row}")
        next_column += 1

    dropped = [HEADERS[k] for k in FIELD_KEYS
               if k not in mapping and any(str(r.get(k, "")).strip() for r in spec["comms"])]
    if dropped:
        print(f"  ! No template column for: {', '.join(dropped)} - this data is not written.",
              file=sys.stderr)

    style_source = header_row + 1
    for offset, row in enumerate(spec["comms"]):
        excel_row = header_row + 1 + offset
        for key, column_index in mapping.items():
            cell = sheet.cell(row=excel_row, column=column_index,
                              value=cell_value(key, row))
            source = sheet.cell(row=style_source, column=column_index)
            if excel_row != style_source and source.has_style:
                cell._style = copy(source._style)
            if key in DATE_FIELDS and isinstance(cell.value, (datetime, date)) \
                    and not cell.number_format.startswith(("d", "m", "y")):
                cell.number_format = "dd-mmm-yyyy"

    workbook.save(out_path)
    return len(spec["comms"])


# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", help="Path to the JSON plan spec.")
    parser.add_argument("--out", help="Path to write the .xlsx to.")
    parser.add_argument("--template", help="Existing .xlsx template to populate.")
    parser.add_argument("--sheet", help="Sheet name within the template.")
    parser.add_argument("--header-row", type=int,
                        help="1-based header row in the template (skips auto-detection).")
    parser.add_argument("--list-fields", action="store_true",
                        help="Print the spec keys and exit.")
    args = parser.parse_args()

    if args.list_fields:
        for key, header, _, _ in FIELDS:
            print(f"{key:<14} -> {header}")
        return

    if not args.spec or not args.out:
        parser.error("--spec and --out are required (or use --list-fields)")

    spec = load_spec(args.spec)
    if args.template:
        count = build_from_template(spec, args.template, args.out,
                                    args.sheet, args.header_row)
    else:
        count = build_from_scratch(spec, args.out)
    print(f"Wrote {count} comms line item(s) to {args.out}")


if __name__ == "__main__":
    main()
