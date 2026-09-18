#!/usr/bin/env python3
"""validate_report.py — deterministic checker for a US SEC EDGAR Harvester report.

Stdlib-only. Verifies that a produced filing-timeline / harvest report carries the
required sections and per-row source + date provenance labels, and that it does not
slip into recommendation/advice framing (this is a collection-only skill).

Usage:
    python scripts/validate_report.py path/to/filing_timeline.md

Exit codes:
    0 — report has all required sections and source/date labels
    1 — one or more required checks failed
    2 — usage / file-read error

The report is expected to be Markdown (or plain text). Checks are intentionally
lenient about exact wording but strict about presence of provenance and disclaimer.
"""
from __future__ import annotations

import re
import sys

# Required section markers (case-insensitive substring match; ZH or EN accepted).
REQUIRED_SECTIONS = [
    ("subject / 主体", [r"subject", r"主体", r"标的", r"cik"]),
    ("timeline / 时间线", [r"timeline", r"时间线", r"时间轴"]),
    ("data source / 数据来源", [r"edgar", r"data source", r"数据来源", r"source url", r"来源"]),
    ("disclaimer / 免责声明", [r"不构成任何投资建议",
                              r"not\s+(?:constitute\s+)?investment\s+advice"]),
]

# At least one accession number must appear (EDGAR canonical dashed form).
ACCESSION_RE = re.compile(r"\b\d{10}-\d{2}-\d{6}\b")
# A source URL to sec.gov must appear.
SEC_URL_RE = re.compile(r"https?://[^\s)]*sec\.gov", re.I)
# A date label distinguishing filing vs event/period must appear.
DATE_LABEL_RE = re.compile(
    r"filing[\s_-]?date|event[\s_-]?date|period[\s_-]?(?:of[\s_-]?report|end|date)|"
    r"申报日|披露日|事件日|报告期|交易日",
    re.I,
)
# Collection-only skill: reject recommendation/advice framing (over-claim guard).
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
    path = argv[1]
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 2

    low = text.lower()
    failures: list[str] = []

    for label, patterns in REQUIRED_SECTIONS:
        if not any(re.search(p, low, re.I) for p in patterns):
            failures.append(f"missing required section: {label}")

    if not ACCESSION_RE.search(text):
        failures.append("no EDGAR accession number found (expected form 0000000000-00-000000)")
    if not SEC_URL_RE.search(text):
        failures.append("no sec.gov source URL found (every filing must cite its source)")
    if not DATE_LABEL_RE.search(text):
        failures.append("no date label found (must distinguish filing date vs event/period date)")

    for pattern, label in BANNED_RE:
        if pattern.search(text):
            failures.append(f"forbidden framing for a collection-only skill: {label}")

    if failures:
        print(f"FAIL: {path}")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"OK: {path} has required sections, source/date provenance, and disclaimer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
