# -*- coding: utf-8 -*-
"""即時盤中指數抓取（Yahoo / TWSE MIS / TPEx）。

遵循 CONTEXT.md 架構規則 5：直接呼叫 requests，不注入 client。
測試時透過 responses / requests_mock 在模組層級 mock。
"""

from __future__ import annotations

from math import isfinite
import threading
import time
from typing import Any, Dict, Optional, Tuple

from twstock.retry import retry_get
from twstock.utils import get_http_session, get_ssl_verify, is_market_open, safe_float

# ── **Public API** — 即時盤中指數抓取 ─────────────────
# 此檔案的頂級函式（get_yahoo_market_volumes, get_realtime_mis_data,
# fetch_market_indices）為 **Public API**。
# 變更簽名前，須先檢查 dependency_graph.json 中所有依賴方。

# 修正 E4：MI_INDEX response 短 TTL cache，避免同一 fetch_market_indices
# 呼叫流程內（get_realtime_mis_data 方法1 與 尾段漲跌家數）重打同一個
# MI_INDEX URL。30 秒 TTL 保守值，不跨»一日«資料邊界（盤後資料靜止）。
_MI_INDEX_CACHE: Dict[str, Any] = {"url": None, "data": None, "ts": 0.0}
_MI_INDEX_TTL = 30.0
_MI_INDEX_LOCK = threading.Lock()


def _fetch_mi_index_cached(session, url: str) -> Optional[Dict[str, Any]]:
    """E4：MI_INDEX 短 TTL 快取。若 30 秒內曾打過同 URL，直接重用 response。

    注意：回傳的是快取內容的 reference；caller 不可 mutate（這裡供唯讀解析用）。
    """
    # 依本檔慣例：safe_http_get 在 function-local import（module-level 未匯入）
    from twstock.utils import safe_http_get

    now = time.time()
    with _MI_INDEX_LOCK:
        if (
            _MI_INDEX_CACHE["url"] == url
            and _MI_INDEX_CACHE["data"] is not None
            and now - _MI_INDEX_CACHE.get("ts", 0.0) < _MI_INDEX_TTL
        ):
            return _MI_INDEX_CACHE["data"]
    r = safe_http_get(url, session=session, timeout=5, verify=get_ssl_verify())
    if not r:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    with _MI_INDEX_LOCK:
        _MI_INDEX_CACHE["url"] = url
        _MI_INDEX_CACHE["data"] = data
        _MI_INDEX_CACHE["ts"] = now
    return data


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

        response = safe_http_get(
            url,
            session=res,
            timeout=5,
            verify=get_ssl_verify(),
            headers=headers,
        )
        if not response:
            return twse_vol, tpex_vol
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        # 修正 B3：regex 鬆緊——改用 re.S 之外的限制：
        # 1. 限定「加權指數/大盤」後「緊接」的數字+億（用 \s*允許空白，不跨行抓錯段落）
        # 2. 用 \d{1,3}(?:,\d{3})*(?:\.\d+)? 精確匹配金額格式，避免誤抓純小數
        _amt_pat = r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*億"
        twse_match = re.search(r"(?:加權指數|大盤)[^\n]{0,30}?" + _amt_pat, text)
        if twse_match:
            twse_vol = twse_match.group(1)
        tpex_match = re.search(r"(?:櫃買指數|上櫃)[^\n]{0,30}?" + _amt_pat, text)
        if tpex_match:
            tpex_vol = tpex_match.group(1)
    except Exception:
        pass
    return twse_vol, tpex_vol


# ── TWSE MIS 即時指數 ───────────────────────────────────
def _is_regular_market_open() -> bool:
    """依系統時間與官方交易日曆判斷正常交易時段。"""
    return is_market_open()


def _fetch_twse_mis(session, symbols=None) -> Dict[str, Any]:
    """呼叫 TWSE MIS 即時服務，失敗時回傳空字典。"""
    from twstock.utils import get_ssl_verify, safe_http_get

    ex_ch_list = ["tse_t00.tw", "otc_o00.tw"]
    if symbols:
        for s in symbols:
            ex_ch_list.append(f"tse_{s}.tw")
            ex_ch_list.append(f"otc_{s}.tw")

    api_url = (
        "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
        f"?ex_ch={'|'.join(ex_ch_list)}&json=1&delay=0&_={int(time.time() * 1000)}"
    )
    try:
        r = safe_http_get(
            api_url,
            session=session,
            timeout=3,
            verify=get_ssl_verify(),
            headers={"Referer": "https://mis.twse.com.tw/stock/index.jsp"},
        )
        if r:
            payload = r.json()
            return payload if isinstance(payload, dict) else {}
    except Exception as e:
        print(f"[{__name__}] get_realtime_mis_data MIS getStockInfo failed: {e}")
    return {}


