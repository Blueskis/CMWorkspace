"""Excel workbook for the CM Effort Estimator: a formula engine and the record.

Mirrors the engine in estimator.html cell by cell, so the same inputs give the
same mandays with no AI involved: a fallback when the Copilot skill is
unavailable, and an independent cross-check when it is.

Three calculation sheets run the same formulas against different sets of
adjustments, which is how the workbook reproduces the artifact's
propose-then-confirm flow without any code:

    Calc_Baseline   no judgement adjustments
    Calc_Current    adjustments marked Accepted
    Calc_Preview    adjustments marked Accepted or Proposed

Every rule here has a twin in the engine; tests/test_copilot_pack.py fills
this workbook from the engine's own TSV, recalculates it in LibreOffice and
checks the totals agree.

Formulas stick to Excel 2007-era functions (INDEX, MATCH, SUMIFS,
SUMPRODUCT) so they evaluate identically in Excel and LibreOffice.
"""

from copy import copy

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as col
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.formula import ArrayFormula

ACCENT = "2E3D77"
ACCENT_SOFT = "E4E8F6"
INPUT_FILL = "FFF7D6"
LINE = "DCE1EA"
FONT = "Arial"

N_LINES_PER_STREAM = 53
LINES_FIRST = 6           # Lines!A6
ADJ_FIRST, ADJ_LAST = 6, 105
CUSTOM_FIRST, CUSTOM_LAST = 6, 45
LIB_FIRST = 6
CAT_FIRST = 6
ARCH_FIRST = 6
QUOTES_FIRST, QUOTES_LAST = 6, 105

LEVELS = ["Simple", "Standard", "Complex"]
CLAMP_ORDER = {"Simple": ["Simple", "Standard", "Complex"],
               "Standard": ["Standard", "Complex", "Simple"],
               "Complex": ["Complex", "Standard", "Simple"]}
QTY_RULE_ORDER = ["one", "two", "months", "months_double", "months_third", "weeks", "waves", "waves_double",
                  "units", "units_min2", "geos", "modules", "modules_half", "modules_third", "extra_languages",
                  "comms_cadence", "hypercare_double", "trainer_sessions", "training_sessions"]
OPS = ["set_driver", "set_line_level", "set_line_mode", "set_line_qty", "set_line_include",
       "set_line_optional", "set_global", "add_line", "note"]
GLOBAL_BASE_CELL = {"involvement.global": "Inputs!$C$11", "involvement.local": "Inputs!$C$12",
                    "reviewCycles": "Inputs!$C$8", "localisationFactor": "Inputs!$C$13",
                    "contingency": "Inputs!$C$10"}

thin = Side(style="thin", color=LINE)
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)


def font(**kw):
    return Font(name=FONT, size=kw.pop("size", 10), **kw)


def header_row(ws, row, labels, start_col=1, widths=None):
    for i, label in enumerate(labels):
        c = ws.cell(row=row, column=start_col + i, value=label)
        c.font = font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=ACCENT)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BOX
    if widths:
        for i, w in enumerate(widths):
            ws.column_dimensions[col(start_col + i)].width = w


def title(ws, text, sub):
    ws["A1"] = text
    ws["A1"].font = Font(name="Georgia", size=16, bold=True, color=ACCENT)
    ws["A2"] = sub
    ws["A2"].font = font(color="7A8494", italic=True)


def mark_input(cell):
    cell.fill = PatternFill("solid", fgColor=INPUT_FILL)
    cell.font = font(color="0000FF")
    cell.border = BOX


def adj_range(c):
    return f"Adjustments!${c}${ADJ_FIRST}:${c}${ADJ_LAST}"


# ---------------------------------------------------------------------------
# Reference sheets
# ---------------------------------------------------------------------------

def build_settings(wb, data):
    ws = wb.create_sheet("Settings")
    title(ws, "Settings", "Factors the engine applies. Admin only: changes here reprice every estimate in this file.")
    header_row(ws, 4, ["", "Mode", "Effort x", "Capacity x"], widths=[3, 22, 12, 12])
    for i, m in enumerate(data["modes"]):
        r = 5 + i
        ws.cell(row=r, column=2, value=m["id"])
        for j, k in enumerate(["effort", "capacity"]):
            c = ws.cell(row=r, column=3 + j, value=data["modeFactors"][m["id"]][k])
            mark_input(c)
    header_row(ws, 9, ["", "Complexity (1-5)", "Multiplier"], widths=None)
    for i in range(1, 6):
        ws.cell(row=9 + i, column=2, value=i)
        mark_input(ws.cell(row=9 + i, column=3, value=data["complexityMult"][str(i)]))
    header_row(ws, 16, ["", "Client CM maturity", "Multiplier"])
    for i, k in enumerate(["low", "medium", "high"]):
        ws.cell(row=17 + i, column=2, value=k)
        mark_input(ws.cell(row=17 + i, column=3, value=data["maturityMult"][k]))
    labels = [("Client review per cycle (% of build)", data["reviewClientPct"]),
              ("Our review per cycle (% of build)", data["reviewOursPct"]),
              ("Default localisation effort (% of build, per market)", data["localisationFactor"] * 100),
              ("Judgement warning threshold (share of baseline)", 0.4)]
    for i, (label, v) in enumerate(labels):
        ws.cell(row=22 + i, column=2, value=label)
        mark_input(ws.cell(row=22 + i, column=3, value=v))
    ws.cell(row=26, column=2, value="Typical tasks per deliverable (median, sizes custom lines)")
    ws.cell(row=26, column=3, value=f"=IF(MOD(COUNT(Catalogue!$K${CAT_FIRST}:$K${CAT_FIRST + 52}),2)=0,"
                                      f"ROUND(MEDIAN(Catalogue!$K${CAT_FIRST}:$K${CAT_FIRST + 52}),0),"
                                      f"MEDIAN(Catalogue!$K${CAT_FIRST}:$K${CAT_FIRST + 52}))")

    header_row(ws, 4, ["Quantity rule"], start_col=6)
    ws.column_dimensions["F"].width = 20
    for i, rule in enumerate(QTY_RULE_ORDER):
        ws.cell(row=5 + i, column=6, value=rule)

    header_row(ws, 4, ["Judgement op"], start_col=8)
    ws.column_dimensions["H"].width = 20
    for i, op in enumerate(OPS):
        ws.cell(row=5 + i, column=8, value=op)

    header_row(ws, 4, ["Global lever", "Min", "Max"], start_col=10)
    ws.column_dimensions["J"].width = 22
    for i, (t, (lo, hi)) in enumerate(data["judgementGlobals"].items()):
        ws.cell(row=5 + i, column=10, value=t)
        ws.cell(row=5 + i, column=11, value=lo)
        ws.cell(row=5 + i, column=12, value=hi)
    return ws


