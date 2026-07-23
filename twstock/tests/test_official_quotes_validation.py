"""Official quote payload validation regressions."""

from __future__ import annotations

import pandas as pd

from twstock.official.quotes import _get_valid_ohlc_rows


def test_get_valid_ohlc_rows_rejects_placeholders_and_bad_ranges() -> None:
    frame = pd.DataFrame(
        {
            "stock_id": ["1538", "2330", "2317"],
            "open": [0.0, 100.0, 110.0],
            "high": [0.0, 99.0, 115.0],
            "low": [0.0, 95.0, 105.0],
            "close": [0.0, 102.0, 112.0],
            "volume": [1, 1000, 2000],
            "amount": [9, 100000, 200000],
        }
    )

    result = _get_valid_ohlc_rows(frame, "test")

    assert result["stock_id"].tolist() == ["2317"]
