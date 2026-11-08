#!/usr/bin/env python
"""Import AdventureWorks OLTP into local Postgres.

Reproduces lorint/AdventureWorks-for-Postgres flow without ruby/psql:
 - cleans the raw Microsoft CSVs (port of update_csvs.rb) in memory
 - executes install.sql statement-by-statement (dollar-quote aware)
 - replaces each psql ``\\copy`` with psycopg2 COPY ... FROM STDIN
Per-statement and per-copy errors are logged and skipped so partial
success is visible.
"""
import os
import re
import tempfile

import psycopg2

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.abspath(os.path.join(HERE, "..", "..", "data", "raw", "adventureworks"))
OLTP = os.path.join(RAW, "oltp")
INSTALL_SQL = os.path.join(RAW, "install.sql")

PG = dict(host="localhost", port=15432, user="postgres", password="postgres")
DBNAME = "adventureworks"


# ----------------------------- SQL splitter -----------------------------
def split_sql(sql):
    stmts, cur, i, n = [], [], 0, len(sql)
    mode, dtag = "normal", ""
    while i < n:
        c = sql[i]
        if mode == "normal":
            if sql.startswith("--", i):
                mode = "line"; cur.append("--"); i += 2; continue
            if sql.startswith("/*", i):
                mode = "block"; cur.append("/*"); i += 2; continue
            if c == "'":
                mode = "single"; cur.append(c); i += 1; continue
            if c == '"':
                mode = "double"; cur.append(c); i += 1; continue
            if c == "$":
                j = i + 1
                while j < n and (sql[j].isalnum() or sql[j] == "_"):
                    j += 1
                if j < n and sql[j] == "$":
                    dtag = sql[i:j + 1]; mode = "dollar"; cur.append(dtag); i = j + 1; continue
                cur.append(c); i += 1; continue
            if c == ";":
                cur.append(c); stmts.append("".join(cur)); cur = []; i += 1; continue
            cur.append(c); i += 1; continue
        elif mode == "line":
            cur.append(c)
            if c == "\n":
                mode = "normal"
            i += 1; continue
        elif mode == "block":
            if sql.startswith("*/", i):
                cur.append("*/"); i += 2; mode = "normal"; continue
            cur.append(c); i += 1; continue
        elif mode == "single":
            cur.append(c)
            if c == "'":
                if i + 1 < n and sql[i + 1] == "'":
                    cur.append("'"); i += 2; continue
                mode = "normal"
            i += 1; continue
        elif mode == "double":
            cur.append(c)
            if c == '"':
                if i + 1 < n and sql[i + 1] == '"':
                    cur.append('"'); i += 2; continue
                mode = "normal"
            i += 1; continue
        elif mode == "dollar":
            if sql.startswith(dtag, i):
                cur.append(dtag); i += len(dtag); mode = "normal"; continue
            cur.append(c); i += 1; continue
    tail = "".join(cur)
    if tail.strip():
        stmts.append(tail)
    return [s for s in stmts if s.strip() and not _comment_only(s)]


def _comment_only(s):
    t = re.sub(r"--[^\n]*", "", s)
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    return not t.strip()


# --------------------------- CSV cleaning (rb port) ---------------------------
def clean_text(raw):
    """Port of update_csvs.rb. Returns (text, changed)."""
    lines = raw.splitlines(keepends=True)
    is_needed = is_pipes = is_cleaning = False
    if lines:
        first = lines[0]
        if "+|" in first:
            is_pipes = is_needed = is_cleaning = True
        if first.startswith("﻿"):
            lines[0] = first[1:]; is_needed = True
        if "&|" in first or "\tE6100000010C" in first:
            is_needed = is_cleaning = True
    if not is_needed:
        return raw, False

    if is_pipes:
        output, text = [], ""
        for line in lines:
            line = line.replace("|474946383961", "|\\\\x474946383961").replace('"', '""')
            while "&|" in line:
                end_index = line.index("&|")
                text += line[:end_index].strip()
                parts = text.split("+|")
                out = []
                for idx, part in enumerate(parts):
                    if idx == 0 and part == "":
                        part = "00"
                    else:
                        part = part.replace("", "")
                    if len(part) >= 1 and part[0] == "<" and part[-1] == ">":
                        out.append('"' + part + '"')
                    elif len(part) >= 2 and part[1] == "<" and part[-1] == ">":
                        out.append('"' + part[1:] + '"')
                    elif "\t" in part:
                        out.append('"' + part + '"')
                    else:
                        out.append(part)
                output.append("\t".join(out) + "\n")
                text = ""
                line = line[end_index + 2:]
            if line.strip() != "":
                text += line.replace("\r\n", "\\n").replace("\n", "\\n")
        return "".join(output), True

    output = []
    for line in lines:
        if is_cleaning:
            line = (line.replace('"', '""')
                        .replace("&|\n", "\n").replace("&|\r\n", "\n")
                        .replace("\tE6100000010C", "\t\\\\xE6100000010C")
                        .replace("\r\n", "\n"))
        output.append(line)
    return "".join(output), True