def get_realtime_mis_data(symbols=None) -> Dict[str, Any]:
    """從 TWSE 官方服務抓取大盤／櫃買指數。

    正常交易時段優先使用 MIS 即時行情；MIS 無有效資料時才降級至
    MI_INDEX。盤後則反向優先 MI_INDEX，避免不必要的即時端點請求。
    """
    session = get_http_session()
    if session is None:
        return {}

    is_market_open = _is_regular_market_open()
    if is_market_open:
        live_data = _fetch_twse_mis(session, symbols)
        if live_data.get("msgArray"):
            return live_data

    try:
        url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?type=MS&response=json"
        data = _fetch_mi_index_cached(session, url)
        if data and data.get("tables"):
            return _parse_twse_mi_index(data)
    except Exception as e:
        print(f"[{__name__}] get_realtime_mis_data MI_INDEX failed: {e}")

    if not is_market_open:
        return _fetch_twse_mis(session, symbols)
    return {}


def _parse_twse_mi_index(data: Dict[str, Any]) -> Dict[str, Any]:
    """將 TWSE MI_INDEX JSON 轉為 get_realtime_mis_data 相容格式。

    TAIEX 收盤指數從「漲跌證券數合計」前一表格的 index 欄位推導，
    或直接用 TWSE 每日收盤指數 API 取得。此處採「大盤統計資訊」表格的
    fields 欄位名稱判斷哪個是收盤指數。

    注意：TWSE MI_INDEX type=MS 回傳的是「各類商品成交金額/收盤指數」表格，
    需要找 fields 中有「收盤指數」的表格，不能直接用總計 row。
    """
    result: Dict[str, Any] = {"msgArray": [], "queryTime": {}}
    sys_date = data.get("date", "")
    if sys_date and len(sys_date) == 8:
        result["queryTime"]["sysDate"] = f"{sys_date[:4]}-{sys_date[4:6]}-{sys_date[6:]}"
        # MI_INDEX 是日收盤統計；不可把目前系統時間套在舊交易日資料上。
        result["queryTime"]["sysTime"] = "13:30:00"

    # 找包含「收盤指數」的表格（非「大盤統計資訊」）
    for table in data.get("tables", []):
        title = table.get("title", "")
        rows = table.get("data", [])
        if "統計" in title and rows:
            for row in rows:
                if "總計" in str(row[0]):
                    # 這個表格的 value 欄位依次是：成交金額、成交股數、成交筆數
                    # 我們無法從 type=MS 取得收盤指數，改用漲跌證券數合計的漲跌家數
                    break

    # 取得 TAIEX 收盤指數：用 FMTQIK（每日收盤指數）API
    if not result["msgArray"]:
        try:
            from twstock.utils import get_http_session, safe_http_get

            session = get_http_session()
            if session:
                url2 = "https://www.twse.com.tw/exchangeReport/FMTQIK?response=json"
                r2 = safe_http_get(url2, session=session, timeout=5, verify=get_ssl_verify())
                if r2:
                    data2 = r2.json()
                    if data2.get("stat") == "OK" and data2.get("data"):
                        latest = data2["data"][-1]
                        #: [日期, 成交金額, 成交股數, 成交筆數, 發行量加權股價指數, 漲跌點數]
                        if len(latest) >= 6:
                            idx_str = str(latest[4]).replace(",", "").strip()
                            chg_str = str(latest[5]).replace(",", "").strip()
                            try:
                                idx_val = float(idx_str)
                                chg_val = float(chg_str)
                                prev_val = idx_val - chg_val
                                result["msgArray"].append(
                                    {
                                        "c": "t00",
                                        "z": idx_str,
                                        "y": f"{prev_val:.2f}",
                                    }
                                )
                                result["queryTime"]["sysDate"] = str(latest[0]).replace("/", "-")
                            except ValueError:
                                pass
        except Exception as e:
            print(f"[{__name__}] _parse_twse_mi_index FMTQIK fallback failed: {e}")

    return result


