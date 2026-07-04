# -*- coding: utf-8 -*-
"""
test_strategy_runner_dispatch.py — strategy_runner dispatch 契約測試

驗證 strategy_runner.py 不再自帶策略演算法，
而是 dispatch 到 ma_strategy / sr_analyzer / chips_strategy / patterns_strategy。
"""

from __future__ import annotations

import sqlite3
import sys
from unittest.mock import MagicMock, patch

import pytest


def _seed_stock_data(db_conn: sqlite3.Connection) -> None:
    """植入 2330 的 30 天測試資料。"""
    db_conn.execute("""
        INSERT INTO stock_meta (stock_id, stock_name, market, type)
        VALUES ('2330', '台積電', 'TSE', 'COMMON')
    """)
    for i in range(1, 31):
        db_conn.execute(
            "INSERT INTO stock_history (stock_id, date, open, high, low, close, volume, amount) "
            "VALUES ('2330', ?, ?, ?, ?, ?, 1000000, 100000000)",
            (f"2026-06-{i:02d}", 100 + i, 105 + i, 95 + i, 102 + i),
        )
    db_conn.execute("""
        INSERT INTO institutional_data
            (stock_id, date, foreign_net, trust_net, dealer_net, institutional_net,
             foreign_buy, foreign_sell, trust_buy, trust_sell, dealer_buy, dealer_sell, source)
        VALUES ('2330', '2026-06-30', 3000000, 600000, 300000, 3900000,
                8000000, 5000000, 1000000, 400000, 600000, 300000, 'official')
    """)
    db_conn.commit()


def test_strategy_runner_has_no_inline_algorithm():
    """strategy_runner.py 不應再包含自實的 MA/SR/chips/pattern 演算法。

    驗證方式：原始碼中不應「定義」私有策略函式
    （允許 import 引用 strategy 模組的函式）。
    """
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "strategy_runner.py"
    content = src.read_text(encoding="utf-8")

    # 不應有自實的 MA 計算定義
    assert (
        "def _compute_ma_with_deduction(" not in content
    ), "strategy_runner 不應定義 _compute_ma_with_deduction"
    assert "def calc_ma(" not in content, "strategy_runner 不應定義 calc_ma"
    # 不應有額外的輔助計算法（get_trend、get_tomorrow 是 run_ma_analysis 的
    # 內部輔助函式，用於格式化輸出，不算獨立策略演算法）


def test_strategy_runner_dispatches_ma():
    """strategy_runner.run_ma_analysis() 應該呼叫 ma_strategy 而非自行計算。"""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "strategy_runner.py"
    content = src.read_text(encoding="utf-8")

    # 應 import ma_strategy
    assert (
        "from strategy" in content or "import strategy" in content or "twstock.strategy" in content
    ), "strategy_runner 應 import strategy 模組"
    # 應呼叫外部策略
    assert "ma_strategy" in content or "run_ma" in content, "應有對 ma_strategy 的呼叫"


def test_strategy_runner_dispatches_chips():
    """strategy_runner.run_chips_analysis() 應 dispatch 到 chips_strategy。"""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "strategy_runner.py"
    content = src.read_text(encoding="utf-8")

    assert "chips_strategy" in content or "StockAnalyzer" in content, "應有對 chips_strategy 的引用"


def test_strategy_runner_dispatches_sr():
    """strategy_runner.run_sr_analysis() 應 dispatch 到 sr_analyzer。"""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "strategy_runner.py"
    content = src.read_text(encoding="utf-8")

    assert "sr_analyzer" in content, "應有對 sr_analyzer 的引用"


def test_strategy_runner_dispatches_pattern():
    """strategy_runner.run_pattern_analysis() 應 dispatch 到 patterns_strategy。"""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "strategy_runner.py"
    content = src.read_text(encoding="utf-8")

    assert "patterns_strategy" in content, "應有對 patterns_strategy 的引用"


def test_strategy_runner_main_runs_all():
    """main() 應輸出所有策略結果。"""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "strategy_runner.py"
    content = src.read_text(encoding="utf-8")

    assert '"sr"' in content or "'sr'" in content, "main 應輸出 sr 策略"
    assert '"ma"' in content or "'ma'" in content, "main 應輸出 ma 策略"
    assert '"chips"' in content or "'chips'" in content, "main 應輸出 chips 策略"


