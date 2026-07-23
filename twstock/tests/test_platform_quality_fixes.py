"""Regression coverage for platform-level data and safety fixes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import requests


def _seed_history(conn, stock_id: str = "2330", days: int = 10) -> None:
    for day in range(1, days + 1):
        conn.execute(
            """
            INSERT INTO stock_history
            (stock_id, date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stock_id,
                f"2026-01-{day:02d}",
                100 + day,
                102 + day,
                99 + day,
                101 + day,
                1_000_000,
                101_000_000,
            ),
        )
    conn.commit()


def test_indicator_engine_uses_latest_rows_and_current_join_schema(patch_db_path) -> None:
    from twstock.calculator import IndicatorEngine
    from twstock.db import get_connection
    from twstock.db_admin import init_db

    init_db()
    conn = get_connection()
    try:
        _seed_history(conn)
        conn.execute(
            """
            INSERT INTO institutional_data
            (stock_id, date, foreign_net, trust_net, dealer_net, institutional_net,
             foreign_buy, foreign_sell, trust_buy, trust_sell, dealer_buy, dealer_sell)
            VALUES ('2330', '2026-01-10', 10, 20, 30, 60, 100, 90, 50, 30, 20, 10)
            """
        )
        conn.execute(
            """
            INSERT INTO shareholding_unified
            (stock_id, date, source, foreign_shares, foreign_ratio)
            VALUES ('2330', '2026-01-10', 'twse_foreign', 123456, 12.34)
            """
        )
        conn.commit()
    finally:
        conn.close()

    frame = IndicatorEngine("2330", limit=3).build()
    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-08",
        "2026-01-09",
        "2026-01-10",
    ]
    latest = frame.iloc[-1]
    assert latest["foreign_net"] == 10
    assert latest["foreign_shares"] == 123456


def test_calculators_support_batched_full_market_refresh(db_conn) -> None:
    from twstock.calculator import ATRCalculator, MACalculator, VWAPCalculator
    from twstock.db_admin import create_tables

    create_tables(db_conn)
    _seed_history(db_conn, "2330", days=30)
    _seed_history(db_conn, "2317", days=30)

    for calculator in (ATRCalculator(db_conn), VWAPCalculator(db_conn), MACalculator(db_conn)):
        counts = calculator.calculate_all()
        assert counts == {"2317": 30, "2330": 30}

    count = db_conn.execute("SELECT COUNT(*) FROM stock_indicators").fetchone()[0]
    assert count == 60


def test_bootstrap_creates_legacy_shareholding_projection(db_conn) -> None:
    from twstock.db_admin import create_tables, create_views

    create_tables(db_conn)
    create_views(db_conn)
    object_type = db_conn.execute(
        "SELECT type FROM sqlite_master WHERE name = 'shareholding_data'"
    ).fetchone()[0]
    assert object_type == "view"


@patch("twstock.retry.requests.get")
def test_tls_error_never_triggers_implicit_insecure_retry(mock_get: MagicMock) -> None:
    from twstock.retry import retry_get

    mock_get.side_effect = requests.exceptions.SSLError("untrusted certificate")
    assert retry_get("https://example.test", retries=0, ssl_fallback=True) is None
    assert mock_get.call_count == 1
    assert mock_get.call_args.kwargs["verify"] is True


def test_normalized_result_contract_uses_uppercase_json_signal() -> None:
    from twstock.strategy.result_contract import normalize_strategy_result

    result = normalize_strategy_result({"signal": "bullish"}, strategy="ma", stock_id="2330")
    assert result["signal"] == "BUY"
    assert result["score"] == 75
    assert isinstance(pd.DataFrame([result]).to_dict(orient="records"), list)


def test_sr_market_scan_passes_latest_date_to_batch(monkeypatch) -> None:
    """Regression: omitting latest_date turns SQLite date('0') into NULL."""
    import sqlite3

    from twstock.strategy import sr_analyzer

    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE stock_history (
            stock_id TEXT, date TEXT, close REAL, volume INTEGER
        );
        CREATE TABLE stock_meta (stock_id TEXT, stock_name TEXT);
        INSERT INTO stock_history VALUES ('2330', '2026-07-21', 100, 1000000);
        INSERT INTO stock_meta VALUES ('2330', '台積電');
    """)
    captured: dict[str, object] = {}

    def fake_batch(_conn, stocks, name_map, min_volume, latest_date):
        captured.update(
            stocks=stocks,
            name_map=name_map,
            min_volume=min_volume,
            latest_date=latest_date,
        )
        return []

    monkeypatch.setattr(sr_analyzer, "_scan_with_progress_basic", fake_batch)
    sr_analyzer._SR_CACHE.update({"date": None, "results": None, "ts": 0})
    try:
        sr_analyzer.scan_market_stocks(conn, min_volume_zhang=500)
    finally:
        conn.close()

    assert captured["latest_date"] == "2026-07-21"
    assert captured["stocks"] == ["2330"]


def test_sr_two_levels_keep_distinct_short_and_long_values() -> None:
    from twstock.strategy.sr_analyzer import _calc_levels

    assert _calc_levels([101.0, 105.0], True, 100.0) == (101.0, 105.0, 105.0)
    assert _calc_levels([90.0, 95.0], False, 100.0) == (95.0, 90.0, 90.0)
