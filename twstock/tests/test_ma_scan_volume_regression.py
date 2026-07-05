import sqlite3
from datetime import date, timedelta

from twstock.strategy import ma_strategy


def _create_schema(conn: sqlite3.Connection):
    conn.execute("""CREATE TABLE stock_history (
            stock_id TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            PRIMARY KEY(stock_id, date)
        )""")
    conn.execute("""CREATE TABLE stock_indicators (
            stock_id TEXT NOT NULL,
            date TEXT NOT NULL,
            ma5 REAL, ma20 REAL, ma25 REAL, ma60 REAL, ma200 REAL,
            vol_ma5 REAL, vol_ma20 REAL, vol_ma60 REAL,
            PRIMARY KEY(stock_id, date)
        )""")
    conn.execute(
        "CREATE VIEW klines AS SELECT stock_id, date, open, high, low, close, CAST(volume AS REAL) AS volume, CAST(amount AS REAL) AS amount FROM stock_history"
    )
    conn.execute("""
        CREATE VIEW klines_indicators AS
        SELECT k.stock_id, k.date, k.open, k.high, k.low, k.close, k.volume, k.amount,
               i.ma5, i.ma20, i.ma25, i.ma60, i.ma200, i.vol_ma5, i.vol_ma20, i.vol_ma60
        FROM klines k LEFT JOIN stock_indicators i ON k.stock_id=i.stock_id AND k.date=i.date
        """)


def test_scan_excludes_below_min_volume():
    """Regression: ensure stocks with latest volume below min_volume (張) are excluded.

    Scenario: stock A has latest volume = 4,000 (4 張) -> should NOT appear when min_volume=500.
              stock B has latest volume = 600,000 (600 張) -> should appear.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_schema(conn)

    # build dates
    start = date(2026, 1, 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(205)]

    # stock A: low latest volume
    a = "9001"
    # make price series so that the latest day is a clear breakout above MA
    closes = [1.0] * 203 + [1.0, 200.0]
    vols_a = [600000] * 204 + [4000]  # last day low (4 張)
    for d, c, v in zip(dates, closes, vols_a, strict=True):
        conn.execute(
            "INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (a, d, c, c, c, c, v, int(c * v)),
        )
    conn.execute(
        "INSERT INTO stock_indicators (stock_id, date, ma200, ma60) VALUES (?, ?, ?, ?)",
        (a, dates[-1], 100.0, 100.0),
    )

    # stock B: valid high volume
    b = "9002"
    vols_b = [600000] * 204 + [700000]  # ensure curr_vol > prev_vol
    for d, c, v in zip(dates, closes, vols_b, strict=True):
        conn.execute(
            "INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (b, d, c, c, c, c, v, int(c * v)),
        )
    conn.execute(
        "INSERT INTO stock_indicators (stock_id, date, ma200, ma60) VALUES (?, ?, ?, ?)",
        (b, dates[-1], 100.0, 100.0),
    )
    conn.commit()

    captured = []

    def fake_display(results, latest_date, sort_choice, strat_choice):
        captured.append(results)

    orig = ma_strategy._display_scan_results
    ma_strategy._display_scan_results = fake_display
    try:
        ma_strategy.scan_market_stocks(conn, min_volume=500, strat_choice="1", sort_choice="1")
    finally:
        ma_strategy._display_scan_results = orig

    # ensure we captured results and that stock B appears but A does not
    assert captured, "No scan output captured"
    codes = {r["code"] for r in captured[0]}
    assert b in codes, f"stock {b} should be present for min_volume=500"
    assert a not in codes, f"stock {a} should NOT be present (below min_volume)"