def build_archetypes(wb, data):
    ws = wb.create_sheet("Archetypes")
    title(ws, "Effort archetypes", "Hours per task by complexity, and the team of ranks that staffs each kind of work. Admin only.")
    ranks = data["ranks"]
    header_row(ws, 5, ["Archetype"] + LEVELS + [r["short"] for r in ranks] + ["Team"] + [f"{r['short']} share" for r in ranks],
               widths=[30] + [10] * 3 + [6] * 7 + [7] + [9] * 7)
    names = list(data["archetypeHours"].keys())
    for i, a in enumerate(names):
        r = ARCH_FIRST + i
        ws.cell(row=r, column=1, value=a)
        for j, lvl in enumerate(LEVELS):
            v = data["archetypeHours"][a][lvl]
            mark_input(ws.cell(row=r, column=2 + j, value=v))
        mix = data["rankMix"].get(a, data["defaultMix"])
        for j, rk in enumerate(ranks):
            mark_input(ws.cell(row=r, column=5 + j, value=mix.get(rk["id"], 0)))
        ws.cell(row=r, column=12, value=f"=SUM(E{r}:K{r})")
        for j in range(7):
            mixc, defc = col(5 + j), col(5 + j)
            ws.cell(row=r, column=13 + j,
                    value=f"=IF($L{r}>0,{mixc}{r}/$L{r},{defc}$16/$L$16)").number_format = "0%"
    ws.cell(row=15, column=1, value="Default team (used when an archetype has nobody on it)").font = font(italic=True)
    for j, rk in enumerate(ranks):
        mark_input(ws.cell(row=16, column=5 + j, value=data["defaultMix"].get(rk["id"], 0)))
    ws.cell(row=16, column=1, value="Default team")
    ws.cell(row=16, column=12, value="=SUM(E16:K16)")
    return ws, names


def build_library(wb, data, arch_names):
    ws = wb.create_sheet("Library")
    title(ws, "Hours library", "189 costed tasks. Hours resolve through the archetype matrix unless pinned. Admin only.")
    ranks = data["ranks"]
    rank_cols = [f"{lvl[:3]} {r['short']}" for lvl in LEVELS for r in ranks]
    header_row(ws, 5, ["Catalogue ID", "Task", "Unit", "Archetype", "Graded", "Source hours", "Enabled", "Pinned hours",
                       "Arch row", "h @ Simple", "h @ Standard", "h @ Complex", "h @ own grade"] + rank_cols,
               widths=[18, 44, 18, 26, 10, 9, 8, 9, 7, 9, 9, 9, 9] + [7] * 21)
    arch_rng = f"Archetypes!$A${ARCH_FIRST}:$A${ARCH_FIRST + len(arch_names) - 1}"
    level_col = {"Simple": "B", "Standard": "C", "Complex": "D"}

    def clamp(r, level):
        order = CLAMP_ORDER[level]
        cells = [f"INDEX(Archetypes!${level_col[l]}${ARCH_FIRST}:${level_col[l]}${ARCH_FIRST + len(arch_names) - 1},$I{r})"
                 for l in order]
        expr = f"$F{r}"
        for c in reversed(cells):
            expr = f"IF(N({c})>0,{c},{expr})"
        return f'=IF($G{r}<>"Y",0,IF(N($H{r})>0,$H{r},{expr}))'

    for i, t in enumerate(data["tasks"]):
        r = LIB_FIRST + i
        for j, v in enumerate([t["g"], t["t"], t["u"], t["a"], t["c"], t["h"]]):
            ws.cell(row=r, column=1 + j, value=v)
        mark_input(ws.cell(row=r, column=7, value="Y"))
        mark_input(ws.cell(row=r, column=8, value=None))
        ws.cell(row=r, column=9, value=f"=MATCH($D{r},{arch_rng},0)")
        for j, lvl in enumerate(LEVELS):
            ws.cell(row=r, column=10 + j, value=clamp(r, lvl))
        ws.cell(row=r, column=13, value=f'=IF($E{r}="Simple",J{r},IF($E{r}="Standard",K{r},L{r}))')
        for li, lvl in enumerate(LEVELS):
            hcol = col(10 + li)
            for ri in range(7):
                share = f"INDEX(Archetypes!${col(13 + ri)}${ARCH_FIRST}:${col(13 + ri)}${ARCH_FIRST + len(arch_names) - 1},$I{r})"
                ws.cell(row=r, column=14 + li * 7 + ri, value=f"={hcol}{r}*{share}")
    return ws, LIB_FIRST + len(data["tasks"]) - 1


def build_catalogue(wb, data, lib_last):
    ws = wb.create_sheet("Catalogue")
    title(ws, "Deliverable catalogue", "53 CM deliverables. Library hours roll up here; the estimate reads from it.")
    ranks = data["ranks"]
    rank_cols = [f"{lvl[:3]} {r['short']}" for lvl in LEVELS for r in ranks]
    header_row(ws, 5, ["Catalogue ID", "Deliverable", "Category", "Unit", "Qty rule", "Core", "Geo", "Mode applies",
                       "Rate key", "Tasks on", "Tasks (median)", "Hours @ Simple", "Hours @ Standard", "Hours @ Complex",
                       "Weight Simple", "Weight Standard", "Weight Complex", "Baseline level", "Benchmark md/unit"] + rank_cols,
               widths=[20, 40, 26, 14, 16, 6, 6, 8, 18, 7, 8, 9, 9, 9, 9, 9, 9, 10, 10] + [7] * 21)
    lib = lambda c: f"Library!${c}${LIB_FIRST}:${c}${lib_last}"  # noqa: E731
    modes = set(data["modeApplies"])
    for i, c in enumerate(data["catalogue"]):
        r = CAT_FIRST + i
        vals = [c["id"], c["name"], c["cat"], c["unit"], c["qty"], "Y" if c["core"] else "", "Y" if c["geo"] else "",
                "Y" if c["id"] in modes else "", c["rateKey"]]
        for j, v in enumerate(vals):
            ws.cell(row=r, column=1 + j, value=v)
        ws.cell(row=r, column=10, value=f'=COUNTIFS({lib("A")},$A{r},{lib("G")},"Y")')
        ws.cell(row=r, column=11, value=f'=IF(J{r}>0,J{r},"")')
        for j, hc in enumerate(["J", "K", "L"]):
            ws.cell(row=r, column=12 + j, value=f"=SUMIFS({lib(hc)},{lib('A')},$A{r})")
        for j, lvl in enumerate(LEVELS):
            ws.cell(row=r, column=15 + j, value=f'=SUMIFS({lib("M")},{lib("A")},$A{r},{lib("E")},"{lvl}")')
        ws.cell(row=r, column=18, value=f'=IF(MAX(O{r}:Q{r})<=0,"Standard",IF(O{r}=MAX(O{r}:Q{r}),"Simple",'
                                        f'IF(P{r}=MAX(O{r}:Q{r}),"Standard","Complex")))')
        rng = f"'Past projects'!$D${QUOTES_FIRST}:$D${QUOTES_LAST}"
        dpu = f"'Past projects'!$G${QUOTES_FIRST}:$G${QUOTES_LAST}"
        ref = f"S{r}"
        ws[ref] = ArrayFormula(ref, f'=IFERROR(MEDIAN(IF(({rng}=$I{r})*ISNUMBER({dpu}),{dpu})),0)')
        for k in range(21):
            lc = col(14 + k)
            ws.cell(row=r, column=20 + k, value=f"=SUMIFS({lib(lc)},{lib('A')},$A{r})")
    return ws


