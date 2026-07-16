"""
Test Cases for Issue 005: Dividend Events Fetcher
Unit Test (mock HTTP) — DoD 必跑

執行（DoD）：  python -m pytest tests/test_005_dividend.py -v -m "not live"
執行（live）： python -m pytest tests/test_005_dividend.py -v -m live
"""

import sqlite3

import pytest

from twstock.market_data.historical_fetcher import DividendFetcher


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE dividend_events (
            stock_id        TEXT NOT NULL,
            date            TEXT NOT NULL,
            before_price    REAL,
            after_price     REAL,
            reference_price REAL,
            cash_dividend   REAL DEFAULT 0,
            stock_dividend  REAL DEFAULT 0,
            source          TEXT,
            updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (stock_id, date)
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def raw_dividend_2330():
    """
    FinMind TaiwanStockDividend 回應（2330，兩次除權息）。
    2023-07-21: 現金股利 3.0 元，無股票股利
    2022-07-22: 現金股利 3.0 元，無股票股利
    """
    return {
        "msg": "success",
        "status": 200,
        "data": [
            {
                "date": "2023-07-21",
                "stock_id": "2330",
                "beforeDividend": 543.0,
                "afterDividend": 528.5,
                "reference": 528.5,
                "CashDividend": 3.0,
                "StockDividend": 0.0,
            },
            {
                "date": "2022-07-22",
                "stock_id": "2330",
                "beforeDividend": 529.0,
                "afterDividend": 514.5,
                "reference": 514.5,
                "CashDividend": 3.0,
                "StockDividend": 0.0,
            },
        ],
    }


@pytest.fixture
def fetcher(db, monkeypatch, raw_dividend_2330):
    f = DividendFetcher(api_token="fake-token", db=db)
    monkeypatch.setattr(f, "fetch_dividend", lambda *a, **k: raw_dividend_2330)
    return f


class TestTC1Transform:
    """TC1: 基本正確性"""

    def test_row_count(self, fetcher, raw_dividend_2330):
        rows = fetcher._transform(raw_dividend_2330)
        assert len(rows) == 2, f"預期 2 列，實際 {len(rows)}"

    def test_required_columns_exist(self, fetcher, raw_dividend_2330):
        rows = fetcher._transform(raw_dividend_2330)
        required = {
            "stock_id",
            "date",
            "before_price",
            "after_price",
            "reference_price",
            "cash_dividend",
            "stock_dividend",
            "source",
        }
        assert required.issubset(set(rows[0].keys())), f"缺少欄位: {required - set(rows[0].keys())}"


class TestTC2BeforePrice:
    """TC2: before_price 正確"""

    def test_before_price(self, fetcher, raw_dividend_2330):
        rows = fetcher._transform(raw_dividend_2330)
        row = next(r for r in rows if r["date"] == "2023-07-21")
        assert row["before_price"] == 543.0, f"before_price 應為 543.0，實際 {row['before_price']}"


class TestTC3ReferencePrice:
    """TC3: reference_price 正確"""

    def test_reference_price(self, fetcher, raw_dividend_2330):
        rows = fetcher._transform(raw_dividend_2330)
        row = next(r for r in rows if r["date"] == "2023-07-21")
        assert (
            row["reference_price"] == 528.5
        ), f"reference_price 應為 528.5，實際 {row['reference_price']}"


class TestTC4Dividends:
    """TC4: cash_dividend / stock_dividend 正確"""

    def test_cash_dividend(self, fetcher, raw_dividend_2330):
        rows = fetcher._transform(raw_dividend_2330)
        row = next(r for r in rows if r["date"] == "2023-07-21")
        assert row["cash_dividend"] == 3.0, f"cash_dividend 應為 3.0，實際 {row['cash_dividend']}"

    def test_stock_dividend(self, fetcher, raw_dividend_2330):
        rows = fetcher._transform(raw_dividend_2330)
        row = next(r for r in rows if r["date"] == "2023-07-21")
        assert (
            row["stock_dividend"] == 0.0
        ), f"stock_dividend 應為 0.0，實際 {row['stock_dividend']}"


class TestTC5Dedup:
    """TC5: 同 (stock_id, date) 去重"""

    def test_dedup(self, fetcher, db):
        fetcher.fetch_and_save("2330", "2022-01-01", "2023-12-31")
        fetcher.fetch_and_save("2330", "2022-01-01", "2023-12-31")
        cur = db.execute(
            "SELECT COUNT(*) FROM dividend_events WHERE stock_id='2330' AND date='2023-07-21'"
        )
        assert cur.fetchone()[0] == 1


class TestTC6Source:
    """TC6: source == 'finmind'"""

    def test_source_is_finmind(self, fetcher, raw_dividend_2330):
        rows = fetcher._transform(raw_dividend_2330)
        for r in rows:
            assert r["source"] == "finmind", f"source 應為 'finmind'，實際 {r['source']}"


class TestTC7EmptyData:
    """TC7: empty data 拋 Exception"""

    def test_empty_data_raises(self, fetcher):
        empty = {"msg": "success", "status": 200, "data": []}
        with pytest.raises(Exception) as exc_info:
            fetcher._transform(empty)
        msg = str(exc_info.value).lower()
        assert "empty" in msg or "空" in msg


class TestTC8Integration:
    """TC8: fetch_and_save 串接"""

    def test_writes_to_db(self, fetcher, db):
        fetcher.fetch_and_save("2330", "2022-01-01", "2023-12-31")
        cur = db.execute("SELECT COUNT(*) FROM dividend_events WHERE stock_id='2330'")
        assert cur.fetchone()[0] == 2

    def test_column_values(self, fetcher, db):
        fetcher.fetch_and_save("2330", "2022-01-01", "2023-12-31")
        cur = db.execute(
            "SELECT before_price, reference_price, cash_dividend, source "
            "FROM dividend_events WHERE stock_id='2330' AND date='2023-07-21'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 543.0, f"before_price 錯：{row[0]}"
        assert row[1] == 528.5, f"reference_price 錯：{row[1]}"
        assert row[2] == 3.0, f"cash_dividend 錯：{row[2]}"
        assert row[3] == "finmind", f"source 錯：{row[3]}"
