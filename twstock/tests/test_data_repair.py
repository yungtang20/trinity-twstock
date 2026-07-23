import sqlite3

from twstock.commands.data_repair import collect_quality_report, repair_database


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE stock_history (
            stock_id TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL
        );
        CREATE TABLE stock_indicators (stock_id TEXT, date TEXT);
        CREATE TABLE shareholding_unified (
            stock_id TEXT, date TEXT, source TEXT,
            total_shares INTEGER, whale_ratio REAL, retail_ratio REAL,
            foreign_shares INTEGER, foreign_ratio REAL, total_people INTEGER,
            whale_shares INTEGER, whale_people INTEGER
        );
        CREATE TABLE institutional_data (
            stock_id TEXT, date TEXT, foreign_net INTEGER, trust_net INTEGER,
            dealer_net INTEGER, institutional_net INTEGER, foreign_buy INTEGER,
            foreign_sell INTEGER, trust_buy INTEGER, trust_sell INTEGER,
            dealer_buy INTEGER, dealer_sell INTEGER
        );
        CREATE TABLE audit_log (action TEXT, status TEXT, detail TEXT);
        """
    )
    conn.executemany(
        "INSERT INTO stock_history VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("2330", "2026-07-20", 100, 105, 99, 101),
            ("9999", "2026-07-20", 100, 0, 99, 101),
        ],
    )
    conn.executemany(
        "INSERT INTO stock_indicators VALUES (?, ?)",
        [("2330", "2026-07-20"), ("9999", "2026-07-20"), ("orphan", "2026-07-20")],
    )
    conn.execute(
        "INSERT INTO shareholding_unified (stock_id, date, source) VALUES ('2330', '2026-07-18', 'twse_foreign')"
    )
    conn.execute("INSERT INTO shareholding_unified (stock_id, date, source) VALUES ('2330', '2099-12-31', 'tdcc')")
    conn.execute("INSERT INTO institutional_data (stock_id, date) VALUES ('6488', '2026-07-20')")
    conn.commit()
    conn.close()


def test_data_repair_dry_run_and_apply(tmp_path):
    path = tmp_path / "repair.db"
    _make_db(path)
    conn = sqlite3.connect(path)
    report = collect_quality_report(conn, today="2026-07-22")
    conn.close()

    assert report == {
        "invalid_history": 1,
        "orphan_indicators": 1,
        "blank_foreign_shareholding": 1,
        "future_shareholding": 1,
        "tdcc_incomplete_rows": 1,
        "tdcc_missing_whale_people": 1,
        "tdcc_tiny_periods": 1,
        "tdcc_weekend_periods": 0,
        "tdcc_large_gaps": 0,
        "blank_institutional": 1,
        "common_institutional_missing": 0,
        "common_active_institutional_missing": 0,
        "history_on_calendar_closed_days": 0,
        "history_missing_calendar_dates": 0,
    }
    assert repair_database(path, today="2026-07-22") == report

    assert repair_database(path, apply=True, today="2026-07-22") == report
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM stock_history").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM stock_indicators").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM shareholding_unified").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM institutional_data").fetchone()[0] == 0
    assert conn.execute("SELECT status FROM audit_log").fetchone()[0] == "success"
    conn.close()