# ── OTC 指數（TPEx）─────────────────────────────────────
def _fetch_otc_from_tpex() -> Optional[Dict[str, Any]]:
    """從 TPEx highlight API 取得櫃買指數。回傳 dict 或 None。"""
    data = _get_tpex_highlight()
    if data is None:
        return None
    table = data["tables"][0]
    fields = table.get("fields", [])
    rows = table.get("data", [])
    if not rows:
        return None
    row = rows[0]
    field_idx = {name: i for i, name in enumerate(fields)}
    idx_i = field_idx.get("收市指數")
    chg_i = field_idx.get("指數漲跌")
    if idx_i is None or idx_i >= len(row):
        return None
    price = safe_float(row[idx_i])
    change = safe_float(row[chg_i]) if chg_i is not None and chg_i < len(row) else 0
    prev = price - change
    return {
        "price": price,
        "change": change,
        "pct": (change / prev * 100) if prev else 0,
    }


# ── TPEx highlight 短 TTL 快取（OTC 指數 + 漲跌家數共用）─────────────
_TPEX_HIGHLIGHT_CACHE: Dict[str, Any] = {"data": None, "ts": 0.0}
_TPEX_HIGHLIGHT_TTL = 30.0
_TPEX_HIGHLIGHT_LOCK = threading.Lock()


def _get_tpex_highlight() -> Optional[Dict[str, Any]]:
    """TPEx market_highlight 短 TTL 快取。

    供 _fetch_otc_from_tpex（OTC 指數）與 fetch_market_indices 尾段（OTC 漲跌家數）
    共用，避免 fetch_market_indices 一次流程內重打同一個 TPEx URL。
    """
    from twstock.utils import get_ssl_verify

    now = time.time()
    with _TPEX_HIGHLIGHT_LOCK:
        cached = _TPEX_HIGHLIGHT_CACHE["data"]
        if cached is not None and now - _TPEX_HIGHLIGHT_CACHE.get("ts", 0.0) < _TPEX_HIGHLIGHT_TTL:
            return cached
    url = "https://www.tpex.org.tw/web/stock/aftertrading/market_highlight/highlight_result.php?l=zh-tw"
    r = retry_get(url, timeout=5, retries=3, backoff=1.0, verify=get_ssl_verify(), ssl_fallback=True)
    if r is None:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    if data.get("stat") != "ok" or not data.get("tables"):
        return None
    with _TPEX_HIGHLIGHT_LOCK:
        _TPEX_HIGHLIGHT_CACHE["data"] = data
        _TPEX_HIGHLIGHT_CACHE["ts"] = now
    return data


def _market_amount_in_billions(value: object, field_name: object) -> float | None:
    """Normalize an explicitly-labelled market amount to ``億`` for the TUI.

    The TPEx highlight endpoint currently reports ``本日總成交值(佰萬元)``;
    100 佰萬元（100 百萬元）才等於一億元。端點未提供單位時不猜測，
    避免回傳看似合理但實際放大 100 倍的數字。
    """
    amount = safe_float(value, default=float("nan"))
    if not isfinite(amount):
        return None

    unit = str(field_name).replace(" ", "")
    if "億元" in unit or "億" in unit:
        return amount
    if "佰萬元" in unit or "百萬元" in unit:
        return amount / 100.0
    if "千元" in unit:
        return amount / 100_000.0
    if "萬元" in unit:
        return amount / 10_000.0
    if "元" in unit:
        return amount / 100_000_000.0
    return None


