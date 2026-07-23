"""Kronos 本機權重載入契約。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from twstock.strategy.kronos_engine import KronosRealEngine, load_kronos


def test_load_kronos_uses_eval_and_device_autodetection(tmp_path, monkeypatch):
    """載入後必須關閉 dropout；未設定裝置時讓 Predictor 自動偵測。"""
    model_dir = tmp_path / "model"
    tokenizer_dir = tmp_path / "tokenizer"
    model_dir.mkdir()
    tokenizer_dir.mkdir()
    monkeypatch.delenv("KRONOS_DEVICE", raising=False)

    model = MagicMock()
    tokenizer = MagicMock()
    predictor = MagicMock()
    with (
        patch(
            "twstock.vendor.kronos.Kronos.from_pretrained",
            return_value=model,
        ) as model_loader,
        patch(
            "twstock.vendor.kronos.KronosTokenizer.from_pretrained",
            return_value=tokenizer,
        ) as tokenizer_loader,
        patch("twstock.vendor.kronos.KronosPredictor", return_value=predictor) as predictor_cls,
    ):
        loaded_tokenizer, loaded_model, loaded_predictor = load_kronos(
            str(model_dir), str(tokenizer_dir)
        )

    tokenizer_loader.assert_called_once_with(str(tokenizer_dir))
    model_loader.assert_called_once_with(str(model_dir))
    tokenizer.eval.assert_called_once_with()
    model.eval.assert_called_once_with()
    predictor_cls.assert_called_once_with(model, tokenizer, device=None, max_context=512)
    assert (loaded_tokenizer, loaded_model, loaded_predictor) == (tokenizer, model, predictor)


def test_load_kronos_respects_explicit_device(tmp_path, monkeypatch):
    model_dir = tmp_path / "model"
    tokenizer_dir = tmp_path / "tokenizer"
    model_dir.mkdir()
    tokenizer_dir.mkdir()
    monkeypatch.setenv("KRONOS_DEVICE", "cpu")

    with (
        patch("twstock.vendor.kronos.Kronos.from_pretrained", return_value=MagicMock()) as ml,
        patch(
            "twstock.vendor.kronos.KronosTokenizer.from_pretrained", return_value=MagicMock()
        ) as tl,
        patch("twstock.vendor.kronos.KronosPredictor") as predictor_cls,
    ):
        load_kronos(str(model_dir), str(tokenizer_dir))

    predictor_cls.assert_called_once_with(ml.return_value, tl.return_value, device="cpu", max_context=512)


def test_prediction_uses_business_dates_and_does_not_invent_confidence():
    """官方回傳已平均樣本，應跳過週末且不可誤報 100% 信心。"""
    index = pd.bdate_range(end="2026-07-17", periods=10)  # Friday
    frame = pd.DataFrame(
        {
            "open": range(100, 110),
            "high": range(101, 111),
            "low": range(99, 109),
            "close": range(100, 110),
            "volume": [1_000] * 10,
            "amount": [100_000] * 10,
        },
        index=index,
    )
    predictor = MagicMock()
    predictor.predict.return_value = pd.DataFrame(
        {"close": [110.0, 111.0]},
        index=pd.bdate_range("2026-07-20", periods=2),
    )
    engine = KronosRealEngine()
    engine._predictor = predictor

    result = engine.predict(frame, {"pred_days": 2})

    call = predictor.predict.call_args.kwargs
    assert list(call["y_timestamp"].dt.strftime("%Y-%m-%d")) == ["2026-07-20", "2026-07-21"]
    assert call["sample_count"] == 5
    assert result.confidence == 0.0
