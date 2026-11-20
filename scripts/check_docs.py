#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hard-fact consistency checker for conow-labs/developer-docs.

Verifies that facts duplicated across files (firmware minimums, register
ranges, wiring parameters) stay byte-identical everywhere they appear, and
enforces repo-wide style invariants. Run from the repo root:

    python3 scripts/check_docs.py
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
READMES = ["README.md", "README.zh-CN.md", "README.de.md", "README.nl.md"]
V2 = [f"modbus/balcony-solar-storage-v2{ext}.md" for ext in ["", ".zh-CN", ".de", ".nl"]]
V1 = [f"modbus/balcony-solar-storage{ext}.md" for ext in ["", ".zh-CN", ".de", ".nl"]]

TRIPLET = "Lyra 1.01.16 · CBE2000 Pro 1.02.18 · Atlas 1.01.09"
FACTS = [
    ("v2 minimum firmware triplet", TRIPLET, READMES),
    # Per-model version strings also appear in the v2 guides' header quotes and
    # model tables and in modbus/README (different separators there), so each
    # version is pinned on its own as well.
    ("v2 minimum Lyra 1.01.16", "1.01.16", READMES + ["modbus/README.md"] + V2),
    ("v2 minimum CBE2000 Pro 1.02.18", "1.02.18", READMES + ["modbus/README.md"] + V2),
    ("v2 minimum Atlas 1.01.09", "1.01.09", READMES + ["modbus/README.md"] + V2),
    ("version-check registers 10062–10063", "10062–10063", READMES + ["modbus/README.md"] + V2),
    ("version-check start 0x274E", "0x274E", READMES + ["modbus/README.md"] + V2),
    ("TCP verification registers 9985–9986", "9985–9986", READMES + V2),
    ("unit-ID register 9984 (0x2700)", "9984 (0x2700)", V2[0:1] + V2[2:]),
    ("unit-ID register 9984 (0x2700), full-width parens in Chinese", "9984（0x2700）", V2[1:2]),
    ("TCP port 502", "502", READMES + ["modbus/README.md"] + V2),
    ("RTU baud 38400", "38400", ["modbus/README.md"] + V1 + V2),
    ("v2 monitoring range 10000–10081", "10000–10081", READMES + V2),
    ("v2 control range 10100–10190", "10100–10190", READMES + V2),
    ("v2 protocol range 9984–9986", "9984–9986", READMES),
    ("v1 monitoring range 10000–10036", "10000–10036", READMES),
    ("v1 control range 10100–10107", "10100–10107", READMES),
]

# Non-Chinese files only (zh-CN docs legitimately use CJK and ——)
NZ = READMES[0:1] + READMES[2:] + V1[0:1] + V1[2:] + V2[0:1] + V2[2:] + ["modbus/README.md", "CONTRIBUTING.md"]

# name, pattern, files (None = all markdown), allowed-exceptions per file
FORBIDDEN = [
    ("ModBus spelling", r"ModBus", None),
    ("curly quotes", '[“”‘’]', None),
    ("double em-dash in non-Chinese docs", "——", NZ),
    ("≥ symbol outside CONTRIBUTING", r"≥", [f for f in READMES + V1 + V2 + ["modbus/README.md", "CONTRIBUTING.md"] if f != "CONTRIBUTING.md"]),
    ("CJK characters in non-Chinese docs", r"[一-鿿]", NZ),
]

def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

# Language-switcher / cross-language link lines are the only legitimate CJK
# carriers in non-Chinese docs: the 简体中文 link text targeting a *.zh-CN.md
# file and the "Language / 语言 / …" label at the start of the line.
ZH_CN_LINK = re.compile(r"\[[^\]]*\]\([^)]*\.zh-CN\.md[^)]*\)")
_LANG = r"(?:Language|Languages|Sprache|Sprachen|Taal|Talen|语言)"
LANG_LABEL = re.compile(r"^\s*" + _LANG + r"(?:\s*/\s*" + _LANG + r")*\s*:")

errors = []
for name, needle, files in FACTS:
    for f in files:
        if needle not in text(f):
            errors.append(f"FACT '{name}' missing from {f}")

for name, pat, files in FORBIDDEN:
    targets = files if files else [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.md") if ".git" not in p.parts]
    rx = re.compile(pat)
    for f in targets:
        for i, line in enumerate(text(f).splitlines(), 1):
            if "zh-CN.md" in line and name.startswith("CJK"):
                # Strip only the legitimate tokens, so stray Chinese anywhere
                # else on the line is still caught. All other forbidden
                # patterns (curly quotes, ModBus, ——, ≥) check the full line.
                line = LANG_LABEL.sub("", ZH_CN_LINK.sub("", line))
            if rx.search(line):
                errors.append(f"FORBIDDEN '{name}' in {f}:{i}: {line.strip()[:70]}")

if errors:
    print(f"{len(errors)} PROBLEM(S):")
    for e in errors:
        print(" -", e)
    sys.exit(1)

# Chinese prose uses full-width （）; a half-width paren on a Chinese line is
# typography drift (e.g. "安全 SoC (10102)"). Fenced blocks, inline code spans,
# and markdown link syntax legitimately carry half-width parens, so they are
# stripped or skipped before testing.
MD_LINK = re.compile(r"\[[^\]]*\]\([^)]*\)")
INLINE_CODE = re.compile(r"`[^`]*`")
_CJK = re.compile(r"[一-鿿]")
for f in [READMES[1], V1[1], V2[1]]:
    fence = False
    for i, line in enumerate(text(f).splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence or re.match(r"^\s*\|[\s:|-]+\|\s*$", line):
            continue
        probe = INLINE_CODE.sub(" ", MD_LINK.sub(" ", line))
        if _CJK.search(probe) and re.search(r"[()]", probe):
            errors.append(f"FORBIDDEN 'half-width parens on Chinese lines' in {f}:{i}: {line.strip()[:70]}")

if errors:
    print(f"{len(errors)} PROBLEM(S):")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print(f"FACTS OK ({len(FACTS)} facts across {len(set(sum((f for _, _, f in FACTS), [])))} files) — no drift, no forbidden patterns")
