# -*- coding: utf-8 -*-
"""
test_no_etl_unit_conversion.py — 禁止在 ETL 層做單位轉換

DB 永遠存原始值（股/元），顯示層才轉換。
這個測試確保 fetcher 不再寫入前做 /1000 或 /1e7。
"""

from __future__ import annotations

from pathlib import Path


def test_quotes_py_has_no_divide_1000_for_volume():
    """quotes.py 不應在寫入前對 volume/amount 做除法轉換。"""
    content = Path("twstock/official/quotes.py").read_text(encoding="utf-8")

    # 確認不存在「safe_int(x) // 1000」或「/ 10000000」這種寫入前轉換
    assert "safe_int(x) // 1000" not in content, "quotes.py 仍在寫入前將 volume 除以 1000（轉張）"
    assert "/ 10000000" not in content, "quotes.py 仍在寫入前將 amount 除以 1e7（轉千萬元）"


def test_institutional_py_has_no_divide_1000_for_shares():
    """institutional.py 不應在寫入前對買賣超股數做除法轉換。"""
    content = Path("twstock/official/institutional.py").read_text(encoding="utf-8")

    # 確認不存在「safe_int(x) // 1000」這種寫入前轉換
    assert (
        "safe_int(x) // 1000" not in content
    ), "institutional.py 仍在寫入前將股數除以 1000（轉張）"