# ── 整合入口 ─────────────────────────────────────────────
def fetch_market_indices() -> Optional[Dict[str, Any]]:
    """抓取 TAIEX + OTC 指數與官方市場統計；失敗回傳 None。

    盤中只採用 MIS 即時指數。免費 MIS 不提供全市場成交金額與漲跌家數，
    因此不可拿前一交易日的盤後報表冒充今日即時統計。
    """
    market_open = is_market_open()
    results: Dict[str, Any] = {
        "TAIEX": {
            "price": 0,
            "change": 0,
            "pct": 0,
            "amount": None,
            "up": None,
            "down": None,
            "flat": None,
            "l_up": None,
            "l_down": None,
        },
        "OTC": {
            "price": 0,
            "change": 0,
            "pct": 0,
            "amount": None,
            "up": None,
            "down": None,
            "flat": None,
            "l_up": None,
            "l_down": None,
        },
        "time": "",
        "date": "",
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
                results[k].update(
                    {
                        "price": z,
                        "change": z - y,
                        "pct": (z - y) / y * 100 if y else 0,
                    }
                )
            if data.get("queryTime"):
                results["time"] = data["queryTime"].get("sysTime", "")
                results["date"] = data["queryTime"].get("sysDate", "")
    except Exception as e:
        print(f"[{__name__}] fetch_market_indices parse msgArray failed: {e}")

    # 官方免費 MIS 的 t00/o00 在盤中只有即時指數，沒有全市場成交金額、
    # 漲跌家數。到此直接返回，避免後續 MI_INDEX / market_highlight 將
    # 前一交易日盤後數字混入今日即時面板。
    if market_open:
        if results["TAIEX"]["price"] > 0 or results["OTC"]["price"] > 0:
            return results
        return None

    # OTC 指數：從 TPEx highlight API 補齊（get_realtime_mis_data 只提供 TAIEX）
    if results["OTC"]["price"] == 0:
        try:
            otc_data = _fetch_otc_from_tpex()
            if otc_data:
                results["OTC"].update(otc_data)
        except Exception as e:
            print(f"[{__name__}] fetch_market_indices OTC fallback failed: {e}")

    try:
        import re as _re

        session = get_http_session()
        if session is None:
            return None

        url_tse = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?type=MS&response=json"
        # E4：改走 _fetch_mi_index_cached，與 get_realtime_mis_data 方法1 共用同一次 HTTP 回應，
        # 消除原尾段自己再打一次 MI_INDEX 的重複外部呼叫。
        r_tse_data = _fetch_mi_index_cached(session, url_tse)

        if r_tse_data and r_tse_data.get("tables"):

            def _clean(s):
                return str(s).replace(",", "").strip()

            def _parse_breadth(s):
                s = _clean(s)
                m = _re.search(r"(\d+)\((\d+)\)", s)
                if m:
                    return int(m.group(1)), int(m.group(2))
                return int(s) if s.isdigit() else 0, 0

            def _normalize_title(title: str) -> str:
                return "".join(str(title or "").split())

            t_breadth = next(
                (
                    t
                    for t in r_tse_data["tables"]
                    if "漲跌證券數合計" in _normalize_title(t.get("title", ""))
                ),
                None,
            )
            if t_breadth:
                data_rows = t_breadth.get("data", [])
                fields = t_breadth.get("fields", [])
                field_idx = {name: i for i, name in enumerate(fields)}
                stock_col = field_idx.get("股票", 2)
                if len(data_rows) >= 3:
                    results["TAIEX"]["up"], results["TAIEX"]["l_up"] = _parse_breadth(
                        data_rows[0][stock_col] if stock_col < len(data_rows[0]) else ""
                    )
                    results["TAIEX"]["down"], results["TAIEX"]["l_down"] = _parse_breadth(
                        data_rows[1][stock_col] if stock_col < len(data_rows[1]) else ""
                    )
                    results["TAIEX"]["flat"] = _parse_breadth(
                        data_rows[2][stock_col] if stock_col < len(data_rows[2]) else ""
                    )[0]

            t_total = next(
                (t for t in r_tse_data["tables"] if "大盤統計資訊" in t.get("title", "")),
                None,
            )
            if t_total:
                for row in t_total.get("data", []):
                    if row and "總計" in str(row[0]) and len(row) > 1:
                        amt_val = safe_float(row[1])
                        results["TAIEX"]["amount"] = round(amt_val / 1e8, 2)

        # 改走 _get_tpex_highlight 快取，與前段 _fetch_otc_from_tpex 共用同一次 HTTP 回應，
        # 消除 tail 自己再打一次 TPEx 的重複外部呼叫。
        r_otc_data = _get_tpex_highlight()

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

                results["OTC"]["up"] = _safe_int_idx(field_idx.get("上漲家數"))
                results["OTC"]["l_up"] = _safe_int_idx(field_idx.get("漲停家數"))
                results["OTC"]["down"] = _safe_int_idx(field_idx.get("下跌家數"))
                results["OTC"]["l_down"] = _safe_int_idx(field_idx.get("跌停家數"))
                results["OTC"]["flat"] = _safe_int_idx(field_idx.get("平盤家數"))
                amount_idx = next(
                    (
                        idx
                        for idx, field in enumerate(fields)
                        if "成交值" in str(field) or "成交金額" in str(field)
                    ),
                    None,
                )
                if amount_idx is not None and amount_idx < len(row):
                    amount = _market_amount_in_billions(row[amount_idx], fields[amount_idx])
                    if amount is not None:
                        results["OTC"]["amount"] = amount
    except Exception as e:
        print(f"[{__name__}] fetch_market_indices TWSE/TPEx table parse failed: {e}")

    if results["TAIEX"]["price"] > 0 or results["OTC"]["price"] > 0:
        return results
    return None
