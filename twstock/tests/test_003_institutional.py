"""
Test Cases for Issue 003: Institutional Data Fetcher
Unit Test (mock HTTP) — DoD 必跑

執行（DoD）：  python -m pytest tests/test_003_institutional.py -v -m "not live"
執行（live）： python -m pytest tests/test_003_institutional.py -v -m live
"""

import sqlite3

import pytest

from twstock.fetcher import InstitutionalFetcher


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE institutional_data (
            stock_id          TEXT NOT NULL,
            date              TEXT NOT NULL,
            foreign_net       INTEGER DEFAULT 0,
            trust_net         INTEGER DEFAULT 0,
            dealer_net        INTEGER DEFAULT 0,
            institutional_net INTEGER DEFAULT 0,
            source            TEXT,
            updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
            foreign_buy       INTEGER DEFAULT 0,
            foreign_sell      INTEGER DEFAULT 0,
            trust_buy         INTEGER DEFAULT 0,
            trust_sell        INTEGER DEFAULT 0,
            dealer_buy        INTEGER DEFAULT 0,
            dealer_sell       INTEGER DEFAULT 0,
            PRIMARY KEY (stock_id, date)
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def raw_institutional_2days():
    """
    FinMind TaiwanStockInstitutionalInvestors 回應（2330，兩日）。
    每日有 4 筆（外資、投信、自營商自行、自營商避險）。
    日期 2024-01-02：
      外資: buy=15000000, sell=8000000, net=7000000
      投信: buy=2000000,  sell=1000000, net=1000000
      自營商(自行): buy=3000000, sell=2500000, net=500000
      自營商(避險): buy=500000,  sell=300000,  net=200000
      → dealer_buy=3500000, dealer_sell=2800000, dealer_net=700000
      → institutional_net=7000000+1000000+700000=8700000
    """
    return {
        "msg": "success",
        "status": 200,
        "data": [
            {
                "date": "2024-01-02",
                "stock_id": "2330",
                "name": "外資及陸資(不含外資自營商)",
                "buy": 15000000,
                "sell": 8000000,
                "net": 7000000,
            },
            {
                "date": "2024-01-02",
                "stock_id": "2330",
                "name": "投信",
                "buy": 2000000,
                "sell": 1000000,
                "net": 1000000,
            },
            {
                "date": "2024-01-02",
                "stock_id": "2330",
                "name": "自營商(自行買賣)",
                "buy": 3000000,
                "sell": 2500000,
                "net": 500000,
            },
            {
                "date": "2024-01-02",
                "stock_id": "2330",
                "name": "自營商(避險)",
                "buy": 500000,
                "sell": 300000,
                "net": 200000,
            },
            {
                "date": "2024-01-03",
                "stock_id": "2330",
                "name": "外資及陸資(不含外資自營商)",
                "buy": 12000000,
                "sell": 9000000,
                "net": 3000000,
            },
            {
                "date": "2024-01-03",
                "stock_id": "2330",
                "name": "投信",
                "buy": 1500000,
                "sell": 800000,
                "net": 700000,
            },
            {
                "date": "2024-01-03",
                "stock_id": "2330",
                "name": "自營商(自行買賣)",
                "buy": 2000000,
                "sell": 1800000,
                "net": 200000,
            },
            {
                "date": "2024-01-03",
                "stock_id": "2330",
                "name": "自營商(避險)",
                "buy": 300000,
                "sell": 200000,
                "net": 100000,
            },
        ],
    }


@pytest.fixture
def fetcher(db, monkeypatch, raw_institutional_2days):
    f = InstitutionalFetcher(api_token="fake-token", db=db)
    monkeypatch.setattr(f, "fetch_daily", lambda *a, **k: raw_institutional_2days)
    return f


class TestTC1Pivot:
    """TC1: 多筆 pivot 成每日一筆"""

    def test_output_row_count(self, fetcher, raw_institutional_2days):
        """2 日資料 → 2 列輸出（每日 pivot 成一筆）"""
        rows = fetcher._transform(raw_institutional_2days)
        assert len(rows) == 2, f"預期 2 列，實際 {len(rows)}"

    def test_required_columns_exist(self, fetcher, raw_institutional_2days):
        rows = fetcher._transform(raw_institutional_2days)
        required = {
            "stock_id",
            "date",
            "foreign_buy",
            "foreign_sell",
            "foreign_net",
            "trust_buy",
            "trust_sell",
            "trust_net",
            "dealer_buy",
            "dealer_sell",
            "dealer_net",
            "institutional_net",
            "source",
        }
        assert required.issubset(set(rows[0].keys())), f"缺少欄位: {required - set(rows[0].keys())}"


class TestTC2ForeignBuy:
    """TC2: 外資買進正確"""

    def test_foreign_buy(self, fetcher, raw_institutional_2days):
        rows = fetcher._transform(raw_institutional_2days)
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert (
            row["foreign_buy"] == 15000000
        ), f"foreign_buy 應為 15000000，實際 {row['foreign_buy']}"


class TestTC3DealerBuy:
    """TC3: 自營商買進 = 自行買賣 + 避險累加"""

    def test_dealer_buy_is_sum(self, fetcher, raw_institutional_2days):
        """3000000 + 500000 = 3500000"""
        rows = fetcher._transform(raw_institutional_2days)
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert (
            row["dealer_buy"] == 3500000
        ), f"dealer_buy 應為 3500000（3000000+500000），實際 {row['dealer_buy']}"


class TestTC4DealerNet:
    """TC4: 自營商淨額 = 自行買賣 + 避險淨額累加"""

    def test_dealer_net_is_sum(self, fetcher, raw_institutional_2days):
        """500000 + 200000 = 700000"""
        rows = fetcher._transform(raw_institutional_2days)
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert (
            row["dealer_net"] == 700000
        ), f"dealer_net 應為 700000（500000+200000），實際 {row['dealer_net']}"


class TestTC5InstitutionalNet:
    """TC5: 三大法人合計 = foreign + trust + dealer net"""

    def test_institutional_net(self, fetcher, raw_institutional_2days):
        """7000000 + 1000000 + 700000 = 8700000"""
        rows = fetcher._transform(raw_institutional_2days)
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert (
            row["institutional_net"] == 8700000
        ), f"institutional_net 應為 8700000，實際 {row['institutional_net']}"


class TestTC6Dedup:
    """TC6: 同 stock+date 寫兩次只保留 1 筆"""

    def test_reinsert_keeps_single_row(self, fetcher, db):
        fetcher.fetch_and_save("2330", "2024-01-02", "2024-01-03")
        fetcher.fetch_and_save("2330", "2024-01-02", "2024-01-03")
        cur = db.execute(
            "SELECT COUNT(*) FROM institutional_data WHERE stock_id='2330' AND date='2024-01-02'"
        )
        assert cur.fetchone()[0] == 1


class TestTC7Source:
    """TC7: source == 'finmind'"""

    def test_source_is_finmind(self, fetcher, raw_institutional_2days):
        rows = fetcher._transform(raw_institutional_2days)
        for r in rows:
            assert r["source"] == "finmind", f"source 應為 'finmind'，實際 {r['source']}"


class TestTC8EmptyData:
    """TC8: empty data 拋 Exception"""

    def test_empty_data_raises(self, fetcher):
        empty = {"msg": "success", "status": 200, "data": []}
        with pytest.raises(Exception) as exc_info:
            fetcher._transform(empty)
        msg = str(exc_info.value).lower()
        assert "empty" in msg or "空" in msg, f"Exception 應含 empty/空，實際：{exc_info.value}"


class TestTC9MissingField:
    """TC9: 缺 name 欄位拋 Exception"""

    def test_missing_name_raises(self, fetcher):
        broken = {
            "msg": "success",
            "status": 200,
            "data": [
                {
                    "date": "2024-01-02",
                    "stock_id": "2330",
                    "buy": 15000000,
                    "sell": 8000000,
                    "net": 7000000,
                }
            ],
        }
        with pytest.raises(Exception) as exc_info:
            fetcher._transform(broken)
        assert "name" in str(exc_info.value), f"Exception 應含 'name'，實際：{exc_info.value}"


class TestTC10Integration:
    """TC10: fetch_and_save 串接"""

    def test_writes_to_db(self, fetcher, db):
        fetcher.fetch_and_save("2330", "2024-01-02", "2024-01-03")
        cur = db.execute("SELECT COUNT(*) FROM institutional_data WHERE stock_id='2330'")
        assert cur.fetchone()[0] == 2, "預期 2 筆"

    def test_column_values(self, fetcher, db):
        fetcher.fetch_and_save("2330", "2024-01-02", "2024-01-03")
        cur = db.execute(
            "SELECT foreign_buy, dealer_buy, institutional_net, source "
            "FROM institutional_data WHERE stock_id='2330' AND date='2024-01-02'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 15000000, f"foreign_buy 錯：{row[0]}"
        assert row[1] == 3500000, f"dealer_buy 錯：{row[1]}"
        assert row[2] == 8700000, f"institutional_net 錯：{row[2]}"
        assert row[3] == "finmind", f"source 錯：{row[3]}"
