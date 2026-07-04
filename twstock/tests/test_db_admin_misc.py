# -*- coding: utf-8 -*-
"""test_db_admin_misc.py — db_admin migrate_db / show_tables 測試。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestMigrateDb:
    @patch("twstock.db_admin.get_connection")
    def test_migrate_commits(self, mock_conn):
        mock_db = MagicMock()
        mock_conn.return_value = mock_db
        from twstock.db_admin import migrate_db

        migrate_db()
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()


class TestShowTables:
    @patch("twstock.db_admin.get_connection")
    def test_show_tables(self, mock_conn, capsys):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"name": "stock_meta"},
            {"name": "klines_indicators"},
        ]
        mock_db.cursor.return_value = mock_cursor
        mock_conn.return_value = mock_db
        from twstock.db_admin import show_tables

        show_tables()
        out = capsys.readouterr().out
        assert "stock_meta" in out
        mock_db.close.assert_called_once()