def build_quotes(wb, data):
    ws = wb.create_sheet("Past projects")
    title(ws, "Past project effort", "Calibrates a deliverable only when every one of its library tasks is switched off. Sample rows, replace with actuals.")
    header_row(ws, 5, ["Project", "Year", "Industry", "Deliverable type (rate key)", "Qty", "Mandays", "Mandays / unit"],
               widths=[28, 7, 16, 26, 8, 9, 12])
    for i in range(QUOTES_LAST - QUOTES_FIRST + 1):
        r = QUOTES_FIRST + i
        if i < len(data["quotes"]):
            q = data["quotes"][i]
            for j, v in enumerate([q["project"], q["year"], q["industry"], q["deliverable"], q["qty"], q["days"]]):
                mark_input(ws.cell(row=r, column=1 + j, value=v))
        ws.cell(row=r, column=7, value=f'=IF(AND(N(E{r})>0,N(F{r})>0),F{r}/E{r},"")')
    return ws


# ---------------------------------------------------------------------------
# Input sheets
# ---------------------------------------------------------------------------

def build_inputs(wb, data):
    ws = wb.create_sheet("Inputs", 1)
    title(ws, "Inputs", "Yellow cells are yours. Paste the agent's TSV blocks at the cell it names (e.g. Inputs!C5).")
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 46
    ws.column_dimensions["C"].width = 22
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 14
    header_row(ws, 4, ["Key", "Engagement", "Value"])
    rows = [("client", "Client / pursuit name", ""), ("scope", "Scope of the rollout: global, local or both", "global"),
            ("mode", "Default mode of conduct: virtual, blended or physical", "blended"),
            ("reviewCycles", "Review cycles (1-3)", 1), ("hoursPerDay", "Hours per day", 8),
            ("contingency", "Delivery buffer %", 0), ("involvement.global", "Our share of the global build %", 100),
            ("involvement.local", "Our share of the local build %", 100),
            ("localisationFactor", "Localisation effort % (blank = Settings default)", None),
            ("rfpAnalysed", "RFP analysed (Y once deliverables were read from an RFP)", "")]
    for i, (k, label, v) in enumerate(rows):
        r = 5 + i
        ws.cell(row=r, column=1, value=k).font = font(color="7A8494")
        ws.cell(row=r, column=2, value=label)
        mark_input(ws.cell(row=r, column=3, value=v))
    dv = DataValidation(type="list", formula1='"global,local,both"', allow_blank=False)
    ws.add_data_validation(dv); dv.add("C6")
    dvm = DataValidation(type="list", formula1='"virtual,blended,physical"', allow_blank=False)
    ws.add_data_validation(dvm); dvm.add("C7")

    header_row(ws, 17, ["Driver key", "Scope driver", "Value (blank = default)", "Default", "Current", "Baseline"])
    for i, d in enumerate(data["drivers"]):
        r = 18 + i
        ws.cell(row=r, column=1, value=d["key"]).font = font(color="7A8494")
        ws.cell(row=r, column=2, value=d["label"] + (" (" + ", ".join(str(o[0]) for o in d["options"]) + ")" if d["options"] else ""))
        mark_input(ws.cell(row=r, column=3, value=None))
        ws.cell(row=r, column=4, value=d["def"])
        ws.cell(row=r, column=5, value=f"=Calc_Current!B{5 + i}")
        ws.cell(row=r, column=6, value=f"=Calc_Baseline!B{5 + i}")
    return ws


def line_ids(data):
    ids = []
    for stream in ["global", "local"]:
        for c in data["catalogue"]:
            ids.append((f"{stream}:{c['id']}", stream, c["id"], c["name"]))
    return ids


def build_lines(wb, data):
    ws = wb.create_sheet("Lines", 2)
    title(ws, "Lines", "One row per deliverable per stream. Columns E-L are inputs (paste the agent's Lines!E6 block); M-S show the current estimate.")
    header_row(ws, 5, ["Line ID", "Stream", "Catalogue ID", "Deliverable", "RFP signal", "RFP option", "Client term",
                       "Include (Y/N)", "Qty override", "Level override", "Mode override", "Option (Y/N)",
                       "Level used", "Mode used", "Qty", "Mandays / unit", "Mandays", "In estimate", "Option"],
               widths=[30, 8, 22, 40, 7, 7, 26, 8, 8, 10, 10, 8, 10, 10, 7, 9, 9, 8, 7])
    for i, (lid, stream, cid, name) in enumerate(line_ids(data)):
        r = LINES_FIRST + i
        cr = 45 + i
        for j, v in enumerate([lid, stream, cid, name]):
            ws.cell(row=r, column=1 + j, value=v)
        for j in range(5, 13):
            mark_input(ws.cell(row=r, column=j, value=None))
        ws.cell(row=r, column=13, value=f"=Calc_Current!E{cr}")
        ws.cell(row=r, column=14, value=f"=Calc_Current!H{cr}")
        ws.cell(row=r, column=15, value=f"=Calc_Current!Q{cr}")
        ws.cell(row=r, column=16, value=f"=Calc_Current!O{cr}")
        ws.cell(row=r, column=17, value=f"=Calc_Current!X{cr}").number_format = "0.0"
        ws.cell(row=r, column=18, value=f'=IF(Calc_Current!W{cr},"Y","")')
        ws.cell(row=r, column=19, value=f'=IF(AND(Calc_Current!W{cr},Calc_Current!U{cr}),"Y","")')
    ws.freeze_panes = "E6"
    for rng, f in [("H6:H111", '"Y,N"'), ("L6:L111", '"Y,N"'), ("J6:J111", '"Simple,Standard,Complex"'),
                   ("K6:K111", '"virtual,blended,physical"')]:
        dv = DataValidation(type="list", formula1=f, allow_blank=True)
        ws.add_data_validation(dv); dv.add(rng)
    return ws


