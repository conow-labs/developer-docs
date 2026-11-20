#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structural mirror checker for conow-labs/developer-docs.

Across the four languages of each doc family: heading structure (level and
number prefix), table row counts, and code-fence content must match. Fence
lines are compared pairwise: box-drawing annotation lines by their skeleton
up to the last box character, pure-ASCII lines (frame bytes, commands, code)
byte-exact, translated prose lines skipped. Also verifies every internal
](#anchor) link resolves against a GitHub-style slug of a heading.

Run from the repo root:  python3 scripts/check_structure.py
"""
import re, pathlib
FAMS = {
 'v2': ["modbus/balcony-solar-storage-v2.md", "modbus/balcony-solar-storage-v2.zh-CN.md", "modbus/balcony-solar-storage-v2.de.md", "modbus/balcony-solar-storage-v2.nl.md"],
 'v1': ["modbus/balcony-solar-storage.md", "modbus/balcony-solar-storage.zh-CN.md", "modbus/balcony-solar-storage.de.md", "modbus/balcony-solar-storage.nl.md"],
 'readme': ["README.md", "README.zh-CN.md", "README.de.md", "README.nl.md"],
}
ALL = FAMS['v2'] + FAMS['v1'] + FAMS['readme'] + ["modbus/README.md", "CONTRIBUTING.md"]
err = []
def heads(t): return re.findall(r'^#{1,6} .*$', t, re.M)
def hstruct(hs): return [(len(m.group(1)), (m.group(2) or '')) for m in (re.match(r'(#+)\s*(?:([\d.]+)\s+)?', h) for h in hs)]
def trows(t):
    out, n, in_t = [], 0, False
    for ln in t.split('\n'):
        s = ln.strip()
        if s.startswith('|') and re.fullmatch(r'\|[\s:|-]+\|', s): in_t, n = True, 0; continue
        if in_t:
            if s.startswith('|'): n += 1
            else: out.append(n); in_t = False
    if in_t: out.append(n)
    return out
def fences(t):
    out, cur = [], None
    for ln in t.split('\n'):
        if ln.strip().startswith('```'):
            if cur is None: cur = []
            else: out.append(cur); cur = None
            continue
        if cur is not None: cur.append(ln)
    return out
BOXC = '│└┘┌┐├┤─┈'
def skel(ln):
    i = max(ln.rfind(c) for c in BOXC)
    return ln[:i+1]
def ascii_only(s): return all(ord(c) < 128 for c in s)
def cmp_fence(a, b, tag):
    if len(a) != len(b):
        err.append(f"{tag}: line count {len(a)} vs {len(b)}"); return
    for i, (la, lb) in enumerate(zip(a, b), 1):
        la, lb = la.split('#', 1)[0].rstrip(), lb.split('#', 1)[0].rstrip()
        if la == lb: continue
        if any(c in la for c in BOXC) and any(c in lb for c in BOXC):
            if skel(la) != skel(lb): err.append(f"{tag}: L{i} box skeleton differs")
        elif ascii_only(la) and ascii_only(lb):
            err.append(f"{tag}: L{i} differs: {la[:40]!r} vs {lb[:40]!r}")
for fam, files in FAMS.items():
    texts = {f: pathlib.Path(f).read_text(encoding='utf-8') for f in files}
    for f in files[1:]:
        if hstruct(heads(texts[files[0]])) != hstruct(heads(texts[f])): err.append(f"{fam}: heading structure differs in {f}")
        if trows(texts[files[0]]) != trows(texts[f]): err.append(f"{fam}: table row counts differ in {f}")
        fb, fx = fences(texts[files[0]]), fences(texts[f])
        if len(fb) != len(fx): err.append(f"{fam}: fence count differs in {f}")
        else:
            for i, (a, b) in enumerate(zip(fb, fx), 1): cmp_fence(a, b, f"{fam} {f} fence#{i}")
def slug(h):
    h = h.lstrip('#').strip().lower()
    h = re.sub(r'[^\w\- ]', '', h)
    return h.replace(' ', '-')
for f in ALL:
    t = re.sub(r'```.*?```', '', pathlib.Path(f).read_text(encoding='utf-8'), flags=re.S)
    slugs = {slug(h) for h in heads(t)}
    for m in re.finditer(r'\]\(#([^)]+)\)', t):
        if m.group(1) not in slugs: err.append(f"{f}: dangling anchor #{m.group(1)}")
if err:
    print(f"{len(err)} PROBLEM(S):"); [print(' -', e) for e in err]; raise SystemExit(1)
print(f"SYNC OK: headings, table row counts, frame/command fences mirrored across languages; anchors resolve in {len(ALL)} files")
