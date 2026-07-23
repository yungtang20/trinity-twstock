"""Tests for guarded SQLite health and maintenance services."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from twstock import db_maintenance


def _scalar(value):
    result = MagicMock()
    result.fetchone.return_value = (value,)
    return result


def test_build_database_health_report_is_read_only(tmp_path: Path):
    database_path = tmp_path / "market.db"
    database_path.write_bytes(b"x" * 8192)
    connection = MagicMock()
    connection.execute.side_effect = [
        _scalar(4096),
        _scalar(100),
        _scalar(2),
        _scalar("ok"),
    ]

    with (
        patch("twstock.db_maintenance.get_path", return_value=str(database_path)),
        patch("twstock.db_maintenance.get_connection", return_value=connection) as get_conn,
        patch(
            "twstock.db_maintenance.collect_quality_report",
            return_value={"invalid_history": 0},
        ),
    ):
        report = db_maintenance.build_database_health_report()

    get_conn.assert_called_once_with(readonly=True)
    connection.close.assert_called_once()
    assert report.quick_check == "ok"
    assert report.reclaimable_bytes == 8192
    assert report.is_healthy is True
    assert report.vacuum_recommended is False


def test_run_database_optimize_uses_write_connection():
    connection = MagicMock()
    with patch("twstock.db_maintenance.get_connection", return_value=connection):
        db_maintenance.run_database_optimize()
    connection.execute.assert_called_once_with("PRAGMA optimize")
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


def test_guarded_vacuum_refuses_when_not_recommended(tmp_path: Path):
    report = db_maintenance.DatabaseHealthReport(
        database_path=tmp_path / "market.db",
        file_size_bytes=1024,
        wal_size_bytes=0,
        page_size=4096,
        page_count=100,
        freelist_count=1,
        reclaimable_bytes=4096,
        reclaimable_ratio=0.01,
        quick_check="ok",
        quality_counts={},
    )
    with pytest.raises(ValueError, match="不需要執行 VACUUM"):
        db_maintenance.run_guarded_database_vacuum(report)
