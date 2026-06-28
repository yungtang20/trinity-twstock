"""
Test Cases for Issue 002: TWSE Official Data Fetcher
Unit Test (mock HTTP) — DoD 必跑

執行（DoD）：  python -m pytest tests/test_002_twse_official.py -v -m "not live"
執行（live）： python -m pytest tests/test_002_twse_official.py -v -m live
"""
import sqlite3
import pytest
from fetcher import TWSEFetcher


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
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
            adj_factor  REAL DEFAULT 1.0,
            source      TEXT,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (stock_id, date)
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def raw_twse_2330():
    """
    TWSE STOCK_DAY API 回應（2330，三個交易日 + 一個停牌日）。
    data 是 list of list，日期 ROC 格式，數字含逗號。
    113/01/05 為停牌行（close='--'），_transform 必須跳過。
    """
    return {
        "stat": "OK",
        "date": "11301",
        "title": "113年01月 2330 台積電 各日成交資訊",
        "fields": [
            "日期", "成交股數", "成交金額",
            "開盤價", "最高價", "最低價", "收盤價",
            "漲跌價差", "成交筆數"
        ],
        "data": [
            ["113/01/02", "22,388,968", "13,130,657,808",
             "589.00", "590.00", "586.00", "586.00", "-5.00", "30,718"],
            ["113/01/03", "20,502,111", "12,017,236,456",
             "588.00", "592.00", "586.00", "590.00", "4.00", "25,432"],
            ["113/01/04", "18,934,567", "11,234,567,890",
             "591.00", "594.00", "589.00", "593.00", "3.00", "22,891"],
            ["113/01/05", "--", "--", "--", "--", "--", "--", "--", "--"],
        ]
    }


@pytest.fixture
def fetcher(db, monkeypatch, raw_twse_2330):
    """TWSEFetcher 實例，fetch_monthly 被 mock。"""
    f = TWSEFetcher(db=db)
    monkeypatch.setattr(f, "fetch_monthly", lambda *a, **k: raw_twse_2330)
    return f


class TestTC1Transform:
    """TC1: 基本正確性"""

    def test_row_count(self, fetcher, raw_twse_2330):
        """停牌行不算，只有 3 筆有效資料"""
        rows = fetcher._transform(raw_twse_2330, "2330")
        assert len(rows) == 3, f"預期 3 筆（排除停牌行），實際 {len(rows)}"

    def test_required_columns_exist(self, fetcher, raw_twse_2330):
        rows = fetcher._transform(raw_twse_2330, "2330")
        required = {
            "stock_id", "date", "open", "high", "low", "close",
            "volume", "amount", "trade_count", "spread", "adj_factor", "source",
        }
        assert required.issubset(set(rows[0].keys())), (
            f"缺少欄位: {required - set(rows[0].keys())}"
        )

    def test_no_adj_close_column(self, fetcher, raw_twse_2330):
        rows = fetcher._transform(raw_twse_2330, "2330")
        assert "adj_close" not in rows[0]


class TestTC2DateConversion:
    """TC2: ROC 日期 → CE 日期"""

    def test_roc_date_to_ce(self, fetcher, raw_twse_2330):
        """'113/01/02' → '2024-01-02'"""
        rows = fetcher._transform(raw_twse_2330, "2330")
        row = rows[0]
        assert row["date"] == "2024-01-02", f"date 應為 2024-01-02，實際 {row['date']}"


class TestTC3Volume:
    """TC3: 成交股數去逗號"""

    def test_volume_comma_removal(self, fetcher, raw_twse_2330):
        """'22,388,968' → 22388968（int）"""
        rows = fetcher._transform(raw_twse_2330, "2330")
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["volume"] == 22388968, f"volume 應為 22388968，實際 {row['volume']}"


