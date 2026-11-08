#!/usr/bin/env python
"""Generate mock messy PDF data-dictionary docs from the schema JSON.

Mirrors generate_docs.py (same messiness) but outputs PDF via reportlab,
using the local Microsoft YaHei font for Chinese. One PDF per schema plus
a whole-database table-list overview.

Output: data/mock_docs/pdf/{cn}_{schema}_数据字典.pdf
        data/mock_docs/pdf/全库表清单.pdf
"""
import json
import os
import random
import zlib

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCHEMA_JSON = os.path.join(ROOT, "data", "adventureworks_schema.json")
OUT_DIR = os.path.join(ROOT, "data", "mock_docs", "pdf")

SCHEMA_CN = {"person": "人员", "humanresources": "人力资源",
             "production": "生产制造", "purchasing": "采购", "sales": "销售"}

HEADER_SETS = [
    ("字段名", "数据类型", "可空", "字段说明"),
    ("Column", "Type", "Nullable", "Description"),
    ("字段 Field", "类型 Type", "可空", "说明 Remarks"),
]

pdfmetrics.registerFont(TTFont("MSYH", r"C:\Windows\Fonts\msyh.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("MSYH-Bold", r"C:\Windows\Fonts\msyhbd.ttc", subfontIndex=0))

ST_TITLE = ParagraphStyle("title", fontName="MSYH-Bold", fontSize=20, leading=26, spaceAfter=6)
ST_SUB = ParagraphStyle("sub", fontName="MSYH", fontSize=9.5, leading=14, textColor=colors.grey)
ST_H2 = ParagraphStyle("h2", fontName="MSYH-Bold", fontSize=13, leading=17,
                       spaceBefore=12, spaceAfter=4)
ST_BODY = ParagraphStyle("body", fontName="MSYH", fontSize=9, leading=13, spaceAfter=3)
ST_CELL = ParagraphStyle("cell", fontName="MSYH", fontSize=8.5, leading=11, alignment=TA_LEFT)
ST_HEAD = ParagraphStyle("head", fontName="MSYH-Bold", fontSize=8.5, leading=11)


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
    pk, fk = {}, {}
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
    d = (c.get("description") or "").strip().replace("\n", " ")
    if d:
        return d + ann
    return ("业务字段" + ann) if tags else ("待补充" if rng.random() < 0.5 else "")


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def seed_of(s):
    return zlib.crc32(s.encode("utf-8")) & 0xffffffff


def footer(canvas, docobj):
    canvas.saveState()
    canvas.setFont("MSYH", 7.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(36, 20, "模拟文档（基于 AdventureWorks 公开示例库生成，非真实公司数据）")
    canvas.drawRightString(A4[0] - 36, 20, f"第 {docobj.page} 页")
    canvas.restoreState()


def build_doc(tables, out_path, title, subtitle, pk, fk, overview=False):
    doc = SimpleDocTemplate(out_path, pagesize=A4, topMargin=20 * mm,
                            bottomMargin=18 * mm, leftMargin=36, rightMargin=36,
                            title=title, author="schema-doc-generator")
    story = [Paragraph(esc(title), ST_TITLE), Paragraph(esc(subtitle), ST_SUB), Spacer(1, 8)]

    if overview:
        data = [[Paragraph(h, ST_HEAD) for h in ("模块", "表名", "表说明", "字段数", "行数")]]
        for t in tables:
            data.append([Paragraph(esc(SCHEMA_CN.get(t["schema"], t["schema"])), ST_CELL),
                         Paragraph(esc(t["full_name"]), ST_CELL),
                         Paragraph(esc(t.get("comment") or ""), ST_CELL),
                         Paragraph(str(len(t["columns"])), ST_CELL),
                         Paragraph(str(t["row_count"]), ST_CELL)])
        widths = [50, 150, 235, 45, 55]
        tb = Table(data, colWidths=widths, repeatRows=1)
        tb.setStyle(_style())
        story.append(tb)
    else:
        for t in tables:
            rng = random.Random(seed_of(t["full_name"]))
            style = rng.choice(["lower", "upper", "cap"])
            hdr = rng.choice(HEADER_SETS)
            full = t["full_name"]
            story.append(Paragraph(
                f"{esc(table_display(t, rng.choice(['cap','cn_en','upper'])))}  ({esc(full)})", ST_H2))
            if t.get("comment"):
                story.append(Paragraph(f"表说明：{esc(t['comment'])}", ST_BODY))
            rows = [[Paragraph(h, ST_HEAD) for h in hdr]]
            for c in t["columns"]:
                rows.append([
                    Paragraph(esc(disp_col(c["name"], style)), ST_CELL),
                    Paragraph(esc(fmt_type(c)), ST_CELL),
                    Paragraph("是" if c["nullable"] else "否", ST_CELL),
                    Paragraph(esc(make_desc(c, c["name"] in pk[full], fk[full].get(c["name"]), rng)), ST_CELL),
                ])
            widths = [150, 105, 45, 223]
            tb = Table(rows, colWidths=widths, repeatRows=1)
            tb.setStyle(_style())
            story.append(tb)
            story.append(Spacer(1, 4))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def _style():
    return TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0B7C3")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDEBF7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ])


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
        p = os.path.join(OUT_DIR, f"{cn}_{sch}_数据字典.pdf")
        build_doc(tables, p, f"{cn}模块 数据字典（{sch}）",
                  "说明：本文件由系统导出，部分字段业务含义尚未补充，请以数据库为准。",
                  pk, fk)
        made.append(p)
        print(f"  {sch}: {len(tables)} tables -> {os.path.basename(p)}")

    p = os.path.join(OUT_DIR, "全库表清单.pdf")
    build_doc(doc["tables"], p, "全库表清单（AdventureWorks）",
              f"共 {doc['table_count']} 张表，覆盖 person / humanresources / production / purchasing / sales 五个模块。",
              pk, fk, overview=True)
    made.append(p)
    print(f"  overview: {doc['table_count']} tables -> {os.path.basename(p)}")
    print(f"\nGenerated {len(made)} PDFs in {OUT_DIR}")


if __name__ == "__main__":
    main()
