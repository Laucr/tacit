#!/usr/bin/env python3
"""Parse IBKR Account Overview markdown into locked book.json for WSB routines.

Does not talk to Google Drive — the agent fetches the newest overview, then calls this.
Never prints account identifiers beyond what's already in the overview markdown.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/workspace/wsb-recap")
BOOK_PATH = ROOT / "book.json"
SUMMARY_PATH = ROOT / "book.summary.txt"

MONEY = re.compile(r"[-+]?\(?\$?[-\d,]+(?:\.\d+)?\)?")
CONTRACT = re.compile(
    r"^(?P<symbol>[A-Z.]+)\s+Sep(?P<day>\d{1,2})'(?P<yy>\d{2})\s+(?P<strike>[\d.]+)\s+(?P<cp>PUT|CALL)$",
    re.I,
)
CONTRACT2 = re.compile(
    r"^(?P<symbol>[A-Z.]+)\s+(?P<mon>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"(?P<day>\d{1,2})'(?P<yy>\d{2})\s+(?P<strike>[\d.]+)\s+(?P<cp>PUT|CALL)$",
    re.I,
)
MON = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _num(s: str) -> float | None:
    if s is None:
        return None
    t = s.strip().replace(",", "").replace("$", "").replace("HK", "")
    t = t.replace("−", "-").replace("–", "-").replace("—", "-")
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    if t in {"", "—", "-", "–"}:
        return None
    try:
        v = float(t)
        return -v if neg else v
    except ValueError:
        return None


def _cells(line: str) -> list[str]:
    parts = [p.strip() for p in line.strip().strip("|").split("|")]
    return parts


def _table_after(md: str, heading_pat: str) -> list[list[str]]:
    m = re.search(heading_pat, md, re.I | re.M)
    if not m:
        return []
    chunk = md[m.end() :]
    rows: list[list[str]] = []
    for line in chunk.splitlines():
        if not line.strip().startswith("|"):
            if rows:
                break
            continue
        cells = _cells(line)
        if all(set(c) <= {"-", ":"} for c in cells):
            continue
        rows.append(cells)
    return rows


def _metric_map(md: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in _table_after(md, r"##\s+Account snapshot"):
        if len(row) < 2:
            continue
        key = row[0].lower()
        val = _num(row[1])
        if val is None:
            # leverage like 0.84x
            m = re.search(r"([\d.]+)\s*x", row[1], re.I)
            if m:
                val = float(m.group(1))
        if val is not None:
            out[key] = val
    return out


def _parse_contract(name: str) -> dict | None:
    name = re.sub(r"\s+", " ", name.strip())
    m = CONTRACT2.match(name) or CONTRACT.match(name)
    if not m:
        return None
    g = m.groupdict()
    mon = MON.get(g.get("mon", "sep").lower(), 9)
    yy = int(g["yy"])
    year = 2000 + yy
    day = int(g["day"])
    return {
        "symbol": g["symbol"].upper(),
        "expiry": f"{year:04d}-{mon:02d}-{day:02d}",
        "strike": float(g["strike"]),
        "cp": "P" if g["cp"].upper().startswith("P") else "C",
        "contract": name,
    }


def parse_overview(md: str, source: dict) -> dict:
    metrics = _metric_map(md)
    equities = []
    for row in _table_after(md, r"###\s+Equities\s*/\s*ETFs"):
        if len(row) < 6 or row[0].lower() == "symbol":
            continue
        equities.append(
            {
                "symbol": row[0],
                "qty": _num(row[1]),
                "last": _num(row[2]),
                "mkt_value": _num(row[3]),
                "avg_cost": _num(row[4]),
                "unrealized_pnl": _num(row[5]),
                "daily_pnl": _num(row[6]) if len(row) > 6 else None,
            }
        )

    options = []
    for row in _table_after(md, r"###\s+Options"):
        if len(row) < 5 or row[0].lower() == "contract":
            continue
        meta = _parse_contract(row[0]) or {"contract": row[0], "symbol": None}
        options.append(
            {
                **meta,
                "qty": _num(row[1]),
                "mark": _num(row[2]),
                "mkt_value": _num(row[3]),
                "credit": _num(row[4]),
                "unrealized_pnl": _num(row[5]) if len(row) > 5 else None,
                "daily_pnl": _num(row[6]) if len(row) > 6 else None,
                "side": "short" if (_num(row[1]) or 0) < 0 else "long",
            }
        )

    asof_m = re.search(r"\*\*As of:\*\*\s*(.+)", md)
    book = {
        "schema": "wsb-book/v1",
        "asof_text": asof_m.group(1).strip() if asof_m else None,
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "account": {
            "net_liq": metrics.get("net liquidation"),
            "cash": metrics.get("total cash"),
            "leverage": metrics.get("leverage"),
            "unrealized_pnl": metrics.get("unrealized p&l"),
            "available_funds": metrics.get("available funds"),
            "excess_liquidity": metrics.get("excess liquidity"),
        },
        "equities": equities,
        "options": options,
    }
    # Prefer exact metric keys with ampersand variants
    if book["account"]["unrealized_pnl"] is None:
        for k, v in metrics.items():
            if "unrealized" in k:
                book["account"]["unrealized_pnl"] = v
                break

    core = []
    for sym in ("TSLA", "NVDY", "AAPL", "PLTR", "NVDA"):
        eq = next((e for e in equities if e["symbol"] == sym), None)
        if eq:
            core.append(f"{sym} {eq['qty']:g}")
    opt_bits = []
    for o in options:
        if not o.get("symbol"):
            continue
        opt_bits.append(
            f"{o['symbol']} {o.get('expiry','')} {o.get('strike')}{o.get('cp')} qty={o.get('qty')} credit={o.get('credit')}"
        )
    summary = (
        f"IBKR book from {source.get('title') or 'overview'} "
        f"(modified {source.get('modifiedTime')}). "
        f"NAV={book['account'].get('net_liq')} cash={book['account'].get('cash')} "
        f"lev={book['account'].get('leverage')}. "
        f"Core: {', '.join(core) or 'n/a'}. "
        f"Opts: {'; '.join(opt_bits) or 'n/a'}."
    )
    book["summary"] = summary
    return book


def write_book(book: dict) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    BOOK_PATH.write_text(json.dumps(book, indent=2) + "\n")
    SUMMARY_PATH.write_text(book.get("summary", "") + "\n")


def load_book() -> dict | None:
    if not BOOK_PATH.exists():
        return None
    return json.loads(BOOK_PATH.read_text() or "{}")


def needs_refresh(drive_id: str, drive_modified: str) -> bool:
    book = load_book()
    if not book:
        return True
    src = book.get("source") or {}
    if src.get("fileId") != drive_id:
        return True
    return (src.get("modifiedTime") or "") != drive_modified


def main() -> None:
    ap = argparse.ArgumentParser(description="WSB IBKR book parse / status")
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write", help="Parse overview markdown → book.json")
    w.add_argument("--md", required=True, help="Path to overview .md")
    w.add_argument("--source-title", required=True)
    w.add_argument("--source-id", required=True)
    w.add_argument("--source-modified", required=True)
    w.add_argument("--source-url", default="")

    sub.add_parser("status", help="Print book source status (no secrets)")
    n = sub.add_parser("needs-refresh", help="Exit 0 if refresh needed, 1 if current")
    n.add_argument("--drive-id", required=True)
    n.add_argument("--drive-modified", required=True)

    args = ap.parse_args()
    if args.cmd == "write":
        md = Path(args.md).read_text()
        book = parse_overview(
            md,
            {
                "title": args.source_title,
                "fileId": args.source_id,
                "modifiedTime": args.source_modified,
                "viewUrl": args.source_url,
            },
        )
        write_book(book)
        print(f"wrote {BOOK_PATH}")
        print(book["summary"])
        return

    if args.cmd == "status":
        book = load_book()
        if not book:
            print("missing\tpath=/workspace/wsb-recap/book.json")
            raise SystemExit(2)
        src = book.get("source") or {}
        print(
            "ok\t"
            f"title={src.get('title')}\t"
            f"fileId={src.get('fileId')}\t"
            f"modifiedTime={src.get('modifiedTime')}\t"
            f"pulled_at={book.get('pulled_at')}"
        )
        print(book.get("summary", ""))
        return

    if args.cmd == "needs-refresh":
        need = needs_refresh(args.drive_id, args.drive_modified)
        print("needs_refresh" if need else "current")
        raise SystemExit(0 if need else 1)


if __name__ == "__main__":
    main()