def build_custom(wb, data, arch_names):
    ws = wb.create_sheet("Custom lines", 3)
    title(ws, "Custom lines", "Deliverables the catalogue lacks. Rows with a Source adjustment ID count only while that adjustment is accepted.")
    header_row(ws, 5, ["Line ID", "Stream", "Deliverable", "Archetype", "Level", "Mode", "Qty", "Include (Y/N)",
                       "Option (Y/N)", "Source adjustment ID", "Mandays (current)", "Counts now"],
               widths=[30, 8, 36, 26, 10, 10, 7, 8, 8, 26, 10, 8])
    for i in range(CUSTOM_LAST - CUSTOM_FIRST + 1):
        r = CUSTOM_FIRST + i
        cr = 155 + i
        for j in range(1, 11):
            mark_input(ws.cell(row=r, column=j, value=None))
        ws.cell(row=r, column=11, value=f"=Calc_Current!T{cr}").number_format = "0.0"
        ws.cell(row=r, column=12, value=f'=IF(Calc_Current!S{cr},"Y","")')
    dv = DataValidation(type="list", formula1=f"=Archetypes!$A${ARCH_FIRST}:$A${ARCH_FIRST + len(arch_names) - 1}", allow_blank=True)
    ws.add_data_validation(dv); dv.add(f"D{CUSTOM_FIRST}:D{CUSTOM_LAST}")
    return ws


def build_adjustments(wb, data):
    ws = wb.create_sheet("Adjustments", 4)
    title(ws, "Judgement adjustments", "The audit log. Paste the agent's rows as Proposed, check Summary's preview, then set each to Accepted or Rejected. Revert = set Reverted.")
    header_row(ws, 5, ["ID", "Op", "Target", "Value", "Rationale", "Confidence", "Status", "Engine delta (md)",
                       "Check", "Key", "Live (current)", "Live (preview)"],
               widths=[26, 16, 30, 14, 60, 10, 11, 10, 34, 30, 8, 8])
    ops = f"Settings!$H$5:$H${4 + len(OPS)}"
    gl = "Settings!$J$5:$J$9"
    drv_keys = "Inputs!$A$18:$A$28"
    for r in range(ADJ_FIRST, ADJ_LAST + 1):
        for j in range(1, 9):
            mark_input(ws.cell(row=r, column=j, value=None))
        num = f"IFERROR(--D{r},-1)"
        boolok = f'OR(UPPER(D{r}&"")="TRUE",UPPER(D{r}&"")="FALSE",UPPER(D{r}&"")="Y",UPPER(D{r}&"")="N",D{r}=1,D{r}=0)'
        driver_check = (f'IF(C{r}="maturity",IF(OR(D{r}="low",D{r}="medium",D{r}="high"),"OK","Invalid: maturity is low, medium or high"),'
                        f'IF(C{r}="complexity",IF(AND({num}>=1,{num}<=5,{num}=INT({num})),"OK","Invalid: complexity is 1-5"),'
                        f'IF({num}>=0,"OK","Invalid: driver must be a number, zero or more")))')
        global_check = (f'IF(AND({num}>=INDEX(Settings!$K$5:$K$9,MATCH(C{r},{gl},0)),{num}<=INDEX(Settings!$L$5:$L$9,MATCH(C{r},{gl},0))),'
                        f'"OK","Invalid: out of range for "&C{r})')
        exists = f"COUNTIF(Lines!$A${LINES_FIRST}:$A${LINES_FIRST + 105},C{r})+COUNTIF('Custom lines'!$A${CUSTOM_FIRST}:$A${CUSTOM_LAST},C{r})>0"
        applies = (f'IF(ISERROR(FIND(":",C{r})),TRUE,INDEX(Catalogue!$H${CAT_FIRST}:$H${CAT_FIRST + 52},'
                   f'MATCH(MID(C{r},FIND(":",C{r})+1,99),Catalogue!$A${CAT_FIRST}:$A${CAT_FIRST + 52},0))="Y")')
        line_check = (f'IF(NOT({exists}),"Invalid: no such line",'
                      f'IF(B{r}="set_line_level",IF(OR(D{r}="Simple",D{r}="Standard",D{r}="Complex"),"OK","Invalid: level is Simple, Standard or Complex"),'
                      f'IF(B{r}="set_line_mode",IF(NOT(OR(D{r}="virtual",D{r}="blended",D{r}="physical")),"Invalid: mode is virtual, blended or physical",'
                      f'IF({applies},"OK","Not applicable: no mode of conduct for a document")),'
                      f'IF(B{r}="set_line_qty",IF({num}>=0,"OK","Invalid: quantity must be zero or more"),'
                      f'IF({boolok},"OK","Invalid: value must be true or false")))))')
        check = (f'=IF(B{r}="","",IF(ISNA(MATCH(B{r},{ops},0)),"Invalid: unknown op",'
                 f'IF(AND(B{r}<>"note",TRIM(E{r})=""),"Invalid: rationale required",'
                 f'IF(B{r}="note","OK",'
                 f'IF(B{r}="set_driver",IF(ISNA(MATCH(C{r},{drv_keys},0)),"Invalid: unknown driver",{driver_check}),'
                 f'IF(B{r}="set_global",IF(ISNA(MATCH(C{r},{gl},0)),"Out of scope: admin configuration",{global_check}),'
                 f'IF(B{r}="add_line",IF(OR(C{r}="global",C{r}="local"),"OK","Invalid: target is global or local"),'
                 f'{line_check})))))))')
        ws.cell(row=r, column=9, value=check)
        ws.cell(row=r, column=10, value=f'=IF(B{r}="","",B{r}&"::"&C{r})')
        ws.cell(row=r, column=11, value=f'=IF(AND(I{r}="OK",G{r}="Accepted"),1,0)')
        ws.cell(row=r, column=12, value=f'=IF(AND(I{r}="OK",OR(G{r}="Accepted",G{r}="Proposed")),1,0)')
    dv = DataValidation(type="list", formula1='"Proposed,Accepted,Rejected,Reverted,Superseded"', allow_blank=True)
    ws.add_data_validation(dv); dv.add(f"G{ADJ_FIRST}:G{ADJ_LAST}")
    dvo = DataValidation(type="list", formula1=f"={ops}", allow_blank=True)
    ws.add_data_validation(dvo); dvo.add(f"B{ADJ_FIRST}:B{ADJ_LAST}")
    ws.freeze_panes = "B6"
    return ws


