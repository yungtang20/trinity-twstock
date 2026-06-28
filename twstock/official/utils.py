#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
official/utils.py - 共用輔助函數
"""

def safe_int(val, default=0):
    """安全轉換為整數"""
    try:
        if val is None:
            return default
        if isinstance(val, str):
            val = val.replace(',', '').strip()
            if val in ('', '--', '---', '-', '除息', '除權', '除權息', 'X'):
                return default
        return int(float(val))
    except (ValueError, TypeError):
        return default

import numpy as np

def safe_float(val, default=np.nan):
    """安全轉換為浮點數，預設回傳 NaN (price類)"""
    try:
        if val is None:
            return default
        if isinstance(val, str):
            val = val.replace(',', '').strip()
            if val in ('', '--', '---', '-', '除息', '除權', '除權息', 'X'):
                return default
        return float(val)
    except (ValueError, TypeError):
        return default