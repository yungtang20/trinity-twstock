#!/usr/bin/env python3
"""Rebuild persisted technical indicators from validated SQLite daily bars.

Use a single stock first when checking a newly repaired data source:

``python scripts/backfill_indicators.py --stock-id 2330``

The no-argument form intentionally performs the full-market rebuild.  It uses
the project's connection factory and batched calculators; it never opens a
second ad-hoc SQLite connection.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Callable, Protocol, TypeAlias

# This file is a supported direct maintenance entry point.  Add only the
# package parent, never the package directory itself, to preserve one module
# identity for ``twstock.db``.
if __package__ in {None, ""}:
    package_parent = str(Path(__file__).resolve().parents[2])
    if package_parent not in sys.path:
        sys.path.insert(0, package_parent)

from twstock.calculator import ATRCalculator, MACalculator, VWAPCalculator
from twstock.db import get_connection


class IndicatorCalculator(Protocol):
    """Common callable surface shared by the persisted indicator calculators."""

    def calculate(self, stock_id: str) -> int:
        """Persist this indicator family for one stock."""

    def calculate_all(self) -> dict[str, int]:
        """Persist this indicator family for every stock."""


CalculatorFactory: TypeAlias = Callable[[sqlite3.Connection], IndicatorCalculator]
_CALCULATORS: dict[str, CalculatorFactory] = {
    "ma": MACalculator,
    "atr": ATRCalculator,
    "vwap": VWAPCalculator,
}


def backfill_indicators(
    *, stock_id: str | None = None, components: tuple[str, ...] = ("ma", "atr", "vwap")
) -> dict[str, int]:
    """Recalculate selected indicator families and return written-row counts."""
    results: dict[str, int] = {}
    conn = get_connection()
    try:
        for component in components:
            calculator = _CALCULATORS[component](conn)
            if stock_id:
                results[component] = int(calculator.calculate(stock_id))
            else:
                totals = calculator.calculate_all()
                results[component] = int(sum(totals.values()))
    finally:
        conn.close()
    return results


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser without changing the main application CLI."""
    parser = argparse.ArgumentParser(description="Rebuild MA, ATR, and VWAP indicators from SQLite")
    parser.add_argument("--stock-id", help="Rebuild one stock instead of the full market")
    parser.add_argument(
        "--component",
        action="append",
        choices=sorted(_CALCULATORS),
        dest="components",
        help="Indicator family to rebuild; repeat to select several",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show selected work without writing")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the maintenance command and emit a concise JSON summary."""
    args = build_parser().parse_args(argv)
    components = tuple(args.components or ("ma", "atr", "vwap"))
    if args.dry_run:
        print(json.dumps({"stock_id": args.stock_id, "components": components, "dry_run": True}))
        return 0

    started = time.perf_counter()
    counts = backfill_indicators(stock_id=args.stock_id, components=components)
    total_elapsed = round(time.perf_counter() - started, 2)
    print(
        json.dumps(
            {
                "stock_id": args.stock_id,
                "components": counts,
                "total_elapsed_seconds": total_elapsed,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
