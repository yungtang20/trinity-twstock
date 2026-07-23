#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Technical indicator loading and persistence for TRINITY.

The module keeps the existing public calculator classes, while using indexed
batched reads and ``executemany`` writes for full-market refreshes.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from typing import Any

import numpy as np
import pandas as pd

from twstock.db import get_connection
from twstock.db_admin import create_tables

logger = logging.getLogger(__name__)


def _iter_stock_frames(
    db: sqlite3.Connection,
    *,
    chunk_size: int = 400,
) -> Iterator[tuple[str, pd.DataFrame]]:
    """Yield each stock's ordered history without retaining the whole market.

    A former implementation first assembled a dictionary containing every
    stock's complete history.  That avoided N+1 reads but retained millions of
    rows at once.  This preserves batched, indexed queries and lets each group
    be released as soon as it has been persisted.
    """
    rows = db.execute("SELECT DISTINCT stock_id FROM stock_history ORDER BY stock_id").fetchall()
    stock_ids = [str(row[0]) for row in rows]
    for offset in range(0, len(stock_ids), chunk_size):
        batch = stock_ids[offset : offset + chunk_size]
        if not batch:
            continue
        placeholders = ",".join("?" for _ in batch)
        frame = pd.read_sql_query(
            "SELECT stock_id, date, open, high, low, close, volume, amount "
            f"FROM stock_history WHERE stock_id IN ({placeholders}) "
            "ORDER BY stock_id ASC, date ASC",
            db,
            params=batch,
        )
        for stock_id, group in frame.groupby("stock_id", sort=False):
            yield str(stock_id), group.reset_index(drop=True)


def _sql_number(value: Any) -> float | None:
    """Return a finite nullable float suitable for a SQLite parameter."""
    if value is None or pd.isna(value):
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def _date_text(value: object) -> str:
    """Normalize pandas and SQLite date values to the public YYYY-MM-DD form."""
    return str(value)[:10]


