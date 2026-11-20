#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Derive machine-readable register CSVs from the English protocol guides.

The Markdown tables remain the hand-written master; the CSVs are derived
artifacts for downstream integrators (home-assistant-local, agent-skills).

    python3 scripts/gen_registers_csv.py           # regenerate in place
    python3 scripts/gen_registers_csv.py --check   # verify CSVs match the tables (for CI)

Slot-matrix tables (base-load 3.9, TOU 3.10) keep their compact human layout
in the Markdown; this script expands them into one CSV row per register.
"""
import csv, io, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = [
    ("modbus/balcony-solar-storage-v2.md", "modbus/balcony-solar-storage-v2.registers.csv"),
    ("modbus/balcony-solar-storage.md", "modbus/balcony-solar-storage.registers.csv"),
]
CANON = {"register", "hex", "name", "type", "unit", "scale", "remarks"}

# Field metadata for slot-matrix tables, keyed by register range. The Markdown
# keeps these facts in the surrounding prose and field tables; the CSV repeats
# them per row for machine consumers.
HHMM = "hour in the high byte, minute in the low byte"
MATRIX_META = [
    (10125, 10148, "Base-Load Slot", {
        "Start": ("uint16", "hhmm", HHMM),
        "End": ("uint16", "hhmm", HHMM),
        "Power": ("uint16", "W", "slot power range 0–3000 W"),
    }),
    (10150, 10189, "TOU Slot", {
        "Start": ("uint16", "hhmm", HHMM),
        "End": ("uint16", "hhmm", HHMM),
        "Mode": ("uint16", "—", "0 = charge (only Target SoC applies) · 1 = discharge (only Discharge Power applies)"),
        "Target SoC": ("uint16", "%", "applies when mode = 0"),
        "Discharge Power": ("uint16", "W", "applies when mode = 1"),
    }),
]

def norm_header(cells):
    m = {"register": ["register", "address (dec)"], "hex": ["hex", "address (hex)"]}
    out = []
    for c in cells:
        lc = c.strip().lower()
        key = next((k for k, v in m.items() if lc in v), lc)
        out.append(key)
    return out

CELL = re.compile(r"(\d{4,5}) \((0x[0-9A-F]{4})\)")

def meta_for(addr):
    for lo, hi, prefix, fields in MATRIX_META:
        if lo <= addr <= hi:
            return prefix, fields
    return None, None

def parse(md_text, problems):
    rows, section, i = [], "", 0
    lines = md_text.splitlines()
    while i < len(lines):
        h = re.match(r"^#{2,4}\s+(.*)", lines[i])
        if h:
            section = h.group(1).strip()
            i += 1
            continue
        if not lines[i].startswith("|"):
            i += 1
            continue
        block = []
        while i < len(lines) and lines[i].startswith("|"):
            block.append(lines[i])
            i += 1
        grid = [[c.strip() for c in l.strip().strip("|").split("|")] for l in block]
        if len(grid) < 2 or not all(re.fullmatch(r":?-+:?", c) for c in grid[1]):
            continue  # not a Markdown table (no separator row)
        header, body = norm_header(grid[0]), grid[2:]
        if not body:
            continue
        if "register" not in header or "hex" not in header:
            # Slot-matrix table: first column is a small integer, every other
            # cell is "address (hex)". Expand one CSV row per register.
            if all(re.fullmatch(r"\d+", r[0]) and len(r) > 2
                   and all(CELL.fullmatch(c) for c in r[1:]) for r in body):
                for r in body:
                    for col, cell in zip(grid[0][1:], r[1:]):
                        m = CELL.fullmatch(cell)
                        addr = int(m.group(1))
                        prefix, fields = meta_for(addr)
                        if prefix is None:
                            problems.append(f"matrix register {addr} has no MATRIX_META entry")
                            continue
                        ftype, funit, fremark = fields[col]
                        rows.append({"section": section, "register": m.group(1), "hex": m.group(2),
                                     "name": f"{prefix} {r[0]} {col}", "type": ftype, "unit": funit,
                                     "scale": "—", "remarks": fremark})
            continue
        if "name" not in header:
            continue
        if "type" not in header:
            problems.append(f"register table without a Type column under '{section}' — add the column so the CSV stays complete")
        for r in body:
            if len(r) < 4:
                continue
            rec = dict.fromkeys(CANON, "")
            for k, v in zip(header, r):
                rec[k if k in CANON else k] = v
            rec["section"] = section
            rows.append(rec)
    return rows

def build(src, problems):
    rows = parse((ROOT / src).read_text(encoding="utf-8"), problems)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["section", "register", "hex", "name", "type", "unit", "scale", "remarks"], lineterminator="\n")
    w.writeheader()
    for r in sorted(rows, key=lambda r: int(re.match(r"\d+", r["register"]).group())):
        w.writerow(r)
    return buf.getvalue()

problems = []
for src, dst in SOURCES:
    want = build(src, problems)
    target = ROOT / dst
    if "--check" in sys.argv:
        have = target.read_text(encoding="utf-8") if target.exists() else ""
        if have != want:
            print(f"DRIFT: {dst} does not match tables in {src} — regenerate with: python3 scripts/gen_registers_csv.py")
            problems.append(f"drift in {dst}")
        else:
            print(f"OK {dst} ({want.count(chr(10)) - 1} register rows)")
    else:
        target.write_text(want, encoding="utf-8")
        print(f"wrote {dst} ({want.count(chr(10)) - 1} register rows)")
if problems:
    print(f"{len(problems)} PROBLEM(S):")
    for p in problems:
        print(" -", p)
sys.exit(1 if problems else 0)
