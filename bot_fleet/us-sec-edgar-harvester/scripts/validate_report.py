#!/usr/bin/env python3
"""validate_report.py — deterministic checker for a US SEC EDGAR Harvester report.

Stdlib-only. Verifies required sections, accession/source/date provenance, and collection-only framing.
"""
from __future__ import annotations
import re
import sys

REQUIRED_SECTIONS = [
    ("subject / 主体", [r"subject", r"主体", r"标的", r"cik"]),
    ("timeline / 时间线", [r"timeline", r"时间线", r"时间轴"]),
    ("data source / 数据来源", [r"edgar", r"data source", r"数据来源", r"source url", r"来源"]),
    ("disclaimer / 免责声明", [r"不构成任何投资建议", r"not\s+(?:constitute\s+)?investment\s+advice"]),
]
ACCESSION_RE = re.compile(r"\b\d{10}-\d{2}-\d{6}\b")
SEC_URL_RE = re.compile(r"https?://[^\s)]*sec\.gov", re.I)
DATE_LABEL_RE = re.compile(r"filing[\s_-]?date|event[\s_-]?date|period[\s_-]?(?:of[\s_-]?report|end|date)|申报日|披露日|事件日|报告期|交易日", re.I)
BANNED_RE = [
    (re.compile(r"guaranteed\s+(?:profit|return)", re.I), "guaranteed profit/return"),
    (re.compile(r"稳赚|保证盈利|稳定盈利|无风险"), "guaranteed-profit framing"),
    (re.compile(r"\b(?:buy|sell)\s+recommendation\b", re.I), "explicit buy/sell recommendation"),
    (re.compile(r"建议(?:买入|卖出|增持|减持)"), "explicit buy/sell recommendation (ZH)"),
]

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python validate_report.py <report.md>", file=sys.stderr)
        return 2
    try:
        text = open(argv[1], "r", encoding="utf-8", errors="replace").read()
    except OSError as exc:
        print(f"error: cannot read {argv[1]}: {exc}", file=sys.stderr)
        return 2
    low = text.lower(); failures = []
    for label, patterns in REQUIRED_SECTIONS:
        if not any(re.search(p, low, re.I) for p in patterns): failures.append(f"missing required section: {label}")
    if not ACCESSION_RE.search(text): failures.append("no EDGAR accession number found")
    if not SEC_URL_RE.search(text): failures.append("no sec.gov source URL found")
    if not DATE_LABEL_RE.search(text): failures.append("no date label found")
    for pattern, label in BANNED_RE:
        if pattern.search(text): failures.append(f"forbidden framing: {label}")
    if failures:
        print(f"FAIL: {argv[1]}"); [print(f"  - {f}") for f in failures]; return 1
    print(f"OK: {argv[1]} has required sections, source/date provenance, and disclaimer"); return 0

if __name__ == "__main__": raise SystemExit(main(sys.argv))