# ---------------------------------------------------------------------------
# Calculation sheets
# ---------------------------------------------------------------------------

DRIVER_ROW = {}   # driver key -> row in a Calc sheet
GLOBAL_ROW = {"involvement.global": 18, "involvement.local": 19, "reviewCycles": 20,
              "localisationFactor": 21, "contingency": 22}


def build_calc(wb, data, scenario, arch_names):
    """scenario: None (baseline), 'K' (current), 'L' (preview) — the live column on Adjustments."""
    name = {None: "Calc_Baseline", "K": "Calc_Current", "L": "Calc_Preview"}[scenario]
    ws = wb.create_sheet(name)
    label = {None: "no judgement", "K": "accepted judgement", "L": "accepted plus proposed judgement"}[scenario]
    title(ws, name, f"Engine, {label}. Generated: edit inputs, not these formulas.")
    live = adj_range(scenario) if scenario else None
    keys, vals = adj_range("J"), adj_range("D")
    rows = f"ROW({keys})"

    def adj_row(key_expr):
        if not scenario:
            return "=0"
        return f"=SUMPRODUCT(MAX(({keys}={key_expr})*{live}*{rows}))"

    def adj_val(rowcell):
        return f"INDEX(Adjustments!$D:$D,{rowcell})"

    # drivers
    header_row(ws, 4, ["Driver", "Effective", "Adj row"])
    ws.column_dimensions["A"].width = 30
    for i, d in enumerate(data["drivers"]):
        r = 5 + i
        DRIVER_ROW[d["key"]] = r
        ws.cell(row=r, column=1, value=d["key"])
        ws.cell(row=r, column=3, value=adj_row(f'"set_driver::"&$A{r}'))
        base = f'IF(Inputs!$C${18 + i}="",Inputs!$D${18 + i},Inputs!$C${18 + i})'
        if d["key"] == "maturity":
            ws.cell(row=r, column=2, value=f"=IF(C{r}>0,{adj_val(f'C{r}')},{base})")
        else:
            ws.cell(row=r, column=2, value=f"=IF(C{r}>0,VALUE({adj_val(f'C{r}')}),IFERROR(VALUE({base}),Inputs!$D${18 + i}))")
    header_row(ws, 17, ["Global", "Effective", "Adj row"])
    for t, r in GLOBAL_ROW.items():
        ws.cell(row=r, column=1, value=t)
        ws.cell(row=r, column=3, value=adj_row(f'"set_global::"&$A{r}'))
        ws.cell(row=r, column=2, value=f"=IF(C{r}>0,VALUE({adj_val(f'C{r}')}),{GLOBAL_BASE_CELL[t]})")

    D = lambda k: f"$B${DRIVER_ROW[k]}"  # noqa: E731
    scalars = {
        25: ("Hours per day", "=IF(N(Inputs!$C$9)>0,Inputs!$C$9,8)"),
        26: ("Scope", "=Inputs!$C$6"),
        27: ("Default mode", '=IF(Inputs!$C$7="","blended",Inputs!$C$7)'),
        28: ("RFP analysed", '=Inputs!$C$14="Y"'),
        29: ("Localisation factor", f"=IF(N($B$21)>0,$B$21/100,Settings!$C$24/100)"),
        30: ("Review cycles", "=MIN(3,MAX(1,IF(N($B$20)>0,$B$20,1)))"),
        31: ("Our share, global", '=MIN(100,MAX(0,IF($B$18="",100,$B$18)))/100'),
        32: ("Our share, local", '=MIN(100,MAX(0,IF($B$19="",100,$B$19)))/100'),
        33: ("Buffer %", "=N($B$22)"),
        34: ("Our review per cycle", "=Settings!$C$23/100"),
        35: ("Client review per cycle", "=Settings!$C$22/100"),
        36: ("Complexity multiplier", f"=IFERROR(INDEX(Settings!$C$10:$C$14,MATCH({D('complexity')},Settings!$B$10:$B$14,0)),1)"),
        37: ("Maturity multiplier", f"=IFERROR(INDEX(Settings!$C$17:$C$19,MATCH({D('maturity')},Settings!$B$17:$B$19,0)),1)"),
        38: ("Sites", f"={D('geos')}"),
        39: ("Markets", f"=MAX(1,{D('geos')})"),
        40: ("Typical tasks per deliverable", "=Settings!$C$26"),
    }
    for r, (lab, f) in scalars.items():
        ws.cell(row=r, column=1, value=lab)
        ws.cell(row=r, column=2, value=f)

    cat = lambda c: f"Catalogue!${c}${CAT_FIRST}:${c}${CAT_FIRST + 52}"  # noqa: E731
    mode_fx = lambda m, c: f"INDEX(Settings!${c}$5:${c}$7,MATCH({m},Settings!$B$5:$B$7,0))"  # noqa: E731
    mo, wv, un, ge, md, lg, hc, hd, ss = (D(k) for k in
        ["months", "waves", "units", "geos", "modules", "languages", "hypercareMonths", "headcount", "sessionSize"])
    true_val = lambda v: f'OR(UPPER({v}&"")="TRUE",UPPER({v}&"")="Y",{v}=1)'  # noqa: E731

    # catalogue lines
    hdr = ["Line", "Stream", "Cat row", "Active", "Level", "Level adj", "Mode applies", "Mode", "Mode adj", "Effort x",
           "Capacity x", "Lib hours", "Base md/unit", "Multiplier", "Md/unit", "Auto qty", "Qty", "Qty adj", "Include",
           "Incl adj", "Option", "Opt adj", "Counted", "Mandays", "Core build", "Option build", "Our share"] + \
          [r["short"] for r in data["ranks"]] + ["Ranked"]
    header_row(ws, 44, hdr)
    for i, (lid, stream, cid, _n) in enumerate(line_ids(data)):
        r = 45 + i
        lr = LINES_FIRST + i
        f = {}
        f["A"] = f"=Lines!A{lr}"
        f["B"] = f"=Lines!B{lr}"
        f["C"] = f"=MATCH(Lines!C{lr},{cat('A')},0)"
        f["D"] = f'=OR($B$26="both",$B$26=B{r})'
        f["F"] = adj_row(f'"set_line_level::"&A{r}')
        f["E"] = f'=IF(F{r}>0,{adj_val(f"F{r}")},IF(Lines!J{lr}<>"",Lines!J{lr},INDEX({cat("R")},C{r})))'
        f["G"] = f'=INDEX({cat("H")},C{r})="Y"'
        f["I"] = adj_row(f'"set_line_mode::"&A{r}')
        f["H"] = f'=IF(G{r},IF(I{r}>0,{adj_val(f"I{r}")},IF(Lines!K{lr}<>"",Lines!K{lr},$B$27)),"")'
        f["J"] = f'=IF(H{r}="",1,{mode_fx(f"H{r}", "C")})'
        f["K"] = f'=IF(H{r}="",1,{mode_fx(f"H{r}", "D")})'
        f["L"] = (f'=IF(E{r}="Simple",INDEX({cat("L")},C{r}),IF(E{r}="Standard",INDEX({cat("M")},C{r}),INDEX({cat("N")},C{r})))')
        f["M"] = f'=IF(L{r}>0,L{r}/$B$25,IF(INDEX({cat("S")},C{r})>0,INDEX({cat("S")},C{r}),5))'
        f["N"] = f'=$B$36*$B$37*IF(AND(INDEX({cat("G")},C{r})="Y",$B$38>1,B{r}="global"),MIN(1.5,1+0.07*($B$38-1)),1)'
        f["O"] = f'=ROUND(M{r}*IF(B{r}="local",$B$29,1)*N{r}*J{r},1)'
        rules = [
            "1", "2", f"MAX(1,{mo})", f"MAX(2,{mo}*2)", f"MAX(2,ROUND({mo}/3,0))", f"MAX(4,ROUND({mo}*4.33,0))",
            f"MAX(1,{wv})", f"MAX(2,{wv}*2)", f"MAX(1,{un})", f"MAX(2,{un})", f"MAX(1,{ge})", f"MAX(1,{md})",
            f"MAX(2,ROUND({md}/2,0))", f"MAX(1,ROUND({md}/3,0))", f"MAX(0,{md}*MAX(0,{lg}-1))", f"MAX(6,{mo}*2)",
            f"MAX(2,{hc}*2)", f"MAX(1,CEILING(CEILING({hd}/50,1)/MAX(1,12*K{r}),1))",
            f"MAX(1,CEILING({hd}/MAX(1,IF(N({ss})=0,20,{ss})*K{r}),1))"]
        rule_cell = f"INDEX({cat('E')},C{r})"
        f["P"] = (f'=MAX(0,ROUND(CHOOSE(MATCH({rule_cell},Settings!$F$5:$F${4 + len(QTY_RULE_ORDER)},0),{",".join(rules)}),0))'
                  f'*IF(AND(B{r}="local",{rule_cell}<>"geos"),$B$39,1)')
        f["R"] = adj_row(f'"set_line_qty::"&A{r}')
        f["Q"] = f'=IF(R{r}>0,VALUE({adj_val(f"R{r}")}),IF(Lines!I{lr}<>"",Lines!I{lr},P{r}))'
        f["T"] = adj_row(f'"set_line_include::"&A{r}')
        core = f'INDEX({cat("F")},C{r})="Y"'
        f["S"] = (f'=IF(T{r}>0,{true_val(adj_val(f"T{r}"))},IF(Lines!H{lr}<>"",Lines!H{lr}="Y",'
                  f'IF($B$28,OR(Lines!E{lr}="Y",{core}),{core})))')
        f["V"] = adj_row(f'"set_line_optional::"&A{r}')
        f["U"] = f'=IF(V{r}>0,{true_val(adj_val(f"V{r}"))},IF(Lines!L{lr}<>"",Lines!L{lr}="Y",Lines!F{lr}="Y"))'
        f["W"] = f"=AND(D{r},S{r})"
        f["X"] = f"=IF(W{r},Q{r}*O{r},0)"
        f["Y"] = f"=IF(AND(W{r},NOT(U{r})),X{r},0)"
        f["Z"] = f"=IF(AND(W{r},U{r}),X{r},0)"
        f["AA"] = f'=IF(B{r}="local",$B$32,$B$31)'
        for k in range(7):
            # Catalogue rank columns run T.. (Simple r1..r7, Standard r1..r7, Complex r1..r7)
            rc = lambda off: f"INDEX({cat(col(20 + off * 7 + k))},C{r})"  # noqa: E731
            share = f'IF(E{r}="Simple",{rc(0)},IF(E{r}="Standard",{rc(1)},{rc(2)}))'
            f[col(28 + k)] = f"=IF(OR(Y{r}=0,L{r}=0),0,Y{r}*AA{r}*{share}/L{r})"
        f["AI"] = f"=IF(AND(Y{r}>0,L{r}>0),Y{r}*AA{r},0)"
        for c, v in f.items():
            ws[f"{c}{r}"] = v

    # custom lines
    chdr = ["Line", "Stream", "Live", "Active", "Level", "Level adj", "Mode", "Mode adj", "Effort x", "Arch row",
            "Hours / task", "Md/unit", "Qty", "Qty adj", "Include", "Incl adj", "Option", "Opt adj", "Counted",
            "Mandays", "Core build", "Option build", "Our share"] + [r["short"] for r in data["ranks"]] + ["Ranked"]
    header_row(ws, 154, chdr)
    arch_last = ARCH_FIRST + len(arch_names) - 1
    for i in range(CUSTOM_LAST - CUSTOM_FIRST + 1):
        r = 155 + i
        cr = CUSTOM_FIRST + i
        src = f"'Custom lines'!J{cr}"
        if scenario:
            live_src = f"SUMPRODUCT(({adj_range('A')}={src})*{live})>0"
        else:
            live_src = "FALSE"
        f = {}
        f["A"] = f"='Custom lines'!A{cr}&\"\""
        f["B"] = f"='Custom lines'!B{cr}&\"\""
        f["C"] = f'=AND(A{r}<>"",OR({src}="",{live_src}))'
        f["D"] = f'=AND(C{r},OR($B$26="both",$B$26=B{r}))'
        f["F"] = adj_row(f'"set_line_level::"&A{r}')
        f["E"] = f"=IF(F{r}>0,{adj_val(f'F{r}')},IF('Custom lines'!E{cr}=\"\",\"Standard\",'Custom lines'!E{cr}))"
        f["H"] = adj_row(f'"set_line_mode::"&A{r}')
        f["G"] = f"=IF(H{r}>0,{adj_val(f'H{r}')},'Custom lines'!F{cr}&\"\")"
        f["I"] = f'=IF(G{r}="",1,{mode_fx(f"G{r}", "C")})'
        f["J"] = f"=IFERROR(MATCH('Custom lines'!D{cr},Archetypes!$A${ARCH_FIRST}:$A${arch_last},0),1)"
        lvl_col = {"Simple": "B", "Standard": "C", "Complex": "D"}

        def clamp_custom(level):
            cells = [f"INDEX(Archetypes!${lvl_col[l]}${ARCH_FIRST}:${lvl_col[l]}${arch_last},J{r})" for l in CLAMP_ORDER[level]]
            expr = "6"
            for c in reversed(cells):
                expr = f"IF(N({c})>0,{c},{expr})"
            return expr
        f["K"] = f'=IF(E{r}="Simple",{clamp_custom("Simple")},IF(E{r}="Complex",{clamp_custom("Complex")},{clamp_custom("Standard")}))'
        f["L"] = f'=ROUND((K{r}*$B$40/$B$25)*($B$36*$B$37)*I{r}*IF(B{r}="local",$B$29,1),1)'
        f["N"] = adj_row(f'"set_line_qty::"&A{r}')
        f["M"] = f"=IF(N{r}>0,VALUE({adj_val(f'N{r}')}),N('Custom lines'!G{cr}))"
        f["P"] = adj_row(f'"set_line_include::"&A{r}')
        f["O"] = f"=IF(P{r}>0,{true_val(adj_val(f'P{r}'))},'Custom lines'!H{cr}<>\"N\")"
        f["R"] = adj_row(f'"set_line_optional::"&A{r}')
        f["Q"] = f"=IF(R{r}>0,{true_val(adj_val(f'R{r}'))},'Custom lines'!I{cr}=\"Y\")"
        f["S"] = f"=AND(D{r},O{r})"
        f["T"] = f"=IF(S{r},M{r}*L{r},0)"
        f["U"] = f"=IF(AND(S{r},NOT(Q{r})),T{r},0)"
        f["V"] = f"=IF(AND(S{r},Q{r}),T{r},0)"
        f["W"] = f'=IF(B{r}="local",$B$32,$B$31)'
        for k in range(7):
            share = f"INDEX(Archetypes!${col(13 + k)}${ARCH_FIRST}:${col(13 + k)}${arch_last},J{r})"
            f[col(24 + k)] = f"=IF(OR(U{r}=0,K{r}=0),0,U{r}*W{r}*{share})"
        f["AE"] = f"=IF(AND(U{r}>0,K{r}>0),U{r}*W{r},0)"
        for c, v in f.items():
            ws[f"{c}{r}"] = v

    # totals
    L1, L2 = 45, 150
    C1, C2 = 155, 194
    header_row(ws, 199, ["Stream", "Build (all)", "Option build", "Our share", "Our build", "Our review", "Client build",
                         "Client review", "Our total", "Client total", "Our options"])
    for i, s in enumerate(["global", "local"]):
        r = 200 + i
        ws.cell(row=r, column=1, value=s)
        ws.cell(row=r, column=2, value=f'=SUMIFS($Y${L1}:$Y${L2},$B${L1}:$B${L2},A{r})+SUMIFS($U${C1}:$U${C2},$B${C1}:$B${C2},A{r})')
        ws.cell(row=r, column=3, value=f'=SUMIFS($Z${L1}:$Z${L2},$B${L1}:$B${L2},A{r})+SUMIFS($V${C1}:$V${C2},$B${C1}:$B${C2},A{r})')
        ws.cell(row=r, column=4, value=f'=IF(A{r}="local",$B$32,$B$31)')
        ws.cell(row=r, column=5, value=f"=B{r}*D{r}")
        ws.cell(row=r, column=6, value=f"=B{r}*$B$34*$B$30")
        ws.cell(row=r, column=7, value=f"=B{r}-E{r}")
        ws.cell(row=r, column=8, value=f"=B{r}*$B$35*$B$30")
        ws.cell(row=r, column=9, value=f"=E{r}+F{r}")
        ws.cell(row=r, column=10, value=f"=G{r}+H{r}")
        ws.cell(row=r, column=11, value=f"=C{r}*D{r}+C{r}*$B$34*$B$30")
    T = {
        204: ("Our effort before buffer", "=SUM(I200:I201)"),
        205: ("Delivery buffer", "=B204*$B$33/100"),
        206: ("Our total effort (mandays)", "=B204+B205"),
        207: ("Client effort", "=SUM(J200:J201)"),
        208: ("Options, quoted separately", "=SUM(K200:K201)"),
        209: ("Our review", "=SUM(F200:F201)"),
        210: ("Ranked effort before review", f"=SUM(AI{L1}:AI{L2})+SUM(AE{C1}:AE{C2})"),
        211: ("Average FTE", f"=IF({mo}>0,B206/({mo}*21),0)"),
        212: ("Months", f"={mo}"),
        213: ("Deliverables in estimate",
              f"=SUMPRODUCT(($W${L1}:$W${L2}=TRUE)*($U${L1}:$U${L2}=FALSE))"
              f"+SUMPRODUCT(($S${C1}:$S${C2}=TRUE)*($Q${C1}:$Q${C2}=FALSE))"),
    }
    for r, (lab, fx) in T.items():
        ws.cell(row=r, column=1, value=lab)
        ws.cell(row=r, column=2, value=fx)
    header_row(ws, 215, ["Rank", "Mandays"])
    for k, rk in enumerate(data["ranks"]):
        r = 216 + k
        lc, cc = col(28 + k), col(24 + k)
        ws.cell(row=r, column=1, value=rk["name"])
        ws.cell(row=r, column=2, value=f"=(SUM({lc}{L1}:{lc}{L2})+SUM({cc}{C1}:{cc}{C2}))*IF(AND($B$210>0,$B$209>0),1+$B$209/$B$210,1)")
    ws.sheet_state = "hidden" if scenario is None else "visible"
    return ws


