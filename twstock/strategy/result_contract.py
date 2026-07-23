"""Utilities for keeping strategy results compatible with the public JSON contract.

The interactive strategy modules historically returned small, display-oriented
dictionaries (for example ``bullish``/``bearish`` signals).  API and JSON
consumers, however, need a stable shape.  This module is deliberately free of
database and UI imports so every strategy can use the same adapter without
creating a circular dependency.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import math
from numbers import Real
from typing import Any


_SIGNAL_MAP = {
    "buy": "BUY",
    "bullish": "BUY",
    "long": "BUY",
    "up": "BUY",
    "strong_buy": "BUY",
    "hold": "HOLD",
    "neutral": "HOLD",
    "flat": "HOLD",
    "wait": "HOLD",
    "sell": "SELL",
    "bearish": "SELL",
    "short": "SELL",
    "down": "SELL",
    "strong_sell": "SELL",
    "unknown": "UNKNOWN",
    "": "UNKNOWN",
}

_SCORE_BY_SIGNAL = {"BUY": 75, "HOLD": 50, "SELL": 25, "UNKNOWN": 0}
_CORE_KEYS = {
    "strategy",
    "stock_id",
    "stockId",
    "stock_name",
    "stockName",
    "date",
    "latest_date",
    "score",
    "signal",
    "confidence",
    "summary",
    "reason",
    "message",
    "details",
}


def normalize_signal(value: Any) -> str:
    """Return one of the documented ``BUY/HOLD/SELL/UNKNOWN`` signals."""
    if value is None:
        return "UNKNOWN"
    text = str(value).strip()
    return _SIGNAL_MAP.get(text.lower(), text.upper() if text.upper() in _SCORE_BY_SIGNAL else "UNKNOWN")


def _bounded_percent(value: Any, default: int) -> int:
    """Coerce a number to an integer percentage in the inclusive 0..100 range."""
    if isinstance(value, bool) or not isinstance(value, Real):
        return default
    numeric = float(value)
    if not math.isfinite(numeric):
        return default
    # Model APIs often expose confidence as a 0..1 fraction, while the JSON
    # contract specifies percent.  Preserve integer scores such as ``1``.
    if 0 <= numeric < 1:
        numeric *= 100
    return max(0, min(100, int(round(numeric))))


def _date_text(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)


def normalize_strategy_result(
    result: Mapping[str, Any] | None,
    *,
    strategy: str | None = None,
    stock_id: str | None = None,
) -> dict[str, Any]:
    """Adapt a strategy result to the documented, version-stable JSON shape.

    Unknown existing fields remain at the top level for backwards
    compatibility and are also placed in ``details`` for JSON consumers.  No
    analysis values are invented: missing score/confidence values get neutral
    contract defaults and missing date/name values remain empty strings.
    """
    raw = dict(result or {})
    canonical_signal = normalize_signal(raw.get("signal"))
    resolved_strategy = str(raw.get("strategy") or strategy or "unknown")
    resolved_stock_id = str(raw.get("stock_id") or raw.get("stockId") or stock_id or "")

    raw_details = raw.get("details")
    details = dict(raw_details) if isinstance(raw_details, Mapping) else {}
    for key, value in raw.items():
        if key not in _CORE_KEYS:
            details.setdefault(key, value)

    summary = raw.get("summary") or raw.get("reason") or raw.get("message") or ""
    normalized: dict[str, Any] = {
        "strategy": resolved_strategy,
        "stock_id": resolved_stock_id,
        "stock_name": str(raw.get("stock_name") or raw.get("stockName") or ""),
        "date": _date_text(raw.get("date") or raw.get("latest_date")),
        "score": _bounded_percent(raw.get("score"), _SCORE_BY_SIGNAL[canonical_signal]),
        "signal": canonical_signal,
        "confidence": _bounded_percent(raw.get("confidence"), 0),
        "summary": str(summary),
        "details": details,
    }

    # Preserve legacy data while exposing a canonical payload.  ``details``
    # is intentionally not overwritten so callers can reliably traverse it.
    for key, value in raw.items():
        if key not in {"strategy", "stock_id", "stockId", "stock_name", "stockName", "date", "latest_date", "score", "signal", "confidence", "summary", "details"}:
            normalized[key] = value
    return normalized


def normalize_json_payload(data: Any) -> Any:
    """Normalize strategy-shaped result/scan payloads without changing generic JSON."""
    if not isinstance(data, Mapping):
        return data

    payload = dict(data)
    if isinstance(payload.get("strategies"), Mapping):
        root_stock_id = str(payload.get("stock_id") or payload.get("stockId") or "")
        payload["stock_id"] = root_stock_id
        payload["stockId"] = root_stock_id  # documented legacy runner field
        payload["data_source"] = payload.get("data_source") or payload.get("dataSource") or "sqlite"
        payload["dataSource"] = payload["data_source"]
        payload["strategies"] = {
            str(name): normalize_strategy_result(value if isinstance(value, Mapping) else {}, strategy=str(name), stock_id=root_stock_id)
            for name, value in payload["strategies"].items()
        }
        return payload

    if isinstance(payload.get("results"), list):
        strategy = payload.get("strategy")
        payload["results"] = [
            normalize_strategy_result(item, strategy=strategy)
            if isinstance(item, Mapping)
            else item
            for item in payload["results"]
        ]
        payload["total"] = len(payload["results"])
        return payload

    if {"strategy", "stock_id", "stockId", "signal"}.intersection(payload):
        return normalize_strategy_result(payload)
    return payload


__all__ = ["normalize_json_payload", "normalize_signal", "normalize_strategy_result"]
