#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LongCat AI 視覺引擎 v1.0
提供深度視覺辨識分析功能
"""

from typing import Dict, Optional, Any
import numpy as np


class VisionEngine:
    """LongCat AI 視覺分析引擎"""

    def analyze_pattern(
        self,
        df: Any,
        code: str,
        name: str,
        predictions: Optional[np.ndarray] = None,
        correction: float = 0.0,
        sr_lines: Optional[Dict] = None,
    ) -> str:
        """
        分析股票型態並返回分析報告

        Args:
            df: pandas DataFrame 包含歷史數據
            code: 股票代號
            name: 股票名稱
            predictions: 預測路徑
            correction: 漂移修正
            sr_lines: 支撐壓力線

        Returns:
            分析報告字串
        """
        try:
            # 基本分析
            if df is None or len(df) == 0:
                return "無數據可分析"

            # 取得最新收盤價
            if hasattr(df, 'iloc'):
                # pandas DataFrame
                current_price = float(df['close'].iloc[-1])
            else:
                # 其他格式
                current_price = float(df['close'][-1]) if 'close' in df else 0

            # 計算簡單指標
            if len(df) >= 20:
                if hasattr(df, 'rolling'):
                    ma5 = float(df['close'].rolling(5).mean().iloc[-1]) if hasattr(df, 'iloc') else current_price
                    ma20 = float(df['close'].rolling(20).mean().iloc[-1]) if hasattr(df, 'iloc') else current_price
                else:
                    ma5 = current_price
                    ma20 = current_price
            else:
                ma5 = current_price
                ma20 = current_price

            # 趨勢判斷
            trend = "多頭" if ma5 > ma20 else "空頭" if ma5 < ma20 else "盤整"

            # 如果有預測路徑
            pred_info = ""
            if predictions is not None and len(predictions) > 0:
                pred_price = float(predictions[-1]) if hasattr(predictions, '__getitem__') else float(predictions)
                change_pct = (pred_price - current_price) / current_price * 100 if current_price > 0 else 0
                pred_info = f"\n預測目標: {pred_price:.2f} ({change_pct:+.1f}%)"

            # 支撐壓力線
            sr_info = ""
            if sr_lines:
                if sr_lines.get('resistance'):
                    sr_info += f"\n壓力線: {sr_lines['resistance']:.2f}"
                if sr_lines.get('support'):
                    sr_info += f"\n支撐線: {sr_lines['support']:.2f}"

            return (
                f"股票: {code} {name}\n"
                f"現價: {current_price:.2f}\n"
                f"MA5: {ma5:.2f} | MA20: {ma20:.2f}\n"
                f"趨勢: {trend}"
                f"{pred_info}"
                f"{sr_info}"
            )

        except Exception as e:
            return f"分析失敗: {str(e)}"


# 全域實例
VISION_ENGINE = VisionEngine()
