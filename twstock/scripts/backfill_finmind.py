#!/usr/bin/env python3
"""Backfill missing FinMind data based on existing stock_history coverage."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

def _ensure_import_path() -> None:
    """Keep script runnable directly from repository checkout."""
    if __package__ in {None, ""}:
        repo_root = Path(__file__).resolve().parents[1]
        for p in (repo_root, repo_root.parent):
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))


_ensure_import_path()

try:
    from twstock.core.processor import DataProcessor
    from twstock.db import get_connection
    from twstock.market_data.historical_fetcher import DataFetcher
except ModuleNotFoundError:
    # Support direct script execution from repo checkout without module-path init.
    from core.processor import DataProcessor
    from db import get_connection
    from market_data.historical_fetcher import DataFetcher


@dataclass
class FillResult:
    stock_id: str
    institutional: int = 0
    shareholding: int = 0
    missing_institutional_dates: int = 0
    missing_shareholding_dates: int = 0
    remaining_institutional_dates: int = 0
    remaining_shareholding_dates: int = 0

    @property
    def ok(self) -> bool:
        return self.remaining_institutional_dates == 0 and self.remaining_shareholding_dates == 0


def _load_done_stock_ids(state_file: str | None) -> set[str]:
    if not state_file:
        return set()
    path = Path(state_file)
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def _mark_done_stock_id(state_file: str | None, stock_id: str) -> None:
    if not state_file:
        return
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{stock_id}\n")


def _iter_stock_ids(
    conn,
    stock_id: str | None,
    limit: int | None = None,
    done_stock_ids: set[str] | None = None,
) -> list[str]:
    if stock_id:
        return [stock_id]
    rows = conn.execute(
        """
        SELECT m.stock_id
        FROM stock_meta m
        WHERE LENGTH(m.stock_id)=4
          AND m.stock_id GLOB '[1-9][0-9][0-9][0-9]'
          AND m.type = 'COMMON'
          AND m.market IN ('TSE', 'OTC')
          AND EXISTS (
              SELECT 1
              FROM stock_history h
              LEFT JOIN institutional_data i
                ON i.stock_id = h.stock_id
               AND i.date = h.date
              WHERE h.stock_id = m.stock_id
                AND i.date IS NULL
          )
        ORDER BY (
            SELECT COUNT(*)
            FROM stock_history h
            LEFT JOIN institutional_data i
              ON i.stock_id = h.stock_id
             AND i.date = h.date
            WHERE h.stock_id = m.stock_id
              AND i.date IS NULL
        ) DESC, m.stock_id
        """
    ).fetchall()
    done_stock_ids = done_stock_ids or set()
    stock_ids = [r[0] for r in rows if r[0] not in done_stock_ids]
    if limit and limit > 0:
        return stock_ids[:limit]
    return stock_ids


def _get_history_range(conn, stock_id: str, from_date: str | None, to_date: str | None) -> tuple[str, str]:
    lower = conn.execute(
        "SELECT MIN(date), MAX(date) FROM stock_history WHERE stock_id = ?", (stock_id,)
    ).fetchone()
    min_date = from_date or lower[0]
    max_date = to_date or lower[1]
    if not min_date or not max_date:
        return "", ""
    return min_date, max_date


def _missing_dates_count(conn, stock_id: str, component: str, start: str, end: str) -> int:
    if component == "institutional_data":
        return conn.execute(
            """
            SELECT COUNT(*)
            FROM stock_history h
            LEFT JOIN institutional_data i
              ON i.stock_id = h.stock_id
             AND i.date = h.date
            WHERE h.stock_id = ?
              AND h.date BETWEEN ? AND ?
              AND i.date IS NULL
            """,
            (stock_id, start, end),
        ).fetchone()[0]

    if component == "shareholding":
        return conn.execute(
            """
            SELECT COUNT(*)
            FROM stock_history h
            LEFT JOIN shareholding_unified s
              ON s.stock_id = h.stock_id
             AND s.date = h.date
             AND s.source = 'finmind'
            WHERE h.stock_id = ?
              AND h.date BETWEEN ? AND ?
              AND s.date IS NULL
            """,
            (stock_id, start, end),
        ).fetchone()[0]
    raise ValueError(f"unsupported component: {component}")


def _build_chunks(start: str, end: str, chunk_days: int) -> Iterable[tuple[str, str]]:
    if not start or not end:
        return []
    if chunk_days <= 0:
        chunk_days = 365
    import datetime as dt

    current = dt.datetime.strptime(start, "%Y-%m-%d").date()
    end_d = dt.datetime.strptime(end, "%Y-%m-%d").date()
    step = dt.timedelta(days=chunk_days - 1)
    while current <= end_d:
        chunk_end = min(end_d, current + step)
        yield current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")
        current = chunk_end + dt.timedelta(days=1)


def _fill_stock(
    fetcher: DataFetcher,
    processor: DataProcessor,
    stock_id: str,
    component: str,
    start: str,
    end: str,
    chunk_days: int,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Fill one stock and return (filled_rows, missing_dates)."""
    if not start or not end:
        return 0, 0

    with get_connection(readonly=True) as conn:
        missing = _missing_dates_count(conn, stock_id, component, start, end)
        if missing == 0:
            return 0, 0

    filled = 0
    if dry_run:
        return 0, missing

    # 實際抓資料採用連續區段：若有缺漏，就抓該區段即可，FinMind 可重複回傳已存在日期，會由 upsert 覆蓋不改變。
    for chunk_start, chunk_end in _build_chunks(start, end, chunk_days):
        if component == "institutional_data":
            df = fetcher.fetch_institutional(stock_id, chunk_start, chunk_end)
            if df is not None and not df.empty:
                df["stock_id"] = stock_id
                filled += processor.upsert_institutional(df)
        else:
            df = fetcher.fetch_shareholding(stock_id, chunk_start, chunk_end)
            if df is not None and not df.empty:
                df["stock_id"] = stock_id
                processor.upsert_shareholding(df)
                # upsert_shareholding currently returns int only in processor design; keep consistency.
                filled += int(df.shape[0])
    return filled, missing


