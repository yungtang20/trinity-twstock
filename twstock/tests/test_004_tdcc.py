"""
Test Cases for Issue 004: TDCC Shareholding Fetcher
Unit Test (mock HTTP) — DoD 必跑

執行（DoD）：  python -m pytest tests/test_004_tdcc.py -v -m "not live"
執行（live）： python -m pytest tests/test_004_tdcc.py -v -m live
"""

import sqlite3

import pytest

from twstock.market_data.historical_fetcher import TDCCFetcher


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE shareholding_unified (
            stock_id       TEXT NOT NULL,
            date           TEXT NOT NULL,
            source         TEXT NOT NULL,
            total_shares   INTEGER,
            whale_ratio    REAL,
            retail_ratio   REAL,
            foreign_shares INTEGER,
            foreign_ratio  REAL,
            total_people   INTEGER,
            whale_shares   INTEGER,
            whale_people   INTEGER,
            updated_at     TEXT,
            PRIMARY KEY (stock_id, date, source)
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def raw_tdcc_2330():
    """
    TDCC 集保資料（2330，2024-01-05，已解析為 list of dict）。
    date_roc = '1130105'（ROC 113年01月05日）
    whale（400001以上）: shares=5009000000, people=100
    retail（1~999 + 1000~5000 + 5001~10000）:
        2000000 + 20000000 + 21000000 = 43000000 shares
    total（合計）: shares=5254000000, people=20500
    whale_ratio = 5009000000 / 5254000000 * 100 ≈ 95.3384
    retail_ratio = 43000000 / 5254000000 * 100 ≈ 0.8184
    """
    return [
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "1~999",
            "people": 5000,
            "shares": 2000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "1000~5000",
            "people": 8000,
            "shares": 20000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "5001~10000",
            "people": 3000,
            "shares": 21000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "10001~15000",
            "people": 1500,
            "shares": 18000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "15001~20000",
            "people": 800,
            "shares": 14000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "20001~30000",
            "people": 600,
            "shares": 14000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "30001~40000",
            "people": 300,
            "shares": 11000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "40001~50000",
            "people": 200,
            "shares": 9000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "50001~100000",
            "people": 500,
            "shares": 37000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "100001~200000",
            "people": 300,
            "shares": 44000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "200001~400000",
            "people": 200,
            "shares": 55000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "400001以上",
            "people": 100,
            "shares": 5009000000,
        },
        {
            "date_roc": "1130105",
            "stock_id": "2330",
            "bracket": "合計",
            "people": 20500,
            "shares": 5254000000,
        },
    ]


@pytest.fixture
def fetcher(db, monkeypatch, raw_tdcc_2330):
    f = TDCCFetcher(db=db)
    monkeypatch.setattr(f, "fetch_by_date", lambda *a, **k: raw_tdcc_2330)
    return f


class TestTC1Transform:
    """TC1: 基本欄位正確性"""

    def test_output_row_count(self, fetcher, raw_tdcc_2330):
        """一股一日 → 一列輸出"""
        rows = fetcher._transform(raw_tdcc_2330)
        assert len(rows) == 1, f"預期 1 列，實際 {len(rows)}"

    def test_required_columns_exist(self, fetcher, raw_tdcc_2330):
        rows = fetcher._transform(raw_tdcc_2330)
        required = {
            "stock_id",
            "date",
            "source",
            "total_shares",
            "total_people",
            "whale_shares",
            "whale_people",
            "whale_ratio",
            "retail_ratio",
        }
        assert required.issubset(set(rows[0].keys())), f"缺少欄位: {required - set(rows[0].keys())}"


class TestTC2DateConversion:
    """TC2: ROC 日期 YYYYMMDD → YYYY-MM-DD"""

    def test_roc_date_conversion(self, fetcher, raw_tdcc_2330):
        """'1130105' → '2024-01-05'"""
        rows = fetcher._transform(raw_tdcc_2330)
        assert rows[0]["date"] == "2024-01-05", f"date 應為 2024-01-05，實際 {rows[0]['date']}"