def build_summary(wb, data):
    ws = wb.create_sheet("Summary", 0)
    title(ws, "CM Effort Estimator v0.5", "Effort in mandays. Baseline = no judgement; Current = accepted judgement; Preview = accepted plus proposed.")
    ws.column_dimensions["A"].width = 38
    for c in "BCDE":
        ws.column_dimensions[c].width = 14
    header_row(ws, 4, ["", "Baseline", "Current", "Preview", "Preview - Current"])
    rows = [("Our total effort (mandays)", 206), ("Our effort before buffer", 204), ("Delivery buffer", 205),
            ("Client effort", 207), ("Options, quoted separately", 208), ("Average FTE", 211), ("Months", 212),
            ("Deliverables in estimate", 213)]
    for i, (lab, src) in enumerate(rows):
        r = 5 + i
        ws.cell(row=r, column=1, value=lab).font = font(bold=(i == 0))
        for j, sh in enumerate(["Calc_Baseline", "Calc_Current", "Calc_Preview"]):
            c = ws.cell(row=r, column=2 + j, value=f"=ROUND({sh}!B{src},1)")
            c.number_format = "#,##0.0"
            if i == 0:
                c.font = font(bold=True, size=12)
        ws.cell(row=r, column=5, value=f"=ROUND(D{r}-C{r},1)").number_format = "+#,##0.0;-#,##0.0;-"
    ws["A15"] = "Judgement moved the estimate by"
    ws["C15"] = "=IF(B5>0,(C5-B5)/B5,0)"
    ws["C15"].number_format = "+0.0%;-0.0%;0.0%"
    ws["A16"] = "Warning"
    ws["B16"] = ('=IF(ABS(C15)>Settings!$C$25,"Accepted judgement has moved the estimate by more than "&'
                 'TEXT(Settings!$C$25,"0%")&" of its baseline. Still computes; worth a second look before it goes to the client.","")')
    ws["B16"].font = font(bold=True, color="8C5E0C")
    ws["A17"] = "Adjustments needing attention"
    ws["C17"] = f'=COUNTIFS(Adjustments!$I${ADJ_FIRST}:$I${ADJ_LAST},"Invalid*")+COUNTIFS(Adjustments!$I${ADJ_FIRST}:$I${ADJ_LAST},"Out of scope*")+COUNTIFS(Adjustments!$I${ADJ_FIRST}:$I${ADJ_LAST},"Not applicable*")'

    header_row(ws, 19, ["Stream (current)", "Build, all parties", "Our share", "Our review", "Our total"])
    for i, s in enumerate(["global", "local"]):
        r = 20 + i
        ws.cell(row=r, column=1, value=s)
        for j, c in enumerate(["B", "D", "F", "I"]):
            cell = ws.cell(row=r, column=2 + j, value=f"=Calc_Current!{c}{200 + i}")
            cell.number_format = "0%" if c == "D" else "#,##0.0"
    header_row(ws, 23, ["Effort by rank (current)", "Mandays"])
    for k, rk in enumerate(reversed(data["ranks"])):
        idx = len(data["ranks"]) - 1 - k
        r = 24 + k
        ws.cell(row=r, column=1, value=rk["name"])
        ws.cell(row=r, column=2, value=f"=ROUND(Calc_Current!B{216 + idx},1)").number_format = "#,##0.0"
    ws["A33"] = ("Effort only. Any commercial number (price, rate, discount, tax) is produced separately. "
                 "Hours library values are placeholder norms until calibrated against past-project actuals.")
    ws["A33"].font = font(italic=True, color="7A8494")
    return ws


