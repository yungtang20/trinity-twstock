"""Bug Fix: fetcher.py 不應轉換單位，DB 存原始值（股/元）"""

import inspect


def test_fetch_history_price_does_not_convert_volume():
    """fetch_history_price 不應將 volume 除以 1000"""
    from twstock.market_data.historical_fetcher import DataFetcher

    source = inspect.getsource(DataFetcher.fetch_history_price)
    assert (
        "// 1000" not in source
    ), "fetch_history_price 不應將 volume // 1000（股→張），DB 存原始股數"


def test_fetch_history_price_does_not_convert_amount():
    """fetch_history_price 不應將 amount 除以 1e7"""
    from twstock.market_data.historical_fetcher import DataFetcher

    source = inspect.getsource(DataFetcher.fetch_history_price)
    assert (
        "/ 10000000" not in source
    ), "fetch_history_price 不應將 amount / 1e7（元→千萬元），DB 存原始元"
    assert "1e7" not in source, "fetch_history_price 不應將 amount / 1e7"


def test_fetch_institutional_does_not_convert_units():
    """fetch_institutional 不應將法人買賣超除以 1000"""
    from twstock.market_data.historical_fetcher import DataFetcher

    source = inspect.getsource(DataFetcher.fetch_institutional)
    assert (
        "// 1000" not in source
    ), "fetch_institutional 不應將 foreign_buy 等 // 1000，DB 存原始股數"


def test_volume_stored_as_raw_shares():
    """確認 DB 中 volume 是原始股數（不是張數）"""
    from db import get_connection

    conn = get_connection(readonly=True)
    row = conn.execute(
        "SELECT volume FROM stock_history WHERE volume > 0 ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        assert row[0] > 0