class IndicatorEngine:
    """Build display-oriented technical indicators for one stock."""

    def __init__(
        self, stock_id: str, limit: int = 600, df_intraday: pd.DataFrame | None = None
    ) -> None:
        self.stock_id = stock_id
        self.limit = limit
        self.df = self._load_data()
        if df_intraday is not None and not df_intraday.empty:
            self.df = pd.concat([self.df, df_intraday], ignore_index=True)

    def _load_data(self) -> pd.DataFrame:
        """Load the most recent ``limit`` daily bars in chronological order."""
        columns = ["date", "open", "high", "low", "close", "volume"]
        try:
            limit = max(0, int(self.limit))
        except (TypeError, ValueError):
            logger.warning("Invalid indicator limit for %s: %r", self.stock_id, self.limit)
            return pd.DataFrame(columns=columns)
        if limit == 0:
            return pd.DataFrame(columns=columns)

        # SQLite can use the (stock_id, date) index for the inner DESC query;
        # the outer query restores the chronological order required by rolling
        # calculations.  Ordering ASC before LIMIT returned the oldest rows.
        query = """
            SELECT date, open, high, low, close, volume
            FROM (
                SELECT date, open, high, low, close, volume
                FROM stock_history
                WHERE stock_id = ?
                ORDER BY date DESC
                LIMIT ?
            )
            ORDER BY date ASC
        """
        conn: sqlite3.Connection | None = None
        try:
            conn = get_connection(readonly=True)
            frame = pd.read_sql_query(query, conn, params=(self.stock_id, limit))
        except Exception as exc:  # database may not be initialized in UI startup
            logger.warning("Could not load indicator history for %s: %s", self.stock_id, exc)
            return pd.DataFrame(columns=columns)
        finally:
            if conn is not None:
                conn.close()

        if frame.empty:
            return pd.DataFrame(columns=columns)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        return frame.dropna(subset=["date"]).reset_index(drop=True)

    def _add_moving_averages(self) -> None:
        if self.df.empty:
            return
        close = self.df["close"]
        volume = self.df["volume"]
        for period in (5, 10, 20, 60, 120, 200):
            self.df[f"sma_{period}"] = close.rolling(window=period).mean()
        self.df["ema_12"] = close.ewm(span=12, adjust=False).mean()
        self.df["ema_26"] = close.ewm(span=26, adjust=False).mean()
        self.df["volume_sma_5"] = volume.rolling(window=5).mean()
        self.df["volume_sma_20"] = volume.rolling(window=20).mean()
        self.df["volume_ratio"] = volume / self.df["volume_sma_5"]

    def _add_macd(self) -> None:
        if self.df.empty:
            return
        ema_12 = self.df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = self.df["close"].ewm(span=26, adjust=False).mean()
        self.df["macd_dif"] = ema_12 - ema_26
        self.df["macd_dea"] = self.df["macd_dif"].ewm(span=9, adjust=False).mean()
        self.df["macd_hist"] = self.df["macd_dif"] - self.df["macd_dea"]

    def _add_kdj(self) -> None:
        if self.df.empty:
            return
        low_n = self.df["low"].rolling(window=9).min()
        high_n = self.df["high"].rolling(window=9).max()
        denominator = (high_n - low_n).replace(0, np.nan)
        rsv = ((self.df["close"] - low_n) / denominator * 100).fillna(50)
        self.df["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
        self.df["kdj_d"] = self.df["kdj_k"].ewm(com=2, adjust=False).mean()
        self.df["kdj_j"] = 3 * self.df["kdj_k"] - 2 * self.df["kdj_d"]

    def _add_rsi(self) -> None:
        if self.df.empty:
            return
        delta = self.df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        for period in (6, 14):
            avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            self.df[f"rsi_{period}"] = 100 - (100 / (1 + rs))

    def _add_bollinger_bands(self) -> None:
        if self.df.empty:
            return
        middle = self.df["close"].rolling(window=20).mean()
        std = self.df["close"].rolling(window=20).std()
        upper = middle + 2 * std
        lower = middle - 2 * std
        self.df["bb_middle"] = middle
        self.df["bb_upper"] = upper
        self.df["bb_lower"] = lower
        self.df["bb_bandwidth"] = (upper - lower) / middle.replace(0, np.nan) * 100
        self.df["bb_pct_b"] = (self.df["close"] - lower) / (upper - lower).replace(0, np.nan)

    def _add_log_return(self) -> None:
        if not self.df.empty:
            self.df["log_return"] = np.log(self.df["close"] / self.df["close"].shift(1))

    def _add_pivot(self) -> None:
        if self.df.empty:
            return
        self.df["pivot"] = (self.df["high"] + self.df["low"] + self.df["close"]) / 3
        self.df["pivot_r1"] = 2 * self.df["pivot"] - self.df["low"]
        self.df["pivot_r2"] = self.df["pivot"] + (self.df["high"] - self.df["low"])
        self.df["pivot_s1"] = 2 * self.df["pivot"] - self.df["high"]
        self.df["pivot_s2"] = self.df["pivot"] - (self.df["high"] - self.df["low"])

    def _join_fundamental_chips(self) -> None:
        """Join related data using the current schema and date as the key.

        ``shareholding_unified`` has a source in its primary key, so its values
        are aggregated per date before merging.  This avoids duplicate daily
        bars when TDCC and foreign-holding records coexist.
        """
        if self.df.empty or "date" not in self.df:
            return
        dates = pd.to_datetime(self.df["date"], errors="coerce")
        if dates.isna().all():
            return
        start_date = dates.min().strftime("%Y-%m-%d")
        end_date = dates.max().strftime("%Y-%m-%d")
        queries = (
            """
            SELECT date, foreign_buy, foreign_sell, trust_buy, trust_sell,
                   dealer_buy, dealer_sell, foreign_net, trust_net, dealer_net,
                   institutional_net
            FROM institutional_data
            WHERE stock_id = ? AND date BETWEEN ? AND ?
            """,
            """
            SELECT date, MAX(foreign_shares) AS foreign_shares,
                   MAX(foreign_ratio) AS foreign_ratio
            FROM shareholding_unified
            WHERE stock_id = ? AND date BETWEEN ? AND ?
            GROUP BY date
            """,
        )
        conn: sqlite3.Connection | None = None
        try:
            conn = get_connection(readonly=True)
            self.df["date"] = dates
            for query in queries:
                try:
                    joined = pd.read_sql_query(
                        query,
                        conn,
                        params=(self.stock_id, start_date, end_date),
                    )
                except (sqlite3.DatabaseError, pd.errors.DatabaseError) as exc:
                    logger.warning("Could not join supplemental data for %s: %s", self.stock_id, exc)
                    continue
                if joined.empty:
                    continue
                joined["date"] = pd.to_datetime(joined["date"], errors="coerce")
                joined = joined.dropna(subset=["date"])
                self.df = self.df.merge(joined, on="date", how="left")
        finally:
            if conn is not None:
                conn.close()

    def build(self) -> pd.DataFrame:
        """Build technical indicators and attach available chip/fundamental data."""
        if self.df.empty:
            return self.df
        self.df["date"] = pd.to_datetime(self.df["date"], errors="coerce")
        self.df = self.df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        self.df = self.df[self.df["close"] > 0].copy()
        if self.df.empty:
            return self.df
        self._add_moving_averages()
        self._add_macd()
        self._add_bollinger_bands()
        self._add_kdj()
        self._add_rsi()
        self._add_log_return()
        self._add_pivot()
        self._join_fundamental_chips()
        self.df["macd"] = self.df["macd_dif"]
        return self.df


class ATRCalculator:
    """Persist ATR14 computed with Wilder's smoothing."""

    _UPSERT = """
        INSERT INTO stock_indicators (stock_id, date, atr14)
        VALUES (?, ?, ?)
        ON CONFLICT(stock_id, date) DO UPDATE SET atr14=excluded.atr14
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def calculate(
        self,
        stock_id: str,
        df: pd.DataFrame | None = None,
        *,
        _commit: bool = True,
        _ensure_schema: bool = True,
    ) -> int:
        """Calculate and upsert ATR14 for one stock.

        Internal keyword arguments let ``calculate_all`` run one transaction
        while preserving the established commit-on-single-calculation behavior.
        """
        if _ensure_schema:
            create_tables(self.db)
        if df is None:
            df = pd.read_sql_query(
                "SELECT date, high, low, close FROM stock_history "
                "WHERE stock_id = ? ORDER BY date ASC",
                self.db,
                params=(stock_id,),
            )
        else:
            df = df.copy()
        required = ["date", "high", "low", "close"]
        if df.empty or not set(required).issubset(df.columns):
            return 0
        frame = df.dropna(subset=required).sort_values("date").reset_index(drop=True)
        if frame.empty:
            return 0

        high = pd.to_numeric(frame["high"], errors="coerce")
        low = pd.to_numeric(frame["low"], errors="coerce")
        close = pd.to_numeric(frame["close"], errors="coerce")
        previous_close = close.shift(1)
        true_range = pd.concat(
            [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
            axis=1,
        ).max(axis=1)
        period = 14
        atr = pd.Series(np.nan, index=frame.index, dtype=float)
        if len(frame) >= period:
            # Seed the EWM with the first SMA so the subsequent values are
            # exactly Wilder's recursive ATR rather than a generic EWM start.
            seeded = true_range.iloc[period - 1 :].copy()
            seeded.iloc[0] = true_range.iloc[:period].mean()
            atr.iloc[period - 1 :] = seeded.ewm(alpha=1 / period, adjust=False).mean()
        rows = [
            (stock_id, _date_text(date), _sql_number(value))
            for date, value in zip(frame["date"], atr, strict=True)
        ]
        self.db.executemany(self._UPSERT, rows)
        if _commit:
            self.db.commit()
        return len(rows)

    def calculate_all(self) -> dict[str, int]:
        """Calculate ATR14 for every stock with batched reads and one commit."""
        create_tables(self.db)
        result: dict[str, int] = {}
        try:
            for stock_id, frame in _iter_stock_frames(self.db):
                result[stock_id] = self.calculate(
                    stock_id, frame, _commit=False, _ensure_schema=False
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return result


class VWAPCalculator:
    """Persist daily VWAP as raw amount divided by raw share volume."""

    _UPSERT = """
        INSERT INTO stock_indicators (stock_id, date, vwap)
        VALUES (?, ?, ?)
        ON CONFLICT(stock_id, date) DO UPDATE SET vwap=excluded.vwap
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def calculate(
        self,
        stock_id: str,
        df: pd.DataFrame | None = None,
        *,
        _commit: bool = True,
        _ensure_schema: bool = True,
    ) -> int:
        """Calculate and upsert VWAP for one stock."""
        if _ensure_schema:
            create_tables(self.db)
        if df is None:
            df = pd.read_sql_query(
                "SELECT date, volume, amount FROM stock_history "
                "WHERE stock_id = ? ORDER BY date ASC",
                self.db,
                params=(stock_id,),
            )
        else:
            df = df.copy()
        required = ["date", "volume", "amount"]
        if df.empty or not set(required).issubset(df.columns):
            return 0
        frame = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        volume = pd.to_numeric(frame["volume"], errors="coerce")
        amount = pd.to_numeric(frame["amount"], errors="coerce")
        vwap = amount.div(volume).where(volume > 0)
        rows = [
            (stock_id, _date_text(date), _sql_number(value))
            for date, value in zip(frame["date"], vwap, strict=True)
        ]
        self.db.executemany(self._UPSERT, rows)
        if _commit:
            self.db.commit()
        return len(rows)

    def calculate_all(self) -> dict[str, int]:
        """Calculate VWAP for every stock with batched reads and one commit."""
        create_tables(self.db)
        result: dict[str, int] = {}
        try:
            for stock_id, frame in _iter_stock_frames(self.db):
                result[stock_id] = self.calculate(
                    stock_id, frame, _commit=False, _ensure_schema=False
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return result


class MACalculator:
    """Persist simple moving averages, volume averages, and MA bias."""

    _UPSERT = """
        INSERT INTO stock_indicators
        (stock_id, date, ma5, ma20, ma25, ma60, ma200, vol_ma5, vol_ma20,
         vol_ma60, bias_ma25, bias_ma60, bias_ma200, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(stock_id, date) DO UPDATE SET
            ma5=excluded.ma5,
            ma20=excluded.ma20,
            ma25=excluded.ma25,
            ma60=excluded.ma60,
            ma200=excluded.ma200,
            vol_ma5=excluded.vol_ma5,
            vol_ma20=excluded.vol_ma20,
            vol_ma60=excluded.vol_ma60,
            bias_ma25=excluded.bias_ma25,
            bias_ma60=excluded.bias_ma60,
            bias_ma200=excluded.bias_ma200,
            updated_at=CURRENT_TIMESTAMP
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def calculate(
        self,
        stock_id: str,
        df: pd.DataFrame | None = None,
        *,
        _commit: bool = True,
        _ensure_schema: bool = True,
    ) -> int:
        """Calculate and upsert MA fields for one stock."""
        if _ensure_schema:
            create_tables(self.db)
        if df is None:
            df = pd.read_sql_query(
                "SELECT date, close, volume FROM stock_history "
                "WHERE stock_id = ? ORDER BY date ASC",
                self.db,
                params=(stock_id,),
            )
        else:
            df = df.copy()
        required = ["date", "close", "volume"]
        if df.empty or not set(required).issubset(df.columns):
            return 0
        frame = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
        frame = frame[frame["close"] > 0].copy()
        if frame.empty:
            return 0

        for period in (5, 10, 20, 25, 60, 120, 200):
            frame[f"sma_{period}"] = frame["close"].rolling(window=period).mean()
        frame["volume_sma_5"] = frame["volume"].rolling(window=5).mean()
        frame["volume_sma_20"] = frame["volume"].rolling(window=20).mean()
        frame["volume_sma_60"] = frame["volume"].rolling(window=60).mean()
        for period in (25, 60, 200):
            average = frame[f"sma_{period}"].replace(0, np.nan)
            frame[f"bias_ma{period}"] = (frame["close"] - average) / average * 100

        rows = [
            (
                stock_id,
                _date_text(row.date),
                _sql_number(row.sma_5),
                _sql_number(row.sma_20),
                _sql_number(row.sma_25),
                _sql_number(row.sma_60),
                _sql_number(row.sma_200),
                _sql_number(row.volume_sma_5),
                _sql_number(row.volume_sma_20),
                _sql_number(row.volume_sma_60),
                _sql_number(row.bias_ma25),
                _sql_number(row.bias_ma60),
                _sql_number(row.bias_ma200),
            )
            for row in frame.itertuples(index=False)
        ]
        self.db.executemany(self._UPSERT, rows)
        if _commit:
            self.db.commit()
        return len(rows)

    def calculate_all(self) -> dict[str, int]:
        """Calculate MA fields for every stock with bounded memory and one commit."""
        create_tables(self.db)
        result: dict[str, int] = {}
        try:
            for stock_id, frame in _iter_stock_frames(self.db):
                result[stock_id] = self.calculate(
                    stock_id, frame, _commit=False, _ensure_schema=False
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return result