def build_readme(wb):
    ws = wb.create_sheet("How to use", 1)
    title(ws, "How to use this workbook", "The Copilot agent proposes; this workbook computes and keeps the record.")
    ws.column_dimensions["A"].width = 110
    lines = [
        "1. Inputs: set scope, engagement settings and drivers in the yellow cells. Blank driver = default assumed.",
        "2. Lines: the agent's Lines!E6 block sets RFP signals, client terms and any hand overrides for the 106 deliverable lines.",
        "3. Custom lines: deliverables the catalogue lacks. Rows with a Source adjustment ID only count while that adjustment is accepted.",
        "4. Adjustments: paste the agent's proposals with Status = Proposed. Summary's Preview column shows the effect.",
        "   Set each row to Accepted or Rejected. To revert later, set Reverted. Never delete a row: it is the audit trail.",
        "   The Check column refuses malformed rows and anything aimed at admin configuration; those never move a number.",
        "5. Summary: Baseline (no judgement), Current (accepted), Preview (accepted plus proposed), the warning, team shape.",
        "",
        "Pasting a TSV block: click the named cell (e.g. Adjustments!A6), paste. Excel splits tabs into columns.",
        "Admin sheets (Settings, Archetypes, Library, Catalogue, Past projects) reprice every estimate: CoE owner only.",
        "Calc_* sheets are generated formulas. Edit inputs, never the Calc sheets.",
    ]
    for i, t in enumerate(lines):
        ws.cell(row=4 + i, column=1, value=t)
    return ws


