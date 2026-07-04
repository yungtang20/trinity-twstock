# -*- coding: utf-8 -*-
# [AI MOD]
"""
ETL data processing and high-performance database writing engine.
Uses INSERT ... ON CONFLICT DO UPDATE to preserve existing column values
when a new write doesn't provide them (prevents NULL/empty overwrite bugs).
"""

import logging
import sqlite3

import pandas as pd

from twstock.db import get_connection

logger = logging.getLogger(__name__)


class DataProcessor:
    """Unified database writing engine."""

    def __init__(self):
        pass

    # ================== Core Batch Upsert Engine (kept for reference) ==================
    @staticmethod
    def _batch_upsert(table_name: str, df: pd.DataFrame, conn: sqlite3.Connection):
        """
        Legacy: INSERT OR REPLACE — deletes the whole row then inserts.
        Can clobber columns not present in the incoming df. Not used by any
        upsert_* method anymore; retained only as a utility for callers that
        genuinely want full-row replacement.
        """
        if df.empty:
            return 0

        cols = list(df.columns)
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        sql = f"INSERT OR REPLACE INTO {table_name} ({col_names}) VALUES ({placeholders})"

        records = df.where(df.notna(), None).values.tolist()

        cursor = conn.cursor()
        cursor.executemany(sql, records)
        conn.commit()

        count = cursor.rowcount
        logger.debug(f"[upsert] {table_name}: {count} rows affected")
        return count

    # ================== Public Upsert Methods ==================
    def upsert_history(self, df: pd.DataFrame) -> int:
        """Upserts daily K-line prices into stock_history."""
        if df is None or df.empty:
            return 0
        df_write = df.copy()
        if "source" not in df_write.columns:
            df_write["source"] = "official"
        expected = [
            "stock_id",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "trade_count",
            "spread",
            "source",
        ]
        cols = [c for c in expected if c in df_write.columns]
        df_write = df_write[cols].copy()
        if "date" in df_write.columns:
            df_write["date"] = pd.to_datetime(df_write["date"]).dt.strftime("%Y-%m-%d")
        df_write = df_write.dropna(subset=["close"])

        records = df_write.where(df_write.notna(), None).values.tolist()

        # Build dynamic SQL based on actual columns present
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)

        # Build SET clause for non-PK columns
        set_clauses = []
        for col in cols:
            if col in ("stock_id", "date"):
                continue
            set_clauses.append(
                f"{col} = CASE WHEN excluded.{col} IS NOT NULL THEN excluded.{col} ELSE stock_history.{col} END"
            )
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        sql = f"""
        INSERT INTO stock_history ({col_names})
        VALUES ({placeholders})
        ON CONFLICT(stock_id, date) DO UPDATE SET
            {", ".join(set_clauses)}
        """

        conn = get_connection()
        try:
            conn.executemany(sql, records)
            conn.commit()
            return len(records)
        finally:
            conn.close()

    def upsert_institutional(self, df: pd.DataFrame) -> int:
        """Upserts institutional flow data into institutional_data."""
        if df is None or df.empty:
            return 0
        df_write = df.copy()
        if "source" not in df_write.columns:
            df_write["source"] = "official"
        expected = [
            "stock_id",
            "date",
            "foreign_net",
            "trust_net",
            "dealer_net",
            "institutional_net",
            "foreign_buy",
            "foreign_sell",
            "trust_buy",
            "trust_sell",
            "dealer_buy",
            "dealer_sell",
            "source",
        ]
        cols = [c for c in expected if c in df_write.columns]
        df_write = df_write[cols].copy()
        if "date" in df_write.columns:
            df_write["date"] = pd.to_datetime(df_write["date"]).dt.strftime("%Y-%m-%d")

        records = df_write.where(df_write.notna(), None).values.tolist()

        # 動態建立 SQL，只包含實際存在的欄位（避免 binding 數量不符）
        all_expected = [
            "stock_id",
            "date",
            "foreign_net",
            "trust_net",
            "dealer_net",
            "institutional_net",
            "foreign_buy",
            "foreign_sell",
            "trust_buy",
            "trust_sell",
            "dealer_buy",
            "dealer_sell",
            "source",
        ]
        insert_cols = [c for c in all_expected if c in cols]
        placeholders = ",".join(["?"] * len(insert_cols))
        col_sql = ",".join(insert_cols)
        updates = ", ".join(
            f"{c} = excluded.{c}" for c in insert_cols if c not in ("stock_id", "date")
        )
        sql = f"""
        INSERT INTO institutional_data ({col_sql})
        VALUES ({placeholders})
        ON CONFLICT(stock_id, date) DO UPDATE SET
            {updates},
            updated_at = CURRENT_TIMESTAMP
        """

        conn = get_connection()
        try:
            conn.executemany(sql, records)
            conn.commit()
            return len(records)
        finally:
            conn.close()

    def _upsert_shareholding_unified(
        self, df: pd.DataFrame, extra_cols_sql: str, extra_cols_values: str
    ):
        """
        Internal helper for upsert_tdcc / upsert_shareholding / upsert_shareholding_unified.
        All three write to shareholding_unified with the same ON CONFLICT logic.
        extra_cols_sql: additional column names for INSERT column list
        extra_cols_values: additional ? placeholders for VALUES
        """
        if df.empty:
            return
        df_write = df.copy()
        if "date" in df_write.columns:
            df_write["date"] = pd.to_datetime(df_write["date"]).dt.strftime("%Y-%m-%d")

        # Build the full column list
        base_cols = ["stock_id", "date", "source"]
        extra_cols_list = [c.strip() for c in extra_cols_sql.split(",") if c.strip()]
        all_cols = base_cols + extra_cols_list

        # Filter to only columns present in df
        cols = [c for c in all_cols if c in df_write.columns]
        df_write = df_write[cols].copy()

        records = df_write.where(df_write.notna(), None).values.tolist()

        # Build dynamic SQL based on actual columns present
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)

        # Build SET clause — protect NULLs with CASE WHEN
        set_clauses = []
        for col in cols:
            if col in ("stock_id", "date", "source"):
                continue  # skip PK columns
            set_clauses.append(
                f"{col} = CASE WHEN excluded.{col} IS NOT NULL THEN excluded.{col} ELSE shareholding_unified.{col} END"
            )
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        sql = f"""
        INSERT INTO shareholding_unified ({col_names})
        VALUES ({placeholders})
        ON CONFLICT(stock_id, date, source) DO UPDATE SET
            {", ".join(set_clauses)}
        """

        conn = get_connection()
        try:
            conn.executemany(sql, records)
            conn.commit()
        finally:
            conn.close()

    def upsert_tdcc(self, df: pd.DataFrame):
        """Write TDCC shareholding data to shareholding_unified."""
        if df.empty:
            return
        df_write = df.copy()
        if "source" not in df_write.columns:
            df_write["source"] = "tdcc"
        expected = [
            "stock_id",
            "date",
            "source",
            "total_shares",
            "whale_ratio",
            "retail_ratio",
            "total_people",
            "whale_shares",
            "whale_people",
        ]
        cols = [c for c in expected if c in df_write.columns]
        df_write = df_write[cols].copy()
        self._upsert_shareholding_unified(
            df_write,
            "total_shares, whale_ratio, retail_ratio, total_people, whale_shares, whale_people",
            "",
        )

    def upsert_shareholding(self, df: pd.DataFrame):
        """Upserts foreign shareholding into shareholding_unified."""
        if df.empty:
            return
        expected = ["stock_id", "date", "foreign_shares", "foreign_ratio", "source"]
        cols = [c for c in expected if c in df.columns]
        df_write = df[cols].copy()
        df_write["source"] = "twse_foreign"
        self._upsert_shareholding_unified(df_write, "foreign_shares, foreign_ratio", "")

    def upsert_shareholding_unified(self, df: pd.DataFrame):
        """Upserts weekly concentrations and foreign details into shareholding_unified."""
        if df.empty:
            return
        expected = [
            "stock_id",
            "date",
            "source",
            "total_shares",
            "whale_ratio",
            "retail_ratio",
            "foreign_shares",
            "foreign_ratio",
            "total_people",
            "whale_shares",
            "whale_people",
        ]
        cols = [c for c in expected if c in df.columns]
        df_write = df[cols].copy()
        self._upsert_shareholding_unified(
            df_write,
            "total_shares, whale_ratio, retail_ratio, foreign_shares, foreign_ratio, total_people, whale_shares, whale_people",
            "",
        )

    def upsert_dividend_events(self, df: pd.DataFrame):
        """Upserts dividend events into dividend_events."""
        if df.empty:
            return
        expected = [
            "stock_id",
            "date",
            "before_price",
            "after_price",
            "reference_price",
            "cash_dividend",
            "stock_dividend",
            "source",
        ]
        cols = [c for c in expected if c in df.columns]
        df_write = df[cols].copy()
        if "date" in df_write.columns:
            df_write["date"] = pd.to_datetime(df_write["date"]).dt.strftime("%Y-%m-%d")

        records = df_write.where(df_write.notna(), None).values.tolist()

        sql = """
        INSERT INTO dividend_events
            (stock_id, date, before_price, after_price, reference_price,
             cash_dividend, stock_dividend, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(stock_id, date) DO UPDATE SET
            before_price    = CASE WHEN excluded.before_price    IS NOT NULL THEN excluded.before_price    ELSE dividend_events.before_price END,
            after_price     = CASE WHEN excluded.after_price     IS NOT NULL THEN excluded.after_price     ELSE dividend_events.after_price END,
            reference_price = CASE WHEN excluded.reference_price IS NOT NULL THEN excluded.reference_price ELSE dividend_events.reference_price END,
            cash_dividend   = excluded.cash_dividend,
            stock_dividend  = excluded.stock_dividend,
            source          = excluded.source,
            updated_at      = CURRENT_TIMESTAMP
        """

        conn = get_connection()
        try:
            conn.executemany(sql, records)
            conn.commit()
        finally:
            conn.close()

    def upsert_per_data(self, df: pd.DataFrame):
        """Upserts PE/PBR valuation data into per_data."""
        if df.empty:
            return
        df_write = df.copy()
        # Dynamic mapping for aliases
        if "per" in df_write.columns:
            df_write["pe_ratio"] = df_write["per"]
        elif "pe_ratio" in df_write.columns:
            df_write["per"] = df_write["pe_ratio"]

        if "pbr" in df_write.columns:
            df_write["pb_ratio"] = df_write["pbr"]
        elif "pb_ratio" in df_write.columns:
            df_write["pbr"] = df_write["pb_ratio"]

        expected = [
            "stock_id",
            "date",
            "per",
            "pbr",
            "pe_ratio",
            "pb_ratio",
            "dividend_yield",
            "source",
        ]
        cols = [c for c in expected if c in df_write.columns]
        df_write = df_write[cols].copy()
        if "date" in df_write.columns:
            df_write["date"] = pd.to_datetime(df_write["date"]).dt.strftime("%Y-%m-%d")

        records = df_write.where(df_write.notna(), None).values.tolist()

        sql = """
        INSERT INTO per_data
            (stock_id, date, per, pbr, pe_ratio, pb_ratio, dividend_yield, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(stock_id, date) DO UPDATE SET
            per            = CASE WHEN excluded.per            IS NOT NULL THEN excluded.per            ELSE per_data.per END,
            pbr            = CASE WHEN excluded.pbr            IS NOT NULL THEN excluded.pbr            ELSE per_data.pbr END,
            pe_ratio       = CASE WHEN excluded.pe_ratio       IS NOT NULL THEN excluded.pe_ratio       ELSE per_data.pe_ratio END,
            pb_ratio       = CASE WHEN excluded.pb_ratio       IS NOT NULL THEN excluded.pb_ratio       ELSE per_data.pb_ratio END,
            dividend_yield = CASE WHEN excluded.dividend_yield IS NOT NULL THEN excluded.dividend_yield ELSE per_data.dividend_yield END,
            source         = excluded.source,
            updated_at     = CURRENT_TIMESTAMP
        """

        conn = get_connection()
        try:
            conn.executemany(sql, records)
            conn.commit()
        finally:
            conn.close()

    def upsert_meta(self, df: pd.DataFrame):
        """Upserts stock metadata into stock_meta.
        Critical: market/type/stock_name must NOT be overwritten by empty strings.
        """
        if df.empty:
            return
        expected = ["stock_id", "stock_name", "industry_category", "market", "type", "source"]
        cols = [c for c in expected if c in df.columns]
        df_write = df[cols].copy()

        records = df_write.where(df_write.notna(), None).values.tolist()

        sql = """
        INSERT INTO stock_meta
            (stock_id, stock_name, industry_category, market, type, source)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(stock_id) DO UPDATE SET
            stock_name        = CASE WHEN excluded.stock_name        IS NOT NULL AND excluded.stock_name        != '' THEN excluded.stock_name        ELSE stock_meta.stock_name END,
            industry_category = CASE WHEN excluded.industry_category IS NOT NULL AND excluded.industry_category != '' THEN excluded.industry_category ELSE stock_meta.industry_category END,
            market            = CASE WHEN excluded.market            IS NOT NULL AND excluded.market            != '' THEN excluded.market            ELSE stock_meta.market END,
            type              = CASE WHEN excluded.type              IS NOT NULL AND excluded.type              != '' THEN excluded.type              ELSE stock_meta.type END,
            source            = excluded.source,
            updated_at        = CURRENT_TIMESTAMP
        """

        conn = get_connection()
        try:
            conn.executemany(sql, records)
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    print("processor.py loaded successfully. Run main.py to execute.")