class TestTC4Amount:
    """TC4: 成交金額去逗號"""

    def test_amount_comma_removal(self, fetcher, raw_twse_2330):
        """'13,130,657,808' → 13130657808（int）"""
        rows = fetcher._transform(raw_twse_2330, "2330")
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["amount"] == 13130657808, f"amount 應為 13130657808，實際 {row['amount']}"


class TestTC5FieldMapping:
    """TC5: 最高/最低欄位映射"""

    def test_high_price(self, fetcher, raw_twse_2330):
        """最高價 '590.00' → high == 590.0"""
        rows = fetcher._transform(raw_twse_2330, "2330")
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["high"] == 590.0, f"high 應為 590.0，實際 {row['high']}"

    def test_low_price(self, fetcher, raw_twse_2330):
        """最低價 '586.00' → low == 586.0"""
        rows = fetcher._transform(raw_twse_2330, "2330")
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["low"] == 586.0, f"low 應為 586.0，實際 {row['low']}"


class TestTC6SuspendedRows:
    """TC6: 停牌行必須跳過"""

    def test_skip_suspended_row(self, fetcher, raw_twse_2330):
        """close=='--' 的行不得出現在結果中"""
        rows = fetcher._transform(raw_twse_2330, "2330")
        dates = [r["date"] for r in rows]
        assert "2024-01-05" not in dates, "停牌行（2024-01-05）不應出現在結果中"


class TestTC7AdjFactor:
    """TC7: adj_factor 預設 1.0"""

    def test_adj_factor_defaults_to_one(self, fetcher, raw_twse_2330):
        rows = fetcher._transform(raw_twse_2330, "2330")
        for r in rows:
            assert r["adj_factor"] == 1.0, f"adj_factor 應為 1.0，實際 {r['adj_factor']}"


class TestTC8BadStat:
    """TC8: stat != OK 拋 Exception"""

    def test_bad_stat_raises(self, fetcher):
        bad = {"stat": "FAIL", "data": [], "fields": []}
        with pytest.raises(Exception) as exc_info:
            fetcher._transform(bad, "2330")
        msg = str(exc_info.value).lower()
        assert "stat" in msg or "ok" in msg, (
            f"Exception 應提及 stat/OK，實際：{exc_info.value}"
        )


class TestTC9Source:
    """TC9: source == 'official'"""

    def test_source_is_official(self, fetcher, raw_twse_2330):
        rows = fetcher._transform(raw_twse_2330, "2330")
        for r in rows:
            assert r["source"] == "official", f"source 應為 'official'，實際 {r['source']}"


class TestTC10Integration:
    """TC10: fetch_and_save 完整串接"""

    def test_fetch_and_save_writes_to_db(self, fetcher, db):
        fetcher.fetch_and_save("2330", "2024-01-01", "2024-01-31")
        cur = db.execute("SELECT COUNT(*) FROM stock_history WHERE stock_id='2330'")
        count = cur.fetchone()[0]
        assert count == 3, f"預期 3 筆（排除停牌行），實際 {count}"

    def test_fetch_and_save_column_values(self, fetcher, db):
        fetcher.fetch_and_save("2330", "2024-01-01", "2024-01-31")
        cur = db.execute(
            "SELECT date, open, high, low, close, volume, amount, adj_factor, source "
            "FROM stock_history WHERE stock_id='2330' AND date='2024-01-02'"
        )
        row = cur.fetchone()
        assert row is not None, "查不到 (2330, 2024-01-02)"
        assert row[0] == "2024-01-02"
        assert row[1] == 589.0,        f"open 錯：{row[1]}"
        assert row[2] == 590.0,        f"high 錯：{row[2]}"
        assert row[3] == 586.0,        f"low 錯：{row[3]}"
        assert row[4] == 586.0,        f"close 錯：{row[4]}"
        assert row[5] == 22388968,     f"volume 錯：{row[5]}"
        assert row[6] == 13130657808,  f"amount 錯：{row[6]}"
        assert row[7] == 1.0,          f"adj_factor 錯：{row[7]}"
        assert row[8] == "official",   f"source 錯：{row[8]}"
