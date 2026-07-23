"""Conservative, repeatable repair for known data-quality corruption.

This command never downloads or invents market data.  It only removes rows
that are provably unusable (for example impossible OHLC ranges, orphaned
derived indicators, and payloads that were written with every metric blank).
Run it without ``--apply`` first to inspect the effect.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from twstock.db import DB_PATH


logger = logging.getLogger(__name__)


INVALID_OHLC_PREDICATE = """
(
    open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
    OR high < open OR high < close OR high < low
    OR low > open OR low > close OR low > high
)
"""

BLANK_FOREIGN_PREDICATE = """
source = 'twse_foreign'
AND foreign_shares IS NULL AND foreign_ratio IS NULL
AND total_shares IS NULL AND whale_ratio IS NULL AND retail_ratio IS NULL
AND total_people IS NULL AND whale_shares IS NULL AND whale_people IS NULL
"""

BLANK_INSTITUTIONAL_PREDICATE = """
foreign_net IS NULL AND trust_net IS NULL AND dealer_net IS NULL
AND institutional_net IS NULL
AND foreign_buy IS NULL AND foreign_sell IS NULL
AND trust_buy IS NULL AND trust_sell IS NULL
AND dealer_buy IS NULL AND dealer_sell IS NULL
"""


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _optional_count(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    """Return a count for diagnostics that depend on optional project tables."""
    try:
        row = conn.execute(sql, params).fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0] if row else 0)


def collect_quality_report(conn: sqlite3.Connection, today: str | None = None) -> dict[str, int]:
    """Return deterministic corruption counts and read-only TDCC quality diagnostics."""
    today = today or date.today().isoformat()
    checks = {
        "invalid_history": f"SELECT COUNT(*) FROM stock_history WHERE {INVALID_OHLC_PREDICATE}",
        "orphan_indicators": """
            SELECT COUNT(*) FROM stock_indicators AS indicator
            WHERE NOT EXISTS (
                SELECT 1 FROM stock_history AS history
                WHERE history.stock_id = indicator.stock_id AND history.date = indicator.date
            )
        """,
        "blank_foreign_shareholding": ("SELECT COUNT(*) FROM shareholding_unified WHERE " + BLANK_FOREIGN_PREDICATE),
        "future_shareholding": "SELECT COUNT(*) FROM shareholding_unified WHERE date > ?",
        "tdcc_incomplete_rows": """
            SELECT COUNT(*) FROM shareholding_unified
            WHERE source = 'tdcc' AND (
                total_shares IS NULL OR whale_ratio IS NULL
                OR total_people IS NULL OR whale_shares IS NULL
            )
        """,
        "tdcc_missing_whale_people": """
            SELECT COUNT(*) FROM shareholding_unified
            WHERE source = 'tdcc' AND whale_people IS NULL
        """,
        "tdcc_tiny_periods": """
            SELECT COUNT(*) FROM (
                SELECT date FROM shareholding_unified
                WHERE source = 'tdcc'
                GROUP BY date
                HAVING COUNT(DISTINCT stock_id) < 50
            )
        """,
        "tdcc_weekend_periods": """
            SELECT COUNT(DISTINCT date) FROM shareholding_unified
            WHERE source = 'tdcc' AND strftime('%w', date) IN ('0', '6')
        """,
        "tdcc_large_gaps": """
            WITH periods AS (
                SELECT date,
                       LAG(date) OVER (ORDER BY date) AS previous_date
                FROM shareholding_unified
                WHERE source = 'tdcc'
                GROUP BY date
            )
            SELECT COUNT(*) FROM periods
            WHERE julianday(date) - julianday(previous_date) > 10
        """,
        "blank_institutional": ("SELECT COUNT(*) FROM institutional_data WHERE " + BLANK_INSTITUTIONAL_PREDICATE),
    }
    report: dict[str, int] = {}
    for name, sql in checks.items():
        params: tuple[str, ...] = (today,) if name == "future_shareholding" else ()
        report[name] = int(conn.execute(sql, params).fetchone()[0])

    # These are explanatory completeness diagnostics, not corruption counts.
    # A stock can have a valid K-line but no institutional payload from a data
    # provider for that date, so these values must not be used for deletion.
    if _table_exists(conn, "stock_meta"):
        report["common_institutional_missing"] = _optional_count(
            conn,
            """
            SELECT COUNT(*) FROM stock_history h
            JOIN stock_meta m ON m.stock_id = h.stock_id
            LEFT JOIN institutional_data i
              ON i.stock_id = h.stock_id
             AND i.date = h.date
            WHERE m.type = 'COMMON'
              AND m.market IN ('TSE', 'OTC')
              AND i.date IS NULL
            """,
        )
        report["common_active_institutional_missing"] = _optional_count(
            conn,
            """
            SELECT COUNT(*) FROM stock_history h
            JOIN stock_meta m ON m.stock_id = h.stock_id
            JOIN (
                SELECT stock_id FROM stock_history
                WHERE date = (SELECT MAX(date) FROM stock_history)
            ) active ON active.stock_id = h.stock_id
            LEFT JOIN institutional_data i
              ON i.stock_id = h.stock_id
             AND i.date = h.date
            WHERE m.type = 'COMMON'
              AND m.market IN ('TSE', 'OTC')
              AND i.date IS NULL
            """,
        )
    else:
        report["common_institutional_missing"] = 0
        report["common_active_institutional_missing"] = 0

    if _table_exists(conn, "stock_trading_calendar"):
        report["history_on_calendar_closed_days"] = _optional_count(
            conn,
            """
            SELECT COUNT(*) FROM stock_history h
            JOIN stock_trading_calendar c ON c.date = h.date
            WHERE COALESCE(c.is_open, 0) = 0
            """,
        )
        report["history_missing_calendar_dates"] = _optional_count(
            conn,
            """
            SELECT COUNT(*) FROM stock_history h
            LEFT JOIN stock_trading_calendar c ON c.date = h.date
            WHERE c.date IS NULL
            """,
        )
    else:
        report["history_on_calendar_closed_days"] = 0
        report["history_missing_calendar_dates"] = 0
    return report


def repair_database(
    db_path: str | Path = DB_PATH,
    *,
    apply: bool = False,
    today: str | None = None,
) -> dict[str, int]:
    """Inspect or remove rows matching deterministic corruption predicates.

    ``apply=False`` is intentionally the default.  In apply mode every
    mutation occurs in one transaction and an audit-log row records the
    removed counts, so this operation is repeatable and traceable.
    """
    db_path = str(db_path)
    if apply:
        conn = sqlite3.connect(db_path)
    else:
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    try:
        report = collect_quality_report(conn, today=today)
        if not apply:
            return report

        today = today or date.today().isoformat()
        conn.execute("BEGIN IMMEDIATE")

        # Derived rows without a source candle can never be used correctly.
        conn.execute(
            """
            DELETE FROM stock_indicators AS indicator
            WHERE NOT EXISTS (
                SELECT 1 FROM stock_history AS history
                WHERE history.stock_id = indicator.stock_id AND history.date = indicator.date
            )
            """
        )
        # An all-null row is a failed ingestion payload, not a zero-position.
        conn.execute("DELETE FROM shareholding_unified WHERE " + BLANK_FOREIGN_PREDICATE)
        conn.execute("DELETE FROM shareholding_unified WHERE date > ?", (today,))
        conn.execute("DELETE FROM institutional_data WHERE " + BLANK_INSTITUTIONAL_PREDICATE)

        # Incorrect prices are worse than a missing day.  Correct values must
        # be restored by a later, validated source refresh rather than guessed.
        conn.execute("DELETE FROM stock_history WHERE " + INVALID_OHLC_PREDICATE)
        conn.execute(
            """
            DELETE FROM stock_indicators AS indicator
            WHERE NOT EXISTS (
                SELECT 1 FROM stock_history AS history
                WHERE history.stock_id = indicator.stock_id AND history.date = indicator.date
            )
            """
        )

        detail = json.dumps(report, ensure_ascii=False, sort_keys=True)
        conn.execute(
            "INSERT INTO audit_log (action, status, detail) VALUES (?, ?, ?)",
            ("data_repair", "success", detail),
        )
        conn.commit()
        return report
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    """Build the standalone repair command parser."""
    parser = argparse.ArgumentParser(description="Inspect or repair known SQLite data corruption")
    parser.add_argument("--database", default=DB_PATH, help="SQLite database path")
    parser.add_argument("--apply", action="store_true", help="Apply the deterministic repairs")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a shell-friendly status code."""
    args = build_parser().parse_args(argv)
    report = repair_database(args.database, apply=args.apply)
    print(json.dumps({"applied": args.apply, "counts": report}, ensure_ascii=False, indent=2))
    if not args.apply:
        logger.info("Dry run only. Re-run with --apply after reviewing the counts.")
    return 0


def execute(args: Any) -> None:
    """Command-package compatibility wrapper.

    The main CLI does not register this maintenance task yet, but every module
    in ``commands`` exposes ``execute(args)``.  Keeping this wrapper makes the
    repair module discoverable without creating a second CLI contract.
    """
    database = getattr(args, "database", DB_PATH)
    apply = bool(getattr(args, "apply", False))
    report = repair_database(database, apply=apply)
    print(json.dumps({"applied": apply, "counts": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
