#!/usr/bin/env python3
"""Backfill full-market PER / PBR / dividend_yield from FinMind TaiwanStockPER.

Writes into the existing ``per_data`` schema (stock_id, date, per, pbr,
pe_ratio, pb_ratio, dividend_yield, source) without changing it.  The
processor's ``upsert_per_data`` keeps ``per``/``pe_ratio`` and ``pbr``/
``pb_ratio`` in sync, so this script passes all eight columns explicitly
to avoid the dynamic-binding mismatch when a payload is sparse.

Usage::

    python scripts/backfill_per.py --dry-run --limit 5
    python scripts/backfill_per.py --from-date 2026-01-01
    python scripts/backfill_per.py --stock-id 2330
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    from twstock.core.processor import DataProcessor
    from twstock.db import get_connection
    from twstock.market_data.historical_fetcher import DataFetcher
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[1]
    for p in (repo_root, repo_root.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from twstock.core.processor import DataProcessor
    from twstock.db import get_connection
    from twstock.market_data.historical_fetcher import DataFetcher


def _load_active_stock_ids() -> list[str]:
    """4-digit COMMON stocks that appear in stock_meta."""
    with get_connection(readonly=True) as conn:
        rows = conn.execute(
            """
            SELECT stock_id
            FROM stock_meta
            WHERE LENGTH(stock_id) = 4
              AND stock_id GLOB '[1-9][0-9][0-9][0-9]'
              AND type = 'COMMON'
              AND market IN ('TSE', 'OTC')
            ORDER BY stock_id
            """
        ).fetchall()
    return [r[0] for r in rows]


def _fetch_per(fetcher: DataFetcher, stock_id: str, start: str, end: str):
    """Fetch TaiwanStockPER and normalize to the eight-column per_data layout.

    PER / PBR <= 0 are treated as invalid (no meaningful ratio) and coerced to
    NaN so the upsert's ``CASE WHEN excluded.x IS NOT NULL`` keeps whatever
    value a stock already had instead of overwriting it with a bogus zero.
    """
    client = fetcher._get_client()
    df = client.get("TaiwanStockPER", stock_id, start, end)
    if df is None or df.empty:
        return df
    import numpy as np
    df = df.rename(columns={"PER": "per", "PBR": "pbr"}).copy()
    for col in ("per", "pbr"):
        if col in df.columns:
            df[col] = df[col].where(df[col] > 0)
    df["pe_ratio"] = df["per"]
    df["pb_ratio"] = df["pbr"]
    df["dividend_yield"] = df.get("dividend_yield")
    df["source"] = "finmind"
    cols = ["stock_id", "date", "per", "pbr", "pe_ratio", "pb_ratio", "dividend_yield", "source"]
    return df[[c for c in cols if c in df.columns]].copy()


def run_backfill(
    *,
    stock_id: str | None = None,
    from_date: str = "2020-01-01",
    to_date: str | None = None,
    token: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    quiet: bool = False,
) -> dict[str, int]:
    to_date = to_date or time.strftime("%Y-%m-%d")
    fetcher = DataFetcher(token=token)
    processor = DataProcessor()
    stock_ids = [stock_id] if stock_id else _load_active_stock_ids()
    if limit:
        stock_ids = stock_ids[:limit]

    stats = {"stocks": len(stock_ids), "filled": 0, "skipped": 0, "errors": 0}
    for idx, sid in enumerate(stock_ids, 1):
        try:
            df = _fetch_per(fetcher, sid, from_date, to_date)
            if df is None or df.empty:
                stats["skipped"] += 1
                continue
            if dry_run:
                stats["filled"] += len(df)
                continue
            processor.upsert_per_data(df)
            stats["filled"] += len(df)
        except Exception as exc:  # noqa: PERF203 — keep one bad stock from killing the batch
            stats["errors"] += 1
            if not quiet:
                print(f"  [WARN] {sid} failed: {exc}", flush=True)
        if not quiet and (idx % 50 == 0 or idx == len(stock_ids)):
            print(f"  [{idx}/{len(stock_ids)}] filled={stats['filled']}", flush=True)
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill PER/PBR/dividend_yield from FinMind")
    parser.add_argument("--stock-id", help="Single stock (default: full market)")
    parser.add_argument("--from-date", default="2020-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--to-date", help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--limit", type=int, help="Max stocks to process")
    parser.add_argument("--token", help="FinMind token")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started = time.perf_counter()
    stats = run_backfill(
        stock_id=args.stock_id,
        from_date=args.from_date,
        to_date=args.to_date,
        token=args.token,
        dry_run=args.dry_run,
        limit=args.limit,
        quiet=args.quiet,
    )
    elapsed = round(time.perf_counter() - started, 2)
    print(json.dumps({**stats, "elapsed_seconds": elapsed, "dry_run": args.dry_run}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