def build_state(wb):
    ws = wb.create_sheet("State")
    title(ws, "Estimate state", "The agent's export puts the whole estimate in A6. To resume in a new chat, copy A6 and paste it to the agent.")
    ws.column_dimensions["A"].width = 120
    ws["A5"] = "State (JSON, generated by the agent: do not edit by hand)"
    ws["A5"].font = font(bold=True)
    mark_input(ws["A6"])
    ws["A6"].alignment = Alignment(wrap_text=False)
    return ws


def build_workbook(data, path):
    wb = Workbook()
    wb.remove(wb.active)
    build_settings(wb, data)
    _arch, arch_names = build_archetypes(wb, data)
    _lib, lib_last = build_library(wb, data, arch_names)
    build_catalogue(wb, data, lib_last)
    build_quotes(wb, data)
    build_inputs(wb, data)
    build_lines(wb, data)
    build_custom(wb, data, arch_names)
    build_adjustments(wb, data)
    build_calc(wb, data, None, arch_names)
    build_calc(wb, data, "K", arch_names)
    build_calc(wb, data, "L", arch_names)
    build_summary(wb, data)
    build_readme(wb)
    build_state(wb)
    order = ["Summary", "How to use", "Inputs", "Lines", "Custom lines", "Adjustments", "State", "Settings", "Archetypes",
             "Library", "Catalogue", "Past projects", "Calc_Baseline", "Calc_Current", "Calc_Preview"]
    wb._sheets = [wb[n] for n in order]
    # Arial throughout, keeping each cell's weight, slant and colour.
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None and c.font.name != FONT and c.row > 2:
                    f = copy(c.font)
                    f.name = FONT
                    c.font = f
    wb["Summary"]["A5"].comment = Comment("Same inputs, same number as the Copilot skill and the web artifact: "
                                          "all three run the same rules.", "CM CoE")
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
