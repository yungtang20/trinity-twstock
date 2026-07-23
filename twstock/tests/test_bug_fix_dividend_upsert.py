"""Regression tests for idempotent dividend writes using an isolated DB."""

from __future__ import annotations

import inspect

import pandas as pd


def test_no_delete_loop() -> None:
    from twstock.official.dividend_crawler import upsert_dividend_events

    assert "DELETE FROM" not in inspect.getsource(upsert_dividend_events)


def test_no_bare_sqlite3_connect() -> None:
    from twstock.official.dividend_crawler import upsert_dividend_events

    assert "sqlite3.connect(" not in inspect.getsource(upsert_dividend_events)


def test_duplicate_writes_are_idempotent(patch_db_path) -> None:
    from twstock.db import get_connection
    from twstock.db_admin import init_db
    from twstock.official.dividend_crawler import upsert_dividend_events

    init_db()
    events = pd.DataFrame(
        [
            {
                "stock_id": "9999",
                "date": "2099-01-01",
                "before_price": 100.0,
                "after_price": 95.0,
                "reference_price": 95.0,
                "cash_dividend": 5.0,
                "stock_dividend": 0.0,
                "source": "test",
            }
        ]
    )
    upsert_dividend_events(events)
    upsert_dividend_events(events)
    with get_connection(readonly=True) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM dividend_events WHERE stock_id = ? AND date = ?",
            ("9999", "2099-01-01"),
        ).fetchone()[0]
    assert count == 1