def read_text(path):
    with open(path, "rb") as f:
        data = f.read()
    for enc in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


COPY_RE = re.compile(r"\\copy\s+(\S+)\s+FROM\s+'([^']+)'\s+DELIMITER\s+E'\\t'\s+CSV(.*?);?\s*$")


def do_copy(cur, line, tmpdir):
    m = COPY_RE.search(line.strip())
    if not m:
        return ("PARSE_FAIL", line.strip())
    table, fname, opts = m.group(1), m.group(2), m.group(3)
    fname = fname.lstrip("./")
    src = os.path.join(OLTP, fname)
    if not os.path.exists(src):
        return ("NO_FILE", fname)
    text, changed = clean_text(read_text(src))
    if chr(0) in text:
        text = text.replace(chr(0), "")
    dst = os.path.join(tmpdir, fname)
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    if "QUOTE E'\\001'" in opts:
        sql = f"COPY {table} FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', QUOTE E'\\001')"
    else:
        sql = f"COPY {table} FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t')"
    with open(dst, "rb") as fh:
        cur.copy_expert(sql, fh)
    return ("OK", table)


def main():
    # (re)create database
    admin = psycopg2.connect(dbname="postgres", **PG)
    admin.autocommit = True
    acur = admin.cursor()
    acur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (DBNAME,))
    acur.execute(f'DROP DATABASE IF EXISTS "{DBNAME}"')
    acur.execute(f'CREATE DATABASE "{DBNAME}"')
    acur.close(); admin.close()
    print(f"created database {DBNAME}")

    conn = psycopg2.connect(dbname=DBNAME, **PG)
    conn.autocommit = True
    cur = conn.cursor()

    sql_text = read_text(INSTALL_SQL)
    lines = sql_text.splitlines(keepends=True)

    stmt_fail = []
    copy_fail = []
    copy_ok = 0
    buf = []
    tmpdir = tempfile.mkdtemp(prefix="aw_clean_")

    def flush_buffer():
        nonlocal buf
        if not buf:
            return
        chunk = "".join(buf); buf = []
        for st in split_sql(chunk):
            try:
                cur.execute(st)
            except Exception as e:
                stmt_fail.append((st.strip()[:80].replace("\n", " "), str(e).splitlines()[0][:160]))

    for ln in lines:
        s = ln.lstrip()
        if s.startswith("\\copy"):
            flush_buffer()
            mm = COPY_RE.search(ln.strip())
            tbl = mm.group(1) if mm else "?"
            try:
                status, info = do_copy(cur, ln, tmpdir)
                if status == "OK":
                    copy_ok += 1
                else:
                    copy_fail.append((status, info))
            except Exception as e:
                copy_fail.append(("COPY_ERR:" + tbl, str(e).splitlines()[0][:160]))
        elif s.startswith("\\pset") or s.startswith("\\dt") or s.startswith("\\echo") or s.startswith("\\i"):
            continue
        else:
            buf.append(ln)
    flush_buffer()

    # summary
    cur.execute("""SELECT table_schema, count(*) FROM information_schema.tables
                   WHERE table_schema IN ('person','humanresources','production','purchasing','sales')
                     AND table_type='BASE TABLE'
                   GROUP BY table_schema ORDER BY table_schema""")
    print("\n=== tables per schema ===")
    total = 0
    for sch, cnt in cur.fetchall():
        print(f"  {sch}: {cnt}"); total += cnt
    print("  TOTAL base tables:", total)

    print(f"\n=== copies: ok={copy_ok}, failed={len(copy_fail)} ===")
    for st, info in copy_fail:
        print("  COPY_FAIL", st, info)
    print(f"\n=== statements failed: {len(stmt_fail)} ===")
    for st, err in stmt_fail:
        print("  STMT_FAIL", st, "||", err)

    cur.close(); conn.close()


if __name__ == "__main__":
    main()
