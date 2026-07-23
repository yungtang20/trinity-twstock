#!/usr/bin/env python3
"""Run backfill_per over a file of stock_ids with a dedicated FinMind token.

Usage::

    python scripts/backfill_per_chunk.py logs/per_chunk_a.txt --token <TOKEN>

Used to parallelize the PER backfill across multiple FinMind tokens without
touching the stock_meta-driven ``backfill_per.py`` entry point.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    from backfill_per import _fetch_per
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = str(Path(__file__).resolve().parent)
    for p in (scripts_dir, repo_root, repo_root.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from backfill_per import _fetch_per


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PER backfill over a stock-id list")
    parser.add_argument("stock_list", help="File with one stock_id per line")
    parser.add_argument("--token", required=True, help="FinMind token for this chunk")
    parser.add_argument("--from-date", default="2020-01-01")
    parser.add_argument("--to-date", default=None)
    args = parser.parse_args(argv)

    stock_ids = [line.strip() for line in Path(args.stock_list).read_text().splitlines() if line.strip()]
    started = time.perf_counter()

    # run_backfill expects full market or single stock; wrap its internals by
    # calling per-stock so we can inject a custom token and a bounded list.
    from twstock.core.processor import DataProcessor
    from twstock.market_data.historical_fetcher import DataFetcher

    fetcher = DataFetcher(token=args.token)
    processor = DataProcessor()
    stats = {"stocks": len(stock_ids), "filled": 0, "skipped": 0, "errors": 0}
    for idx, sid in enumerate(stock_ids, 1):
        try:
            df = _fetch_per(fetcher, sid, args.from_date, args.to_date or time.strftime("%Y-%m-%d"))
            if df is None or df.empty:
                stats["skipped"] += 1
                continue
            processor.upsert_per_data(df)
            stats["filled"] += len(df)
        except Exception as exc:  # noqa: PERF203
            stats["errors"] += 1
            print(f"  [WARN] {sid} failed: {exc}", flush=True)
        if idx % 50 == 0 or idx == len(stock_ids):
            print(f"  [{idx}/{len(stock_ids)}] filled={stats['filled']}", flush=True)

    elapsed = round(time.perf_counter() - started, 2)
    print(json.dumps({**stats, "elapsed_seconds": elapsed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
