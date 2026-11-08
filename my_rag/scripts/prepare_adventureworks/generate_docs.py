#!/usr/bin/env python
"""Generate mock messy Word/Excel data-dictionary docs from the schema JSON.

Simulates a real company's inconsistent field documentation:
 - one Word doc per schema (module) + one Excel workbook per schema
 - multiple sheets per Excel, merged title cells
 - inconsistent naming (lower/upper/Capitalized), mixed CN/EN headers
 - ~30% of field descriptions dropped; PK/FK annotated in Chinese
Deterministic (seed) so output is reproducible.
"""
import json
import os
import random
import re

from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCHEMA_JSON = os.path.join(ROOT, "data", "adventureworks_schema.json")
OUT_DIR = os.path.join(ROOT, "data", "mock_docs")

SCHEMA_CN = {"person": "人员", "humanresources": "人力资源",
             "production": "生产制造", "purchasing": "采购", "sales": "销售"}

HEADER_SETS = [
    ("字段名", "数据类型", "可空", "字段说明"),
    ("Column", "Type", "Nullable", "Description"),
    ("字段 Field", "类型 Type", "可空", "说明 Remarks"),
]


def load_schema():
    with open(SCHEMA_JSON, encoding="utf-8") as f:
        return json.load(f)


def fmt_type(c):
    dt = c["data_type"]
    if dt in ("character varying", "character") and c.get("max_length"):
        return f"{dt}({c['max_length']})"
    if dt == "numeric" and c.get("numeric_precision"):
        return f"numeric({c['numeric_precision']},{c['numeric_scale']})"
    return dt


def disp_col(name, style):
    if style == "upper":
        return name.upper()
    if style == "cap":
        return name[:1].upper() + name[1:]
    return name


def table_display(t, style):
    name = t["name"]
    cn = SCHEMA_CN.get(t["schema"], t["schema"])
    if style == "upper":
        return name.upper()
    if style == "cap":
        return name[:1].upper() + name[1:]
    if style == "cn_en":
        return f"{cn}-{name}"
    return name


def build_indexes(doc):
    pk = {}
    fk = {}
    for t in doc["tables"]:
        key = t["full_name"]
        pk[key] = set((t["primary_key"] or {}).get("columns") or [])
        m = {}
        for f in t["foreign_keys"]:
            for lc in f["columns"]:
                m[lc] = f"{f['references']['table']}.{f['references']['columns'][0]}"
        fk[key] = m
    return pk, fk


def make_desc(c, is_pk, fk_ref, rng):
    if rng.random() < 0.30:
        return ""
    tags = []
    if is_pk:
        tags.append("主键")
    if fk_ref:
        tags.append(f"外键→{fk_ref}")
    ann = ("（" + "；".join(tags) + "）") if tags else ""
    d = (c.get("description") or "").strip()
    if d:
        return d + ann
    return ("业务字段" + ann) if tags else ("待补充" if rng.random() < 0.5 else "")


def gen_word(doc, tables, pk, fk, out_path):
    d = Document()
    sch = tables[0]["schema"]
    cn = SCHEMA_CN.get(sch, sch)
    d.add_heading(f"{cn}模块 数据字典（{sch}）", level=0)
    d.add_paragraph("说明：本文件由系统整理导出，部分字段的业务含义尚未补充，请以数据库为准。")

    for t in tables:
        rng = random.Random(hash(t["full_name"]) & 0xffffffff)
        style = rng.choice(["lower", "upper", "cap"])
        hdr = rng.choice(HEADER_SETS)
        full = t["full_name"]
        d.add_heading(f"{table_display(t, rng.choice(['cap','cn_en','upper']))}  ({full})", level=2)
        if t.get("comment"):
            d.add_paragraph(f"表说明：{t['comment']}")

        cols = t["columns"]
        ncol = 4
        table = d.add_table(rows=2, cols=ncol)
        table.style = "Table Grid"
        # merged title row
        merged = table.cell(0, 0).merge(table.cell(0, ncol - 1))
        merged.text = f"{full}  共 {len(cols)} 个字段，约 {t['row_count']} 行"

        for j, h in enumerate(hdr):
            cell = table.cell(1, j)
            cell.text = h
            for p in cell.paragraphs:
                for r in p.runs:
                    r.bold = True
        for c in cols:
            row = table.add_row().cells
            row[0].text = disp_col(c["name"], style)
            row[1].text = fmt_type(c)
            row[2].text = "是" if c["nullable"] else "否"
            row[3].text = make_desc(c, c["name"] in pk[full], fk[full].get(c["name"]), rng)
    d.save(out_path)