def _format_row(row: FillResult) -> str:
    return (
        f"{row.stock_id}: inst_missing={row.missing_institutional_dates}, "
        f"inst_filled={row.institutional}, inst_remaining={row.remaining_institutional_dates}, "
        f"shar_missing={row.missing_shareholding_dates}, shar_filled={row.shareholding}, "
        f"shar_remaining={row.remaining_shareholding_dates}"
    )


def _append_progress(progress_log: str | None, message: str) -> None:
    if not progress_log:
        return
    path = Path(progress_log)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(message + "\n")


def run_backfill(
    stock_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    include_shareholding: bool = False,
    chunk_days: int = 365,
    token: str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    verbose: bool = False,
    state_file: str | None = None,
    progress_log: str | None = None,
    quiet: bool = False,
) -> list[FillResult]:
    results: list[FillResult] = []
    fetcher = DataFetcher(token=token)
    processor = DataProcessor()
    done_stock_ids = _load_done_stock_ids(state_file)

    with get_connection(readonly=True) as conn:
        stock_ids = _iter_stock_ids(conn, stock_id, limit, done_stock_ids)

    for idx, sid in enumerate(stock_ids, start=1):
        with get_connection(readonly=True) as conn:
            start, end = _get_history_range(conn, sid, from_date, to_date)

        if not start or not end:
            results.append(FillResult(stock_id=sid))
            continue

        with get_connection(readonly=True) as conn:
            miss_inst = _missing_dates_count(conn, sid, "institutional_data", start, end)

        row = FillResult(stock_id=sid, missing_institutional_dates=miss_inst)
        if miss_inst > 0:
            filled, _ = _fill_stock(
                fetcher, processor, sid, "institutional_data", start, end, chunk_days, dry_run
            )
            row.institutional = filled
            with get_connection(readonly=True) as conn:
                row.remaining_institutional_dates = _missing_dates_count(
                    conn, sid, "institutional_data", start, end
                )

        if include_shareholding:
            with get_connection(readonly=True) as conn:
                row.missing_shareholding_dates = _missing_dates_count(
                    conn, sid, "shareholding", start, end
                )
            if row.missing_shareholding_dates > 0:
                filled, _ = _fill_stock(
                    fetcher, processor, sid, "shareholding", start, end, chunk_days, dry_run
                )
                row.shareholding = filled
                with get_connection(readonly=True) as conn:
                    row.remaining_shareholding_dates = _missing_dates_count(
                        conn, sid, "shareholding", start, end
                    )

        results.append(row)
        if not dry_run and stock_id is None:
            _mark_done_stock_id(state_file, sid)
        message = f"[{idx}/{len(stock_ids)}] {_format_row(row)}"
        if not quiet and (
            verbose or row.institutional or row.shareholding or row.remaining_institutional_dates
        ):
            print(message, flush=True)
        _append_progress(progress_log, message)

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill missing data from FinMind")
    parser.add_argument("--stock-id", dest="stock_id", help="Single stock_id to fill (default: all)")
    parser.add_argument("--from-date", dest="from_date", help="Start date YYYY-MM-DD")
    parser.add_argument("--to-date", dest="to_date", help="End date YYYY-MM-DD")
    parser.add_argument(
        "--component",
        action="append",
        choices=["institutional", "shareholding"],
        default=["institutional"],
        help="Data component: institutional / shareholding",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=4000,
        help="Fetch chunk size in days for long date ranges",
    )
    parser.add_argument("--limit", type=int, help="Maximum number of missing stocks to process")
    parser.add_argument(
        "--state-file",
        default="logs/finmind_institutional_backfill_done.txt",
        help="Stock IDs already attempted in this batch run; use an empty string to disable",
    )
    parser.add_argument("--progress-log", help="Append per-stock progress to this log file")
    parser.add_argument("--verbose", action="store_true", help="Print per-stock progress")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-stock terminal output")
    parser.add_argument("--token", help="FinMind token (falls back to FINMIND_TOKEN)")
    parser.add_argument("--dry-run", action="store_true", help="Only report missing counts")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    include_shareholding = "shareholding" in set(args.component)
    results = run_backfill(
        stock_id=args.stock_id,
        from_date=args.from_date,
        to_date=args.to_date,
        include_shareholding=include_shareholding,
        chunk_days=args.chunk_days,
        token=args.token,
        dry_run=args.dry_run,
        limit=args.limit,
        verbose=args.verbose,
        state_file=args.state_file or None,
        progress_log=args.progress_log,
        quiet=args.quiet,
    )

    total = len(results)
    with_incomplete = sum(1 for row in results if not row.ok)
    total_inst_missing = sum(row.missing_institutional_dates for row in results)
    total_shar_missing = sum(row.missing_shareholding_dates for row in results)
    total_inst_remaining = sum(row.remaining_institutional_dates for row in results)
    total_shar_remaining = sum(row.remaining_shareholding_dates for row in results)
    total_inst_filled = sum(row.institutional for row in results)
    total_shar_filled = sum(row.shareholding for row in results)

    print(f"target_stocks={total}, incomplete={with_incomplete}, dry_run={args.dry_run}")
    missing_line = (
        "missing={"
        f"\"institutional\": {total_inst_missing}, "
        f"\"shareholding\": {total_shar_missing}"
        "}"
    )
    remaining_line = (
        "remaining={"
        f"\"institutional\": {total_inst_remaining}, "
        f"\"shareholding\": {total_shar_remaining}"
        "}"
    )
    print(missing_line)
    print(remaining_line)
    _append_progress(args.progress_log, f"target_stocks={total}, incomplete={with_incomplete}, dry_run={args.dry_run}")
    _append_progress(args.progress_log, missing_line)
    _append_progress(args.progress_log, remaining_line)
    if total_inst_filled or total_shar_filled:
        print(
            "filled={"
            f"\"institutional\": {total_inst_filled}, "
            f"\"shareholding\": {total_shar_filled}"
            "}"
        )
    if not args.quiet:
        for row in results:
            if row.ok:
                continue
            print(_format_row(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
