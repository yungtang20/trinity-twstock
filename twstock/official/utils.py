# -*- coding: utf-8 -*-
"""Shared helpers for official subpackage.

Note: safe_float / safe_int 已統一至 twstock.utils，本模組保留
向舊程式匯入路徑（from official.utils import safe_float）。
"""

from twstock.utils import safe_float, safe_int  # noqa: F401  (re-export for backwards compat)

import requests


def _get_session():
    """建立帶預設 User-Agent 的 requests.Session。

    供 official/ 套件內的爬蟲模組使用,在模組載入時建立全域 SESSION。
    """
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    return session