def gen_excel(doc, tables, pk, fk, out_path):
    wb = Workbook()
    ws0 = wb.active
    ws0.title = "目录"
    ws0.merge_cells("A1:D1")
    ws0["A1"] = f"{SCHEMA_CN.get(tables[0]['schema'], '')}模块 字段清单（共 {len(tables)} 张表）"
    ws0["A1"].font = Font(bold=True, size=13)
    ws0.append(["序号", "表名", "表说明", "行数"])

    used = {"目录"}
    for i, t in enumerate(tables, 1):
        rng = random.Random((hash(t["full_name"]) ^ 0x9e37) & 0xffffffff)
        full = t["full_name"]
        style = rng.choice(["lower", "upper", "cap"])
        hdr = rng.choice(HEADER_SETS)
        include_desc = rng.random() > 0.25          # some sheets omit description column
        order = [0, 1, 2, 3]
        if rng.random() < 0.4:                       # reorder columns sometimes
            order = [0, 2, 1, 3]

        # sheet name (<=31 chars, unique)
        base = re.sub(r"[\[\]:*?/\\]", "_", t["name"])[:28]
        sname = base
        k = 1
        while sname in used:
            k += 1
            sname = f"{base[:28-len(str(k))]}_{k}"
        used.add(sname)
        ws = wb.create_sheet(sname)

        headers = list(hdr)
        if not include_desc:
            headers = headers[:3]
        ncol = len(headers)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
        ws.cell(1, 1, f"{table_display(t, rng.choice(['cap','cn_en']))} ({full}) — {t.get('comment') or ''}")
        ws.cell(1, 1).font = Font(bold=True, size=12)
        ws.cell(1, 1).alignment = Alignment(horizontal="center")
        for j, h in enumerate(headers, 1):
            cell = ws.cell(2, j, h)
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DDEBF7")
        r = 3
        for c in t["columns"]:
            vals = [disp_col(c["name"], style), fmt_type(c), "Y" if c["nullable"] else "N",
                    make_desc(c, c["name"] in pk[full], fk[full].get(c["name"]), rng)]
            shown = [vals[k] for k in order if include_desc or k != 3]
            for j, v in enumerate(shown, 1):
                ws.cell(r, j, v)
            r += 1
        ws.column_dimensions["A"].width = 26
        ws.column_dimensions["B"].width = 24
        ws.column_dimensions["C"].width = 10
        if include_desc:
            ws.column_dimensions["D"].width = 55
        ws0.append([i, table_display(t, "cap"), t.get("comment") or "", t["row_count"]])

    wb.save(out_path)


def main():
    doc = load_schema()
    pk, fk = build_indexes(doc)
    os.makedirs(OUT_DIR, exist_ok=True)
    by_schema = {}
    for t in doc["tables"]:
        by_schema.setdefault(t["schema"], []).append(t)

    made = []
    for sch, tables in by_schema.items():
        cn = SCHEMA_CN.get(sch, sch)
        wpath = os.path.join(OUT_DIR, f"{cn}_{sch}_数据字典.docx")
        xpath = os.path.join(OUT_DIR, f"{cn}_{sch}_字段清单.xlsx")
        gen_word(doc, tables, pk, fk, wpath)
        gen_excel(doc, tables, pk, fk, xpath)
        made += [wpath, xpath]
        print(f"  {sch}: {len(tables)} tables -> {os.path.basename(wpath)}, {os.path.basename(xpath)}")
    print(f"\nGenerated {len(made)} files in {OUT_DIR}")


if __name__ == "__main__":
    main()
