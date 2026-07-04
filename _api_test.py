#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 測試腳本 — 逐一驗證所有外部 API 端點

測試項目：
- HTTP Status
- JSON 格式
- 欄位名稱
- 資料型態
- 日期格式
- 錯誤回傳
- Rate Limit
- Timeout
"""

import datetime
import json
import logging
import os
import time

import requests

# Load env
from dotenv import load_dotenv

load_dotenv("twstock/api.env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

RESULTS = []


def record(name, status, details, ok=True):
    if isinstance(details, str):
        details = {"note": details}
    RESULTS.append(
        {
            "name": name,
            "status": status,
            "ok": ok,
            "details": details,
        }
    )
    icon = "✅" if ok else "❌"
    log.info(f"{icon} {name}: {status}")
    if details and isinstance(details, dict):
        for k, v in details.items():
            log.info(f"   {k}: {v}")


# ============================================================
# 1. FinMind API
# ============================================================
def test_finmind():
    log.info("=" * 60)
    log.info("TESTING: FinMind API")
    log.info("=" * 60)

    token = os.environ.get("FINMIND_TOKEN", "").strip()
    if not token:
        record("FinMind", "SKIP", "No token in env", ok=False)
        return

    base = "https://api.finmindtrade.com/api/v4/data"
    headers = {"Authorization": f"Bearer {token}"}

    # Test 1: TaiwanStockPrice (single stock)
    url = f"{base}?dataset=TaiwanStockPrice&stock_id=2330&start_date=20250101&end_date=20250131&token={token}"
    try:
        start = time.time()
        r = requests.get(url, headers=headers, timeout=30)
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {
            "msg": data.get("msg", ""),
            "data_count": len(data.get("data", [])),
        }
        if data.get("data"):
            first = data["data"][0]
            details["columns"] = list(first.keys())
            details["sample"] = first
            # Check date format
            if "date" in first:
                details["date_format"] = str(first["date"])

        record("FinMind: TaiwanStockPrice (2330)", status, details, ok)
    except Exception as e:
        record("FinMind: TaiwanStockPrice (2330)", f"ERROR: {e}", {}, ok=False)

    # Test 2: TaiwanStockInfo (all stocks)
    url = f"{base}?dataset=TaiwanStockInfo&token={token}"
    try:
        start = time.time()
        r = requests.get(url, headers=headers, timeout=30)
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {
            "msg": data.get("msg", ""),
            "data_count": len(data.get("data", [])),
        }
        if data.get("data"):
            details["columns"] = list(data["data"][0].keys())

        record("FinMind: TaiwanStockInfo", status, details, ok)
    except Exception as e:
        record("FinMind: TaiwanStockInfo", f"ERROR: {e}", {}, ok=False)

    # Test 3: Invalid token (error handling test)
    url = f"{base}?dataset=TaiwanStockPrice&stock_id=2330&token=invalid_token"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        record(
            "FinMind: Invalid token",
            f"HTTP {r.status_code}",
            {"msg": data.get("msg", "")},
            ok=(r.status_code == 200),
        )
    except Exception as e:
        record("FinMind: Invalid token", f"ERROR: {e}", {}, ok=False)

    # Test 4: Rate limit test (rapid fire)
    try:
        results_rl = []
        for i in range(5):
            start = time.time()
            r = requests.get(url.replace("invalid_token", token), headers=headers, timeout=10)
            elapsed = time.time() - start
            results_rl.append((r.status_code, elapsed))
        avg = sum(e for _, e in results_rl) / len(results_rl)
        record(
            "FinMind: Rate limit (5 rapid calls)",
            f"Avg {avg:.3f}s",
            {"results": results_rl},
            ok=True,
        )
    except Exception as e:
        record("FinMind: Rate limit", f"ERROR: {e}", {}, ok=False)


# ============================================================
# 2. TWSE API
# ============================================================
def test_twse():
    log.info("=" * 60)
    log.info("TESTING: TWSE API")
    log.info("=" * 60)

    # Test 1: After Trading (MI_INDEX)
    today = datetime.datetime.now()
    date_str = today.strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_str}&type=ALL&response=json"
    try:
        start = time.time()
        r = requests.get(url, timeout=15, verify=False)
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {
            "date_requested": date_str,
            "tables_count": len(data.get("tables", [])),
        }
        if data.get("tables"):
            first_table = data["tables"][0]
            details["table_title"] = first_table.get("title", "")
            details["fields"] = first_table.get("fields", [])
            details["data_rows"] = len(first_table.get("data", []))
            if first_table.get("data"):
                details["first_row_sample"] = first_table["data"][0][:5]

        record("TWSE: MI_INDEX (after trading)", status, details, ok)
    except Exception as e:
        record("TWSE: MI_INDEX", f"ERROR: {e}", {}, ok=False)

    # Test 2: ExRight (dividend)
    url = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U?response=json&startDate=20250101&endDate=20250131"
    try:
        start = time.time()
        r = requests.get(url, timeout=15, verify=False)
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {
            "data_count": len(data.get("data", [])),
        }
        if data.get("data"):
            details["first_row"] = data["data"][0]

        record("TWSE: TWT49U (dividend)", status, details, ok)
    except Exception as e:
        record("TWSE: TWT49U", f"ERROR: {e}", {}, ok=False)

    # Test 3: Institutional Investors (T86)
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"
    try:
        start = time.time()
        r = requests.get(url, timeout=15, verify=False)
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {
            "data_count": len(data.get("data", [])),
            "fields": data.get("fields", []),
        }
        if data.get("data"):
            details["first_row_sample"] = data["data"][0][:5]

        record("TWSE: T86 (institutional)", status, details, ok)
    except Exception as e:
        record("TWSE: T86", f"ERROR: {e}", {}, ok=False)

    # Test 4: QFIIS (foreign ownership)
    url = f"https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date={date_str}&selectType=ALLBUT0999&response=json"
    try:
        start = time.time()
        r = requests.get(url, timeout=15, verify=False)
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {
            "data_count": len(data.get("data", [])),
        }
        if data.get("data"):
            details["first_row_sample"] = data["data"][0][:5]

        record("TWSE: MI_QFIIS (foreign)", status, details, ok)
    except Exception as e:
        record("TWSE: MI_QFIIS", f"ERROR: {e}", {}, ok=False)


# ============================================================
# 3. TPEx API
# ============================================================
def test_tpex():
    log.info("=" * 60)
    log.info("TESTING: TPEx API")
    log.info("=" * 60)

    today = datetime.datetime.now()
    roc_year = today.year - 1911
    roc_date = f"{roc_year}/{today.month:02d}/{today.day:02d}"

    # Test 1: OTC Quotes (stk_wn1430)
    url = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php"
    params = {"l": "zh-tw", "d": roc_date, "se": "AL", "s": "0,asc,0"}
    try:
        start = time.time()
        r = requests.get(url, params=params, timeout=15, verify=False)
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {}
        if data.get("aaData"):
            details["data_count"] = len(data["aaData"])
            details["first_row_sample"] = data["aaData"][0][:5] if data["aaData"] else "empty"
        if data.get("tables"):
            details["tables_count"] = len(data["tables"])
            if data["tables"]:
                details["table_title"] = data["tables"][0].get("title", "")
                details["fields"] = data["tables"][0].get("fields", [])

        record("TPEx: stk_wn1430 (quotes)", status, details, ok)
    except Exception as e:
        record("TPEx: stk_wn1430", f"ERROR: {e}", {}, ok=False)

    # Test 2: Institutional (3itrade_hedge_result)
    url = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
    params = {"l": "zh-tw", "o": "json", "se": "AL", "t": "D", "d": roc_date}
    try:
        start = time.time()
        r = requests.get(url, params=params, timeout=15, verify=False)
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {}
        if data.get("aaData"):
            details["data_count"] = len(data["aaData"])
            details["first_row_sample"] = data["aaData"][0][:5] if data["aaData"] else "empty"

        record("TPEx: 3itrade_hedge (institutional)", status, details, ok)
    except Exception as e:
        record("TPEx: 3itrade_hedge", f"ERROR: {e}", {}, ok=False)

    # Test 3: Dividend (exDailyQ)
    roc_start = f"{roc_year}/01/01"
    roc_end = roc_date
    url = "https://www.tpex.org.tw/web/stock/exright/dailyquo/exDailyQ_result.php"
    params = {"l": "zh-tw", "d": roc_start, "ed": roc_end, "se": "EW", "s": "0,asc,0"}
    try:
        start = time.time()
        r = requests.get(url, params=params, timeout=15, verify=False)
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {}
        tables = data.get("tables", [])
        if tables and tables[0].get("data"):
            details["data_count"] = len(tables[0]["data"])
            details["fields"] = tables[0].get("fields", [])

        record("TPEx: exDailyQ (dividend)", status, details, ok)
    except Exception as e:
        record("TPEx: exDailyQ", f"ERROR: {e}", {}, ok=False)


# ============================================================
# 4. TDCC API
# ============================================================
def test_tdcc():
    log.info("=" * 60)
    log.info("TESTING: TDCC API")
    log.info("=" * 60)

    # Test 1: OpenAPI (weekly data)
    today = datetime.datetime.now()
    days_to_subtract = (today.weekday() - 5) % 7
    latest_sat = today - datetime.timedelta(days=days_to_subtract)
    date_str = latest_sat.strftime("%Y-%m-%d")

    url = f"https://openapi.tdcc.com.tw/v1/opendata/1-5?date={date_str}"
    try:
        start = time.time()
        r = requests.get(url, timeout=30)
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {
            "date_requested": date_str,
            "record_count": len(data) if isinstance(data, list) else "N/A",
        }
        if isinstance(data, list) and data:
            details["first_record_sample"] = data[0]

        record("TDCC: OpenAPI 1-5", status, details, ok)
    except Exception as e:
        record("TDCC: OpenAPI 1-5", f"ERROR: {e}", {}, ok=False)

    # Test 2: Invalid date
    url = "https://openapi.tdcc.com.tw/v1/opendata/1-5?date=2020-01-01"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        record(
            "TDCC: Invalid date",
            f"HTTP {r.status_code}",
            {"response": str(data)[:200]},
            ok=(r.status_code == 200),
        )
    except Exception as e:
        record("TDCC: Invalid date", f"ERROR: {e}", {}, ok=False)


# ============================================================
# 5. LongCat AI API
# ============================================================
def test_longcat():
    log.info("=" * 60)
    log.info("TESTING: LongCat AI API")
    log.info("=" * 60)

    api_key = os.environ.get("LONGCAT_API_KEY", "").strip()
    if not api_key:
        record("LongCat", "SKIP", "No API key", ok=False)
        return

    api_url = os.environ.get("LONGCAT_API_URL", "https://api.longcat.chat/openai")
    model = os.environ.get("LONGCAT_MODEL", "LongCat-2.0-Preview")

    # Test 1: Simple chat completion
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in 5 words."},
        ],
        "temperature": 0.7,
        "max_tokens": 100,
    }
    try:
        start = time.time()
        r = requests.post(
            f"{api_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=60,
        )
        elapsed = time.time() - start
        data = r.json()

        status = f"HTTP {r.status_code}, {elapsed:.2f}s"
        ok = r.status_code == 200

        details = {
            "model": data.get("model", ""),
            "choices_count": len(data.get("choices", [])),
        }
        if data.get("choices"):
            first_choice = data["choices"][0]
            details["role"] = first_choice.get("message", {}).get("role", "")
            msg = first_choice.get("message", {}).get("content", "")
            details["response_preview"] = msg[:100] if msg else ""
        details["usage"] = data.get("usage", {})

        record("LongCat: Chat Completion", status, details, ok)
    except Exception as e:
        record("LongCat: Chat Completion", f"ERROR: {e}", {}, ok=False)

    # Test 2: Error handling (bad model)
    payload_bad = {
        "model": "nonexistent-model",
        "messages": [{"role": "user", "content": "test"}],
    }
    try:
        r = requests.post(
            f"{api_url}/chat/completions",
            json=payload_bad,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=10,
        )
        data = r.json()
        record(
            "LongCat: Bad model error",
            f"HTTP {r.status_code}",
            {"error": str(data)[:200]},
            ok=(r.status_code == 200),
        )
    except Exception as e:
        record("LongCat: Bad model error", f"ERROR: {e}", {}, ok=False)


# ============================================================
# 6. Kronos API (HuggingFace model inference)
# ============================================================
def test_kronos():
    log.info("=" * 60)
    log.info("TESTING: Kronos API")
    log.info("=" * 60)

    model_id = os.environ.get("KRONOS_MODEL_ID", "NeoQuasar/Kronos-base")
    tokenizer_id = os.environ.get("KRONOS_TOKENIZER_ID", "NeoQuasar/Kronos-Tokenizer-base")

    # Test 1: Check if model exists on HuggingFace
    try:
        from huggingface_hub import model_info

        info = model_info(model_id)
        details = {
            "model_id": model_id,
            "tags": info.tags if hasattr(info, "tags") else "N/A",
            "downloads": info.downloads if hasattr(info, "downloads") else "N/A",
        }
        record("Kronos: Model exists (HuggingFace)", f"Model: {model_id}", details, ok=True)
    except Exception as e:
        record("Kronos: Model exists (HuggingFace)", f"ERROR: {e}", {}, ok=False)

    # Test 2: Check tokenizer
    try:
        from huggingface_hub import model_info

        info = model_info(tokenizer_id)
        details = {
            "tokenizer_id": tokenizer_id,
            "downloads": info.downloads if hasattr(info, "downloads") else "N/A",
        }
        record("Kronos: Tokenizer exists", f"Tokenizer: {tokenizer_id}", details, ok=True)
    except Exception as e:
        record("Kronos: Tokenizer exists", f"ERROR: {e}", {}, ok=False)

    # Test 3: Try loading the model (if torch available)
    try:
        import torch
        from kronos import Kronos, KronosTokenizer

        tokenizer = KronosTokenizer.from_pretrained(tokenizer_id)
        model = Kronos.from_pretrained(model_id)
        model.eval()

        # Create dummy input
        dummy_prices = [100.0 + i * 0.5 for i in range(100)]
        dummy_dates = [(datetime.datetime(2024, 1, i + 1)).strftime("%Y-%m-%d") for i in range(100)]

        inputs = tokenizer(
            prices=dummy_prices,
            dates=dummy_dates,
            return_tensors="pt",
        )

        start = time.time()
        with torch.no_grad():
            preds = model.generate(
                inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                max_length=105,
                num_return_sequences=1,
            )
        elapsed = time.time() - start

        decoded = tokenizer.batch_decode(preds, skip_special_tokens=True)
        details = {
            "inference_time": f"{elapsed:.2f}s",
            "output_sample": decoded[0][:100] if decoded else "none",
        }
        record("Kronos: Inference test", f"Success in {elapsed:.2f}s", details, ok=True)
    except ImportError:
        record("Kronos: Inference test", "SKIP", "torch not installed", ok=False)
    except Exception as e:
        record("Kronos: Inference test", f"ERROR: {e}", {}, ok=False)


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("TRINITY API TEST SUITE")
    print("=" * 60)

    test_finmind()
    test_twse()
    test_tpex()
    test_tdcc()
    test_longcat()
    test_kronos()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r["ok"])
    failed = total - passed
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")

    for r in RESULTS:
        icon = "✅" if r["ok"] else "❌"
        print(f"  {icon} {r['name']}: {r['status']}")

    # Save results
    with open("d:/twse/API_TEST_RESULTS.json", "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    print("\nResults saved to API_TEST_RESULTS.json")
