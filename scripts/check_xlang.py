#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-language drift checker for conow-labs/developer-docs.

Table cells are compared across the four languages of each doc family:

- column 0 "data" cells (register addresses, hex codes, bit ids) must be
  byte-identical in every language;
- translated cells must preserve the multiset of numeric facts (register
  ids, ranges, defaults, hex values) and the empty-cell placeholder "—"
  (Chinese ordinal-classifier words 一级/二级/三级 map to 1/2/3);
- translated name columns must map 1:1 within a table (same source word
  always translates to the same target word);
- the whole-document numeric multiset (prose, fences excluded) must be
  equal across languages, so a number edited in one language cannot drift.

Run from the repo root:  python3 scripts/check_xlang.py
"""
import re, pathlib, sys
from collections import Counter
FAMS = {
 'v2': ["modbus/balcony-solar-storage-v2.md", "modbus/balcony-solar-storage-v2.zh-CN.md", "modbus/balcony-solar-storage-v2.de.md", "modbus/balcony-solar-storage-v2.nl.md"],
 'v1': ["modbus/balcony-solar-storage.md", "modbus/balcony-solar-storage.zh-CN.md", "modbus/balcony-solar-storage.de.md", "modbus/balcony-solar-storage.nl.md"],
 'readme': ["README.md", "README.zh-CN.md", "README.de.md", "README.nl.md"],
}
err, warn = [], []
def read(f): return pathlib.Path(f).read_text(encoding='utf-8')
def tables(text):
    tabs, cur = [], None
    for ln in text.split('\n'):
        s = ln.strip()
        if s.startswith('|') and s.endswith('|'):
            if re.fullmatch(r'[\s:|-]+', s[1:-1]): continue
            cur = cur or []
            cur.append([c.strip() for c in s[1:-1].split('|')])
        elif cur: tabs.append(cur); cur = None
    if cur: tabs.append(cur)
    return tabs
NUM = re.compile(r'0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?')
def sig(cell):
    cell = cell.replace('一级', ' 1 ').replace('二级', ' 2 ').replace('三级', ' 3 ')
    toks = NUM.findall(cell)
    if cell == '—': toks.append('EMPTY')
    return Counter(toks)
DATA0 = re.compile(r'^(?:0[xX][0-9A-F]+|\d{4,5}(?:[–-]\d{4,5})?|bit\d+)$')
for fam, files in FAMS.items():
    T = {f: tables(read(f)) for f in files}
    base = files[0]
    for f in files[1:]:
        if len(T[base]) != len(T[f]): err.append(f"{fam}: table count differs in {f}"); continue
        for ti, (tb, tf) in enumerate(zip(T[base], T[f]), 1):
            if len(tb) != len(tf): err.append(f"{fam} table#{ti}: row count differs in {f}"); continue
            for ri, (rb, rf) in enumerate(zip(tb, tf)):
                if len(rb) != len(rf): err.append(f"{fam} table#{ti} row{ri}: cell count differs in {f}"); continue
                for ci, (cb, cf) in enumerate(zip(rb, rf)):
                    if cb == cf: continue
                    if ci == 0 and (DATA0.match(cb) or DATA0.match(cf)):
                        err.append(f"{fam} t#{ti} r{ri}: data col0 {cb!r} vs {cf!r} in {f}")
                    elif sig(cb) != sig(cf):
                        err.append(f"{fam} t#{ti} r{ri} c{ci}: number/EMPTY mismatch {cb[:34]!r} vs {cf[:34]!r} in {f}")
        for ti, (tb, tf) in enumerate(zip(T[base], T[f]), 1):
            for ci in range(max(len(r) for r in tb)):
                fwd, rev = {}, {}
                for rb, rf in zip(tb, tf):
                    if ci >= len(rb) or ci >= len(rf): continue
                    a, b = rb[ci], rf[ci]
                    if a == b: continue
                    if a in fwd and fwd[a] != b: warn.append(f"{fam} t#{ti} c{ci}: {a[:28]!r} -> both {fwd[a][:22]!r},{b[:22]!r} in {f}")
                    if b in rev and rev[b] != a: warn.append(f"{fam} t#{ti} c{ci}: {b[:28]!r} <- both {rev[b][:22]!r},{a[:22]!r} in {f}")
                    fwd[a], rev[b] = b, a
def prose(f): return Counter(NUM.findall(re.sub(r'```.*?```', '', read(f), flags=re.S)))
for fam, files in FAMS.items():
    b = prose(files[0])
    for f in files[1:]:
        d1, d2 = b - prose(f), prose(f) - b
        if d1 or d2: warn.append(f"{fam} {f}: numeric diff missing={dict(d1)} extra={dict(d2)}")
if err: print(f"{len(err)} ERROR(S):"); [print(' -', e) for e in err]
if warn: print(f"{len(warn)} REVIEW ITEM(S):"); [print(' -', w) for w in warn]
if not err and not warn: print("XLANG OK (12 docs): data cells identical, translated cells number-preserving, names 1:1, doc numeric multiset equal")
sys.exit(1 if err else 0)
