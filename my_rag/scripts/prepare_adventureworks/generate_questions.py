#!/usr/bin/env python
"""Auto-generate ground-truth test questions from the schema JSON.

Question types (answer derivable deterministically from the DB/schema):
  - field_reverse : which tables contain a given column (exact set)
  - primary_key   : a table's primary key column(s)
  - join_path     : BFS shortest FK path between two tables
  - field_meaning : which table.column records a given business description
  - column_type   : data type of a given table.column
  - row_count     : exact row count of a table (deterministic SQL)
  - schema_tables : tables belonging to a module/schema
  - schema_of     : which schema/module a table belongs to
Output: data/eval/ground_truth_questions.jsonl
"""
import json
import os
import random
from collections import deque, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCHEMA_JSON = os.path.join(ROOT, "data", "adventureworks_schema.json")
OUT_DIR = os.path.join(ROOT, "data", "eval")
OUT = os.path.join(OUT_DIR, "ground_truth_questions.jsonl")

SCHEMA_CN = {"person": "人员", "humanresources": "人力资源",
             "production": "生产制造", "purchasing": "采购", "sales": "销售"}


def load():
    with open(SCHEMA_JSON, encoding="utf-8") as f:
        return json.load(f)


def fmt_type(c):
    dt = c["data_type"]
    if dt in ("character varying", "character") and c.get("max_length"):
        return f"{dt}({c['max_length']})"
    if dt == "numeric" and c.get("numeric_precision"):
        return f"numeric({c['numeric_precision']},{c['numeric_scale']})"
    return dt


def build_graph(doc):
    """Undirected FK graph: table -> list of (neighbor, from_col, to_col)."""
    g = defaultdict(list)
    for t in doc["tables"]:
        src = t["full_name"]
        for f in t["foreign_keys"]:
            dst = f"{f['references']['schema']}.{f['references']['table']}"
            lc = f["columns"][0]
            rc = f["references"]["columns"][0]
            g[src].append((dst, lc, rc))
            g[dst].append((src, rc, lc))
    return g


def bfs_path(g, start, goal):
    if start == goal:
        return []
    q = deque([(start, [])])
    seen = {start}
    while q:
        node, path = q.popleft()
        for nb, lc, rc in g[node]:
            if nb in seen:
                continue
            step = {"from": node, "from_col": lc, "to": nb, "to_col": rc}
            if nb == goal:
                return path + [step]
            seen.add(nb)
            q.append((nb, path + [step]))
    return None


