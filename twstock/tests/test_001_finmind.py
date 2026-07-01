"""
Test Cases for Issue 001: FinMind Data Fetcher
Unit Test (mock HTTP) — DoD 必跑

執行（DoD）：  python -m pytest tests/test_001_finmind.py -v -m "not live"
執行（live）： python -m pytest tests/test_001_finmind.py -v -m live
"""
import sqlite3

import pytest

from fetcher import FinMindFetcher


@pytest.fixture
def db():
    """
    In-memory SQLite，完全依照 taiwan_stock_unified.db 的實際 schema。
    注意：volume 是股（INTEGER），amount 是元（INTEGER），沒有 adj_close。
    """
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE stock_history (
            stock_id    TEXT NOT NULL,
            date        TEXT NOT NULL,
            open        REAL NOT NULL,
            high        REAL NOT NULL,
            low         REAL NOT NULL,
            close       REAL NOT NULL,
            volume      INTEGER NOT NULL,
            amount      INTEGER NOT NULL,
            trade_count INTEGER,
            spread      REAL,
            source      TEXT,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (stock_id, date)
        )
        """
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def raw_2330_3days():
    """
    貼近真實的 FinMind TaiwanStockPrice 回應（2330，三日）。
    Trading_Volume 單位是股，Trading_money 單位是元。
    存入 DB 時不做任何轉換。
    """
    return {
        "msg": "success",
        "status": 200,
        "data": [
            {
                "date": "2024-01-02",
                "stock_id": "2330",
                "Trading_Volume": 31530000,
                "Trading_money": 18750000000,
                "open": 593.0,
                "max": 595.0,
                "min": 590.0,
                "close": 594.0,
                "spread": 2.0,
                "Trading_turnover": 28456,
            },
            {
                "date": "2024-01-03",
                "stock_id": "2330",
                "Trading_Volume": 25010000,
                "Trading_money": 14820000000,
                "open": 592.0,
                "max": 596.0,
                "min": 591.0,
                "close": 593.0,
                "spread": -1.0,
                "Trading_turnover": 22113,
            },
            {
                "date": "2024-01-04",
                "stock_id": "2330",
                "Trading_Volume": 28940000,
                "Trading_money": 17260000000,
                "open": 594.0,
                "max": 598.0,
                "min": 593.0,
                "close": 597.0,
                "spread": 4.0,
                "Trading_turnover": 25887,
            },
        ],
    }


@pytest.fixture
def fetcher(db, monkeypatch, raw_2330_3days):
    """FinMindFetcher 實例，HTTP 層被 mock，不打真實 API。"""
    f = FinMindFetcher(api_token="fake-token", db=db)
    monkeypatch.setattr(f, "fetch_daily", lambda *a, **k: raw_2330_3days)
    return f


class TestTC1Transform:
    """TC1: _transform 基本正確性 — 欄位齊全且不含 adj_close"""

    def test_row_count(self, fetcher, raw_2330_3days):
        rows = fetcher._transform(raw_2330_3days)
        assert len(rows) == 3

    def test_required_columns_exist(self, fetcher, raw_2330_3days):
        rows = fetcher._transform(raw_2330_3days)
        required = {
            "stock_id", "date", "open", "high", "low", "close",
            "volume", "amount", "trade_count", "spread",
            "source",
        }
        assert required.issubset(set(rows[0].keys())), (
            f"缺少欄位: {required - set(rows[0].keys())}"
        )

    def test_no_adj_close_column(self, fetcher, raw_2330_3days):
        rows = fetcher._transform(raw_2330_3days)
        assert "adj_close" not in rows[0], "不應該有 adj_close 欄位"


class TestTC2Volume:
    """TC2: 成交量 — 直接存原始股數，不做 ÷ 1000"""

    def test_volume_raw_value(self, fetcher, raw_2330_3days):
        rows = fetcher._transform(raw_2330_3days)
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["volume"] == 31530000, (
            f"volume 應為 31530000（原始股數），實際 {row['volume']}"
        )


class TestTC3Amount:
    """TC3: 成交額 — 直接存原始元，不做 ÷ 10,000,000"""

    def test_amount_raw_value(self, fetcher, raw_2330_3days):
        rows = fetcher._transform(raw_2330_3days)
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["amount"] == 18750000000, (
            f"amount 應為 18750000000（原始元），實際 {row['amount']}"
        )


class TestTC4FieldMapping:
    """TC4: 欄位名映射 — FinMind 的 max→high, min→low"""

    def test_max_maps_to_high(self, fetcher, raw_2330_3days):
        rows = fetcher._transform(raw_2330_3days)
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["high"] == 595.0, f"high 應為 595.0，實際 {row['high']}"

    def test_min_maps_to_low(self, fetcher, raw_2330_3days):
        rows = fetcher._transform(raw_2330_3days)
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["low"] == 590.0, f"low 應為 590.0，實際 {row['low']}"


class TestTC5Dedup:
    """TC5: 去重 — 同 (stock_id, date) 寫兩次，只保留 1 筆，值為最後一次"""

    def test_reinsert_same_key_keeps_single_row(self, fetcher, db):
        # 第一次寫入（3 筆）
        fetcher.fetch_and_save("2330", "2024-01-02", "2024-01-04")

        # 第二次：同一天但 close 改成 600
        modified_data = {
            "msg": "success",
            "status": 200,
            "data": [
                {
                    "date": "2024-01-02",
                    "stock_id": "2330",
                    "Trading_Volume": 31530000,
                    "Trading_money": 18750000000,
                    "open": 593.0,
                    "max": 595.0,
                    "min": 590.0,
                    "close": 600.0,
                    "spread": 2.0,
                    "Trading_turnover": 28456,
                }
            ],
        }
        rows = fetcher._transform(modified_data)
        fetcher.save(rows)

        cur = db.execute(
            "SELECT COUNT(*) FROM stock_history "
            "WHERE stock_id='2330' AND date='2024-01-02'"
        )
        count = cur.fetchone()[0]
        assert count == 1, f"預期 1 筆，實際 {count} 筆"

        cur = db.execute(
            "SELECT close FROM stock_history "
            "WHERE stock_id='2330' AND date='2024-01-02'"
        )
        close_val = cur.fetchone()[0]
        assert close_val == 600.0, f"預期 close=600.0，實際 {close_val}"


class TestTC7EmptyResponse:
    """TC7: 空回應必須拋 Exception，訊息含 'empty' 或 '空'"""

    def test_empty_data_list_raises(self, fetcher):
        empty_response = {"msg": "success", "status": 200, "data": []}
        with pytest.raises(Exception) as exc_info:
            fetcher._transform(empty_response)
        error_msg = str(exc_info.value).lower()
        assert "empty" in error_msg or "空" in error_msg, (
            f"Exception 訊息應包含 'empty' 或 '空'，實際：{exc_info.value}"
        )


class TestTC8MissingField:
    """TC8: 缺欄位必須拋 Exception，訊息含缺失的欄位名"""

    def test_missing_Trading_Volume_raises(self, fetcher):
        broken_response = {
            "msg": "success",
            "status": 200,
            "data": [
                {
                    "date": "2024-01-02",
                    "stock_id": "2330",
                    "Trading_money": 18750000000,
                    "open": 593.0,
                    "max": 595.0,
                    "min": 590.0,
                    "close": 594.0,
                    "spread": 2.0,
                    "Trading_turnover": 28456,
                }
            ],
        }
        with pytest.raises(Exception) as exc_info:
            fetcher._transform(broken_response)
        error_msg = str(exc_info.value)
        assert "Trading_Volume" in error_msg, (
            f"Exception 訊息應包含 'Trading_Volume'，實際：{error_msg}"
        )


class TestTC9SourceField:
    """TC9: source 欄位必須是 'finmind'"""

    def test_source_is_finmind(self, fetcher, raw_2330_3days):
        rows = fetcher._transform(raw_2330_3days)
        for r in rows:
            assert r["source"] == "finmind", (
                f"source 應為 'finmind'，實際 {r['source']}"
            )


class TestTC10Integration:
    """TC10: fetch_and_save 完整串接測試"""

    def test_fetch_and_save_writes_to_db(self, fetcher, db):
        """fetch_and_save 後 DB 應有 3 筆資料"""
        fetcher.fetch_and_save("2330", "2024-01-02", "2024-01-04")
        cur = db.execute(
            "SELECT COUNT(*) FROM stock_history WHERE stock_id='2330'"
        )
        count = cur.fetchone()[0]
        assert count == 3, f"預期 3 筆，實際 {count} 筆"

    def test_fetch_and_save_column_values(self, fetcher, db):
        """fetch_and_save 後檢查每一欄的值是否正確"""
        fetcher.fetch_and_save("2330", "2024-01-02", "2024-01-04")
        cur = db.execute(
            "SELECT date, open, high, low, close, volume, amount, "
            "source FROM stock_history "
            "WHERE stock_id='2330' AND date='2024-01-02'"
        )
        row = cur.fetchone()
        assert row is not None, "查不到 (2330, 2024-01-02)"
        assert row[0] == "2024-01-02", f"date 錯：{row[0]}"
        assert row[1] == 593.0, f"open 錯：{row[1]}"
        assert row[2] == 595.0, f"high 錯：{row[2]}"
        assert row[3] == 590.0, f"low 錯：{row[3]}"
        assert row[4] == 594.0, f"close 錯：{row[4]}"
        assert row[5] == 31530000, f"volume 錯：{row[5]}（應為原始股數）"
        assert row[6] == 18750000000, f"amount 錯：{row[6]}（應為原始元）"
        assert row[7] == "finmind", f"source 錯：{row[7]}"
