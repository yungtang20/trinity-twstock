# -*- coding: utf-8 -*-
"""Shared helpers for official subpackage.

Note: safe_float / safe_int 已統一至 twstock.utils，本模組保留
向舊程式匯入路徑（from official.utils import safe_float）。
"""

from twstock.utils import safe_float, safe_int  # noqa: F401  (re-export for backwards compat)