def test_strategy_runner_dispatches_to_real_strategy(monkeypatch):
    """strategy_runner.run_strategy() 應 dispatch 到正式策略模組。

    驗證方式：mock get_strategy，確認 run_strategy 正確呼叫 strategy.analyze()。
    """
    called = {}

    class FakeStrategy:
        def analyze(self, stock_id):
            called["stock_id"] = stock_id
            return {"stock_id": stock_id, "signal": "buy"}

    def fake_get_strategy(name):
        assert name == "chips", f"應請求 'chips' 策略，實際 '{name}'"
        return FakeStrategy()

    import strategy_runner

    monkeypatch.setattr(strategy_runner, "get_strategy", fake_get_strategy)

    result = strategy_runner.run_strategy("chips", "2330")

    assert called["stock_id"] == "2330", "應正確傳遞 stock_id 給策略"
    assert result["signal"] == "buy", "應回傳策略分析結果"


def test_strategy_runner_does_not_use_random_prediction():
    """strategy_runner.py 不應使用 random 預測（避免假邏輯混入正式輸出）。"""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "strategy_runner.py"
    content = src.read_text(encoding="utf-8")

    # 不應有 np.random 或 random. 的使用
    assert "np.random" not in content, "strategy_runner 不應使用 np.random"
    assert "random." not in content, "strategy_runner 不應使用 random 模組"


# ── Runtime behavior tests ────────────────────────────────


def test_strategy_runner_main_runs_all_strategies():
    """main() 應執行所有策略並寫入結果。"""
    import strategy_runner

    with (
        patch("strategy_runner.run_sr_analysis", return_value={}),
        patch("strategy_runner.run_ma_analysis", return_value={}),
        patch("strategy_runner.run_chips_analysis", return_value={}),
        patch("strategy_runner.run_pattern_analysis", return_value={}),
        patch("strategy_runner.run_prediction_analysis", return_value={}),
    ):

        mock_writer = MagicMock()
        with patch.object(sys, "argv", ["strategy_runner.py", "2330"]):
            strategy_runner.main(writer=mock_writer)

        mock_writer.write_result.assert_called_once()
        call_args = mock_writer.write_result.call_args[0][0]
        assert call_args["stockId"] == "2330"
        assert "strategies" in call_args


def test_strategy_runner_main_handles_error():
    """main() 遇到錯誤應呼叫 write_error。"""
    import strategy_runner

    with patch("strategy_runner.run_sr_analysis", side_effect=Exception("DB error")):
        mock_writer = MagicMock()
        with patch.object(sys, "argv", ["strategy_runner.py", "2330"]):
            with pytest.raises(SystemExit):
                strategy_runner.main(writer=mock_writer)

        mock_writer.write_error.assert_called_once()


def test_strategy_runner_main_no_args_exits():
    """main() 無 args 應顯示用法並 exit。"""
    import strategy_runner

    mock_writer = MagicMock()
    with patch.object(sys, "argv", ["strategy_runner.py"]):
        with pytest.raises(SystemExit):
            strategy_runner.main(writer=mock_writer)

    mock_writer.write_error.assert_called_once()
    assert "用法" in mock_writer.write_error.call_args[0][0]


def test_prediction_adapter_no_data():
    """_PredictionAdapter.analyze 應處理資料不足的情況。"""
    from strategy_runner import _PredictionAdapter

    adapter = _PredictionAdapter()
    # 無資料時應回傳 error dict
    result = adapter.analyze("9999")
    assert isinstance(result, dict)


def test_run_prediction_analysis():
    """run_prediction_analysis 應呼叫 _PredictionAdapter。"""
    import strategy_runner

    with patch.object(strategy_runner, "_PredictionAdapter") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.analyze.return_value = {"predictions": []}
        mock_cls.return_value = mock_instance

        result = strategy_runner.run_prediction_analysis("2330", ma={"ma25Trend": "up"})
        mock_instance.analyze.assert_called_once_with("2330", ma={"ma25Trend": "up"})
        assert result == {"predictions": []}