def main():
    doc = load()
    tables = doc["tables"]
    by_full = {t["full_name"]: t for t in tables}
    rng = random.Random(20261104)

    # column -> list of full tables containing it
    col_tables = defaultdict(list)
    for t in tables:
        for c in t["columns"]:
            col_tables[c["name"]].append(t["full_name"])

    # description -> list of (full, col)
    desc_index = defaultdict(list)
    for t in tables:
        for c in t["columns"]:
            d = (c.get("description") or "").strip()
            if d:
                desc_index[d].append((t["full_name"], c["name"]))

    g = build_graph(doc)
    questions = []
    qid = 0

    def add(qtype, q, answer, atype, diff, notes=""):
        nonlocal qid
        qid += 1
        questions.append({
            "id": f"q{qid:03d}", "type": qtype, "question": q,
            "answer": answer, "answer_type": atype,
            "difficulty": diff, "notes": notes,
        })

    # 1) field_reverse — columns present in >=3 tables
    common = sorted([(col, ts) for col, ts in col_tables.items() if len(ts) >= 3],
                    key=lambda x: (-len(x[1]), x[0]))[:18]
    for col, ts in common:
        ans = sorted(ts)
        add("field_reverse", f"哪些表包含名为 {col} 的字段？（请列出全部）",
            ans, "table_list", "hard" if len(ans) >= 5 else "medium",
            f"共 {len(ans)} 张表")

    # 2) primary_key — all tables
    for t in tables:
        pk = (t["primary_key"] or {}).get("columns") or []
        if pk:
            add("primary_key", f"表 {t['full_name']} 的主键是什么？",
                pk, "column_list", "easy")

    # 3) column_type — sample
    all_cols = [(t["full_name"], c) for t in tables for c in t["columns"]]
    for full, c in rng.sample(all_cols, 20):
        add("column_type", f"字段 {full}.{c['name']} 的数据类型是什么？",
            fmt_type(c), "string", "easy")

    # 4) field_meaning — unique descriptions only
    unique_desc = [(d, locs) for d, locs in desc_index.items()
                   if len(locs) == 1 and len(d) >= 20]
    for d, locs in rng.sample(unique_desc, min(22, len(unique_desc))):
        full, col = locs[0]
        add("field_meaning",
            f"哪个字段的说明是：『{d}』？请给出所在表和字段名。",
            {"table": full, "column": col}, "table_column", "medium")

    # 5) join_path — cross/interesting pairs
    names = list(by_full.keys())
    pairs = [
        ("sales.salesorderheader", "person.person"),
        ("sales.salesorderdetail", "production.product"),
        ("sales.customer", "sales.salesterritory"),
        ("humanresources.employee", "sales.salesperson"),
        ("purchasing.purchaseorderheader", "person.person"),
        ("production.product", "production.productsubcategory"),
        ("sales.salesorderheader", "sales.creditcard"),
        ("person.person", "humanresources.employee"),
        ("production.workorder", "production.product"),
        ("purchasing.vendor", "person.businessentity"),
        ("sales.salesperson", "person.person"),
        ("production.productinventory", "production.location"),
    ]
    for a, b in pairs:
        if a not in by_full or b not in by_full:
            continue
        path = bfs_path(g, a, b)
        if not path:
            continue
        # normalize: represent as list of join steps with direction
        steps = [{"left": s["from"], "left_col": s["from_col"],
                  "right": s["to"], "right_col": s["to_col"]} for s in path]
        add("join_path",
            f"从表 {a} 查询到表 {b} 的数据，需要经过哪些表、用哪些字段做关联？（给出最短连接路径）",
            {"from": a, "to": b, "hops": len(path), "steps": steps},
            "join_path", "hard" if len(path) > 1 else "medium")

    # extra random reachable pairs for breadth
    extra = 0
    tries = 0
    while extra < 8 and tries < 400:
        tries += 1
        a, b = rng.sample(names, 2)
        if (a, b) in pairs or (b, a) in pairs:
            continue
        path = bfs_path(g, a, b)
        if path and 1 <= len(path) <= 3:
            steps = [{"left": s["from"], "left_col": s["from_col"],
                      "right": s["to"], "right_col": s["to_col"]} for s in path]
            add("join_path",
                f"从表 {a} 查询到表 {b} 的数据，需要经过哪些表、用哪些字段做关联？（给出最短连接路径）",
                {"from": a, "to": b, "hops": len(path), "steps": steps},
                "join_path", "hard" if len(path) > 1 else "medium")
            extra += 1

    # 6) row_count — sample
    for t in rng.sample(tables, 16):
        add("row_count", f"表 {t['full_name']} 一共有多少行数据？",
            t["row_count"], "integer", "medium")

    # 7) schema_tables — per module
    by_schema = defaultdict(list)
    for t in tables:
        by_schema[t["schema"]].append(t["full_name"])
    for sch, ts in by_schema.items():
        cn = SCHEMA_CN.get(sch, sch)
        add("schema_tables", f"{cn}（{sch}）模块下有哪些表？",
            sorted(ts), "table_list", "easy", f"共 {len(ts)} 张表")

    # 8) schema_of — sample
    for t in rng.sample(tables, 12):
        add("schema_of", f"表 {t['name']} 属于哪个模块（schema）？",
            t["schema"], "string", "easy")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    # summary
    counts = defaultdict(int)
    for q in questions:
        counts[q["type"]] += 1
    print(f"wrote {len(questions)} questions -> {OUT}")
    for k in sorted(counts):
        print(f"  {k:14s} {counts[k]}")


if __name__ == "__main__":
    main()
