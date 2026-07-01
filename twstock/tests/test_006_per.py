"""
Test Cases for Issue 006: PER Data Fetcher
Unit Test (mock HTTP) — DoD 必跑

執行（DoD）：  python -m pytest tests/test_006_per.py -v -m "not live"
執行（live）： python -m pytest tests/test_006_per.py -v -m live
"""
import sqlite3
import pytest
from fetcher import PERFetcher


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE per_data (
            stock_id       TEXT NOT NULL,
            date           TEXT NOT NULL,
            per            REAL,
            pbr            REAL,
            pe_ratio       REAL,
            pb_ratio       REAL,
            dividend_yield REAL,
            source         TEXT,
            updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (stock_id, date)
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def raw_per_2330():
    """
    TWSE BWIBBU API 回應（2330，三日）。
    日期 ROC 格式，本益比/淨值比為字串。
    """
    return {
        "stat": "OK",
        "fields": ["日期", "殖利率(%)", "股利年度", "本益比", "股價淨值比", "財報年/季"],
        "data": [
            ["113/01/02", "1.22", "112", "15.50", "3.20", "112/3"],
            ["113/01/03", "1.21", "112", "15.70", "3.22", "112/3"],
            ["113/01/04", "1.20", "112", "15.90", "3.25", "112/3"],
        ]
    }


@pytest.fixture
def fetcher(db, monkeypatch, raw_per_2330):
    f = PERFetcher(db=db)
    monkeypatch.setattr(f, "fetch_monthly", lambda *a, **k: raw_per_2330)
    return f


class TestTC1Transform:
    """TC1: 基本正確性"""

    def test_row_count(self, fetcher, raw_per_2330):
        rows = fetcher._transform(raw_per_2330, "2330")
        assert len(rows) == 3, f"預期 3 列，實際 {len(rows)}"

    def test_required_columns_exist(self, fetcher, raw_per_2330):
        rows = fetcher._transform(raw_per_2330, "2330")
        required = {
            "stock_id", "date",
            "dividend_yield", "per", "pe_ratio", "pbr", "pb_ratio", "source",
        }
        assert required.issubset(set(rows[0].keys())), (
            f"缺少欄位: {required - set(rows[0].keys())}"
        )


class TestTC2DateConversion:
    """TC2: ROC 日期轉換"""

    def test_roc_date_to_ce(self, fetcher, raw_per_2330):
        rows = fetcher._transform(raw_per_2330, "2330")
        assert rows[0]["date"] == "2024-01-02", (
            f"date 應為 2024-01-02，實際 {rows[0]['date']}"
        )


class TestTC3DividendYield:
    """TC3: dividend_yield 正確"""

    def test_dividend_yield(self, fetcher, raw_per_2330):
        rows = fetcher._transform(raw_per_2330, "2330")
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["dividend_yield"] == 1.22, (
            f"dividend_yield 應為 1.22，實際 {row['dividend_yield']}"
        )


class TestTC4PER:
    """TC4: per == pe_ratio 且值正確"""

    def test_per_value(self, fetcher, raw_per_2330):
        rows = fetcher._transform(raw_per_2330, "2330")
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["per"] == 15.50, f"per 應為 15.50，實際 {row['per']}"

    def test_per_equals_pe_ratio(self, fetcher, raw_per_2330):
        rows = fetcher._transform(raw_per_2330, "2330")
        for r in rows:
            assert r["per"] == r["pe_ratio"], (
                f"per({r['per']}) 應等於 pe_ratio({r['pe_ratio']})"
            )


class TestTC5PBR:
    """TC5: pbr == pb_ratio 且值正確"""

    def test_pbr_value(self, fetcher, raw_per_2330):
        rows = fetcher._transform(raw_per_2330, "2330")
        row = next(r for r in rows if r["date"] == "2024-01-02")
        assert row["pbr"] == 3.20, f"pbr 應為 3.20，實際 {row['pbr']}"

    def test_pbr_equals_pb_ratio(self, fetcher, raw_per_2330):
        rows = fetcher._transform(raw_per_2330, "2330")
        for r in rows:
            assert r["pbr"] == r["pb_ratio"], (
                f"pbr({r['pbr']}) 應等於 pb_ratio({r['pb_ratio']})"
            )


class TestTC6Source:
    """TC6: source == 'official'"""

    def test_source_is_official(self, fetcher, raw_per_2330):
        rows = fetcher._transform(raw_per_2330, "2330")
        for r in rows:
            assert r["source"] == "official"


class TestTC7BadStat:
    """TC7: stat != OK 拋 Exception"""

    def test_bad_stat_raises(self, fetcher):
        bad = {"stat": "FAIL", "data": [], "fields": []}
        with pytest.raises(Exception):
            fetcher._transform(bad, "2330")


class TestTC8Integration:
    """TC8: fetch_and_save 串接"""

    def test_writes_to_db(self, fetcher, db):
        fetcher.fetch_and_save("2330", "2024-01-01", "2024-01-31")
        cur = db.execute("SELECT COUNT(*) FROM per_data WHERE stock_id='2330'")
        assert cur.fetchone()[0] == 3

    def test_column_values(self, fetcher, db):
        fetcher.fetch_and_save("2330", "2024-01-01", "2024-01-31")
        cur = db.execute(
            "SELECT date, dividend_yield, per, pe_ratio, pbr, pb_ratio, source "
            "FROM per_data WHERE stock_id='2330' AND date='2024-01-02'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "2024-01-02"
        assert row[1] == 1.22,      f"dividend_yield 錯：{row[1]}"
        assert row[2] == 15.50,     f"per 錯：{row[2]}"
        assert row[3] == 15.50,     f"pe_ratio 錯：{row[3]}"
        assert row[4] == 3.20,      f"pbr 錯：{row[4]}"
        assert row[5] == 3.20,      f"pb_ratio 錯：{row[5]}"
        assert row[6] == "official", f"source 錯：{row[6]}"