class TestTC3WhaleShares:
    """TC3: whale_shares = 400001以上 bracket 的 shares"""

    def test_whale_shares(self, fetcher, raw_tdcc_2330):
        rows = fetcher._transform(raw_tdcc_2330)
        assert (
            rows[0]["whale_shares"] == 5009000000
        ), f"whale_shares 應為 5009000000，實際 {rows[0]['whale_shares']}"


class TestTC4WhaleRatio:
    """TC4: whale_ratio = whale_shares / total_shares * 100"""

    def test_whale_ratio(self, fetcher, raw_tdcc_2330):
        rows = fetcher._transform(raw_tdcc_2330)
        expected = 5009000000 / 5254000000 * 100
        assert (
            abs(rows[0]["whale_ratio"] - expected) < 0.001
        ), f"whale_ratio 應為 {expected:.4f}，實際 {rows[0]['whale_ratio']}"


class TestTC5RetailShares:
    """TC5: retail = 1~999 + 1000~5000 + 5001~10000 三個 bracket 合計"""

    def test_retail_shares_sum(self, fetcher, raw_tdcc_2330):
        """2000000 + 20000000 + 21000000 = 43000000"""
        rows = fetcher._transform(raw_tdcc_2330)
        retail_shares = rows[0]["retail_ratio"] / 100 * 5254000000
        assert (
            abs(retail_shares - 43000000) < 1
        ), f"retail_shares 應為 43000000，推算值 {retail_shares}"


class TestTC6RetailRatio:
    """TC6: retail_ratio = retail_shares / total_shares * 100"""

    def test_retail_ratio(self, fetcher, raw_tdcc_2330):
        rows = fetcher._transform(raw_tdcc_2330)
        expected = 43000000 / 5254000000 * 100
        assert (
            abs(rows[0]["retail_ratio"] - expected) < 0.001
        ), f"retail_ratio 應為 {expected:.4f}，實際 {rows[0]['retail_ratio']}"


class TestTC7TotalShares:
    """TC7: total_shares 來自合計 bracket"""

    def test_total_shares(self, fetcher, raw_tdcc_2330):
        rows = fetcher._transform(raw_tdcc_2330)
        assert (
            rows[0]["total_shares"] == 5254000000
        ), f"total_shares 應為 5254000000，實際 {rows[0]['total_shares']}"


class TestTC8Source:
    """TC8: source == 'tdcc'"""

    def test_source_is_tdcc(self, fetcher, raw_tdcc_2330):
        rows = fetcher._transform(raw_tdcc_2330)
        assert rows[0]["source"] == "tdcc", f"source 應為 'tdcc'，實際 {rows[0]['source']}"


class TestTC9SaveToTable:
    """TC9: 寫入 shareholding_unified（非 VIEW）"""

    def test_save_writes_to_shareholding_unified(self, fetcher, db):
        fetcher.fetch_and_save("2024-01-05")
        cur = db.execute(
            "SELECT COUNT(*) FROM shareholding_unified " "WHERE stock_id='2330' AND source='tdcc'"
        )
        assert cur.fetchone()[0] == 1, "預期 1 筆寫入 shareholding_unified"


class TestTC10Integration:
    """TC10: fetch_and_save 串接"""

    def test_fetch_and_save_writes_correctly(self, fetcher, db):
        fetcher.fetch_and_save("2024-01-05")
        cur = db.execute(
            "SELECT date, whale_shares, total_shares, source "
            "FROM shareholding_unified WHERE stock_id='2330'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "2024-01-05", f"date 錯：{row[0]}"
        assert row[1] == 5009000000, f"whale_shares 錯：{row[1]}"
        assert row[2] == 5254000000, f"total_shares 錯：{row[2]}"
        assert row[3] == "tdcc", f"source 錯：{row[3]}"

    def test_dedup(self, fetcher, db):
        fetcher.fetch_and_save("2024-01-05")
        fetcher.fetch_and_save("2024-01-05")
        cur = db.execute(
            "SELECT COUNT(*) FROM shareholding_unified "
            "WHERE stock_id='2330' AND date='2024-01-05'"
        )
        assert cur.fetchone()[0] == 1, "重複寫入應只保留 1 筆"
