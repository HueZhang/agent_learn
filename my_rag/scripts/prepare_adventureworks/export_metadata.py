#!/usr/bin/env python
"""Export AdventureWorks schema metadata to JSON for the schema-Q&A project.

Output: data/adventureworks_schema.json
Includes per table: schema, name, comment, row_count, columns
(name/type/nullable/default/length/precision/description), primary key,
foreign keys (with referenced table+columns).
"""
import json
import os

import psycopg2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, "..", "..", "data", "adventureworks_schema.json"))
SCHEMAS = ("person", "humanresources", "production", "purchasing", "sales")

PG = dict(host="localhost", port=15432, user="postgres", password="postgres", dbname="adventureworks")


def main():
    conn = psycopg2.connect(**PG)
    cur = conn.cursor()

    # columns
    cur.execute("""
        SELECT table_schema, table_name, ordinal_position, column_name, data_type,
               udt_name, is_nullable, column_default,
               character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema IN %s AND table_name IN (
            SELECT table_name FROM information_schema.tables
            WHERE table_schema=information_schema.columns.table_schema AND table_type='BASE TABLE')
        ORDER BY table_schema, table_name, ordinal_position
    """, (SCHEMAS,))
    cols = {}
    for (sch, tbl, pos, name, dtype, udt, nullable, default, maxlen, prec, scale) in cur.fetchall():
        cols.setdefault((sch, tbl), []).append({
            "ordinal": pos, "name": name, "data_type": dtype, "udt_name": udt,
            "nullable": (nullable == "YES"), "default": default,
            "max_length": maxlen, "numeric_precision": prec, "numeric_scale": scale,
            "description": None,
        })

    # table comments
    cur.execute("""
        SELECT n.nspname, c.relname, d.description
        FROM pg_description d
        JOIN pg_class c ON c.oid = d.objoid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE d.objsubid = 0 AND n.nspname IN %s AND c.relkind = 'r'
    """, (SCHEMAS,))
    table_comment = {(s, t): desc for s, t, desc in cur.fetchall()}

    # column comments
    cur.execute("""
        SELECT n.nspname, c.relname, a.attname, d.description
        FROM pg_description d
        JOIN pg_class c ON c.oid = d.objoid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = d.objsubid
        WHERE d.objsubid > 0 AND n.nspname IN %s
    """, (SCHEMAS,))
    col_comment = {(s, t, a): desc for s, t, a, desc in cur.fetchall()}

    # primary keys
    cur.execute("""
        SELECT n.nspname, c.relname, con.conname,
               (SELECT array_agg(a.attname ORDER BY k.ord)
                FROM unnest(con.conkey) WITH ORDINALITY k(attnum, ord)
                JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum)
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE con.contype = 'p' AND n.nspname IN %s
    """, (SCHEMAS,))
    pk = {(s, t): {"name": name, "columns": pcols} for s, t, name, pcols in cur.fetchall()}

    # foreign keys
    cur.execute("""
        SELECT n.nspname, c.relname, con.conname,
               (SELECT array_agg(a.attname ORDER BY k.ord)
                FROM unnest(con.conkey) WITH ORDINALITY k(attnum, ord)
                JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum),
               fn.nspname, fc.relname,
               (SELECT array_agg(a.attname ORDER BY k.ord)
                FROM unnest(con.confkey) WITH ORDINALITY k(attnum, ord)
                JOIN pg_attribute a ON a.attrelid = fc.oid AND a.attnum = k.attnum)
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_class fc ON fc.oid = con.confrelid
        JOIN pg_namespace fn ON fn.oid = fc.relnamespace
        WHERE con.contype = 'f' AND n.nspname IN %s
    """, (SCHEMAS,))
    fks = {}
    for s, t, name, lcols, rs, rt, rcols in cur.fetchall():
        fks.setdefault((s, t), []).append({
            "name": name, "columns": lcols,
            "references": {"schema": rs, "table": rt, "columns": rcols},
        })

    tables = []
    for (sch, tbl), columns in cols.items():
        for c in columns:
            c["description"] = col_comment.get((sch, tbl, c["name"]))
        cur.execute(f'SELECT count(*) FROM "{sch}"."{tbl}"')
        rc = cur.fetchone()[0]
        tables.append({
            "schema": sch, "name": tbl, "full_name": f"{sch}.{tbl}",
            "comment": table_comment.get((sch, tbl)),
            "row_count": rc,
            "primary_key": pk.get((sch, tbl)),
            "foreign_keys": fks.get((sch, tbl), []),
            "columns": columns,
        })

    tables.sort(key=lambda t: (t["schema"], t["name"]))
    doc = {
        "database": "adventureworks",
        "source": "Microsoft AdventureWorks OLTP 2014 (via lorint/AdventureWorks-for-Postgres)",
        "schemas": list(SCHEMAS),
        "table_count": len(tables),
        "tables": tables,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    n_cols = sum(len(t["columns"]) for t in tables)
    n_desc = sum(1 for t in tables for c in t["columns"] if c["description"])
    n_fks = sum(len(t["foreign_keys"]) for t in tables)
    print(f"wrote {OUT}")
    print(f"tables={len(tables)} columns={n_cols} described_columns={n_desc} foreign_keys={n_fks}")
    conn.close()


if __name__ == "__main__":
    main()
