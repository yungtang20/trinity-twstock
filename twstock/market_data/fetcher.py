# -*- coding: utf-8 -*-
"""即時盤中指數抓取（Yahoo / TWSE MIS / TPEx）。

遵循 CONTEXT.md 架構規則 5：直接呼叫 requests，不注入 client。
測試時透過 responses / requests_mock 在模組層級 mock。
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

# 確保 twstock 在 sys.path（讓 from utils import 能運作）
_PKG_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

from twstock.utils import get_http_session, safe_float, safe_int  # noqa: E402
from twstock.utils import get_ssl_verify


# ── **Public API** — 即時盤中指數抓取 ─────────────────
# 此檔案的頂級函式（get_yahoo_market_volumes, get_realtime_mis_data,
# fetch_market_indices）為 **Public API**。
# 變更簽名前，須先檢查 dependency_graph.json 中所有依賴方。


# ── Yahoo 成交金額 ──────────────────────────────────────
def get_yahoo_market_volumes() -> Tuple[str, str]:
    """從 Yahoo 財經抓取 TWSE / TPEx 成交金額（億）。"""
    url = "https://tw.stock.yahoo.com/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    twse_vol = "無資料"
    tpex_vol = "無資料"
    try:
        import re
        from bs4 import BeautifulSoup

        res = get_http_session()
        if res is None:
            return twse_vol, tpex_vol
        from twstock.utils import safe_http_get

        response = safe_http_get(url, timeout=5, headers=headers)
        if not response:
            return twse_vol, tpex_vol
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        twse_match = re.search(r"(?:加權指數|大盤).{0,50}?([\d,\.]+)\s*億", text)
        if twse_match:
            twse_vol = twse_match.group(1)
        tpex_match = re.search(r"(?:櫃買指數|上櫃).{0,50}?([\d,\.]+)\s*億", text)
        if tpex_match:
            tpex_vol = tpex_match.group(1)
    except Exception:
        pass
    return twse_vol, tpex_vol


# ── TWSE MIS 即時指數 ───────────────────────────────────
def get_realtime_mis_data(symbols=None) -> Dict[str, Any]:
    """從 TWSE MIS API 抓取大盤 / 櫃買即時指數。"""
    session = get_http_session()
    if session is None:
        return {}
    try:
        from twstock.utils import safe_http_get

        safe_http_get(
            "https://mis.twstock.com.tw/stock/index.jsp",
            session=session, timeout=5, verify=get_ssl_verify(),
        )
    except Exception:
        pass

    ex_ch_list = ["tse_t00.tw", "otc_o00.tw"]
    if symbols:
        for s in symbols:
            ex_ch_list.append(f"tse_{s}.tw")
            ex_ch_list.append(f"otc_{s}.tw")

    api_url = (
        "https://mis.twstock.com.tw/stock/api/getStockInfo.jsp"
        f"?ex_ch={'|'.join(ex_ch_list)}&json=1&delay=0&_={int(time.time() * 1000)}"
    )
    from twstock.utils import safe_http_get

    r = safe_http_get(api_url, session=session, timeout=1.5, verify=True)
    if not r:
        return {}
    try:
        return r.json()
    except ValueError:
        return {}


# ── 整合入口 ─────────────────────────────────────────────
def fetch_market_indices() -> Optional[Dict[str, Any]]:
    """抓取 TAIEX + OTC 即時指數 + 成交量。失败回傳 None。"""
    results = {
        "TAIEX": {"price": 0, "change": 0, "pct": 0, "amount": 0,
                  "up": None, "down": None, "flat": None, "l_up": None, "l_down": None},
        "OTC":   {"price": 0, "change": 0, "pct": 0, "amount": 0,
                  "up": None, "down": None, "flat": None, "l_up": None, "l_down": None},
        "time": "", "date": "",
    }
    try:
        data = get_realtime_mis_data()
        if data and data.get("msgArray"):
            for item in data["msgArray"]:
                k = "TAIEX" if item.get("c") == "t00" else "OTC"
                z = safe_float(item.get("z"), 0)
                y = safe_float(item.get("y"), 0)
                if z == 0:
                    z = y
                results[k].update({
                    "price": z, "change": z - y,
                    "pct": (z - y) / y * 100 if y else 0,
                })
            if data.get("queryTime"):
                results["time"] = data["queryTime"].get("sysTime", "")
                results["date"] = data["queryTime"].get("sysDate", "")
    except Exception:
        pass

    try:
        twse_vol, tpex_vol = get_yahoo_market_volumes()
        if twse_vol != "無資料":
            results["TAIEX"]["amount"] = safe_float(twse_vol.replace(",", ""))
        if tpex_vol != "無資料":
            results["OTC"]["amount"] = safe_float(tpex_vol.replace(",", ""))
    except Exception:
        pass

    try:
        import re as _re

        session = get_http_session()
        if session is None:
            return None
        from twstock.utils import safe_http_get

        url_tse = (
            "https://www.twstock.com.tw/rwd/zh/afterTrading/"
            "MI_INDEX?type=MS&response=json"
        )
        r_tse_data = None
        for _ in range(1):
            r_tse = safe_http_get(url_tse, session=session, timeout=1.5, verify=True)
            if r_tse:
                try:
                    r_tse_data = r_tse.json()
                    break
                except ValueError:
                    pass

        if r_tse_data and r_tse_data.get("tables"):
            def _clean(s):
                return str(s).replace(",", "").strip()

            def _parse_breadth(s):
                s = _clean(s)
                m = _re.search(r"(\d+)\((\d+)\)", s)
                if m:
                    return int(m.group(1)), int(m.group(2))
                return int(s) if s.isdigit() else 0, 0

            t_breadth = next(
                (t for t in r_tse_data["tables"]
                 if "漲跌證券數合計" in t.get("title", "")),
                None,
            )
            if t_breadth:
                data_rows = t_breadth.get("data", [])
                if len(data_rows) >= 3:
                    results["TAIEX"]["up"], results["TAIEX"]["l_up"] = _parse_breadth(data_rows[0][2])
                    results["TAIEX"]["down"], results["TAIEX"]["l_down"] = _parse_breadth(data_rows[1][2])
                    results["TAIEX"]["flat"] = _parse_breadth(data_rows[2][2])[0]

            t_total = next(
                (t for t in r_tse_data["tables"] if "大盤統計資訊" in t.get("title", "")),
                None,
            )
            if t_total:
                for row in t_total.get("data", []):
                    if "總計" in row[0]:
                        amt_val = safe_float(row[1])
                        results["TAIEX"]["amount"] = round(amt_val / 1e8, 2)

        url_otc = (
            "https://www.tpex.org.tw/web/stock/aftertrading/"
            "market_highlight/highlight_result.php?l=zh-tw"
        )
        r_otc_data = None
        for _ in range(1):
            r_otc = safe_http_get(url_otc, session=session, timeout=1.5, verify=True)
            if r_otc:
                try:
                    r_otc_data = r_otc.json()
                    break
                except ValueError:
                    pass

        if r_otc_data and r_otc_data.get("stat") == "ok" and r_otc_data.get("tables"):
            otc_table = r_otc_data["tables"][0]
            fields = otc_table.get("fields", [])
            data_rows = otc_table.get("data", [])
            field_idx = {name: i for i, name in enumerate(fields)}
            if len(data_rows) > 0:
                row = data_rows[0]

                def _safe_int_idx(idx):
                    if idx is None or idx >= len(row):
                        return None
                    val = str(row[idx]).replace(",", "").strip()
                    return int(val) if val.isdigit() else None

                results["OTC"]["up"]    = _safe_int_idx(field_idx.get("上漲家數"))
                results["OTC"]["l_up"]  = _safe_int_idx(field_idx.get("漲停家數"))
                results["OTC"]["down"]  = _safe_int_idx(field_idx.get("下跌家數"))
                results["OTC"]["l_down"] = _safe_int_idx(field_idx.get("跌停家數"))
                results["OTC"]["flat"]  = _safe_int_idx(field_idx.get("平盤家數"))
                if len(row) > 3:
                    amt_str = row[3].replace(",", "")
                    if amt_str.isdigit():
                        results["OTC"]["amount"] = safe_float(amt_str) / 100.0
    except Exception:
        pass

    if results["TAIEX"]["price"] > 0 or results["OTC"]["price"] > 0:
        return results
    return None
