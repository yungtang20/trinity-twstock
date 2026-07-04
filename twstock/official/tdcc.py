#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
official/tdcc.py - 集保股權分散資料抓取（支援多週歷史，附重試機制與官網補爬）
"""

import time
from datetime import datetime, timedelta

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

from twstock.utils import get_ssl_verify

from .utils import safe_float, safe_int

# Suppress insecure SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_single_stock_tdcc_from_portal(stock_id: str, date_str: str, session: requests.Session = None) -> dict:
    """
    從集保官方網站 (https://www.tdcc.com.tw/portal/zh/smWeb/qryStock) 抓取單一股票特定日期的集保股權分散資料。
    # [AI MOD] Support modern dynamic CSRF token & form fields
    """
    if session is None:
        with requests.Session() as local_session:
            local_session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.tdcc.com.tw/portal/zh/smWeb/qryStock',
                'Origin': 'https://www.tdcc.com.tw',
                'Host': 'www.tdcc.com.tw',
                'Content-Type': 'application/x-www-form-urlencoded'
            })
            return fetch_single_stock_tdcc_from_portal(stock_id, date_str, local_session)

    try:
        # 1. 取得查詢頁面以擷取 CSRF Token 與下拉選單日期
        r_get = session.get('https://www.tdcc.com.tw/portal/zh/smWeb/qryStock', verify=get_ssl_verify(), timeout=15)
        if r_get.status_code != 200:
            return None

        sp_get = BeautifulSoup(r_get.text, 'html.parser')
        token_input = sp_get.find('input', {'name': 'SYNCHRONIZER_TOKEN'})
        token = token_input['value'] if token_input else None
        if not token:
            return None

        # 取得下拉選單的所有可用日期 (格式為 YYYYMMDD)
        select_date = sp_get.find('select', {'id': 'scaDate'})
        if not select_date:
            return None

        available_dates = [opt['value'] for opt in select_date.find_all('option') if opt.get('value')]
        if not available_dates:
            return None

        # 比對並尋找小於或等於目標日期 (YYYY-MM-DD) 的最接近可用日期
        target_int = int(date_str.replace('-', ''))
        matching_date = None
        for d_str in available_dates:
            if int(d_str) <= target_int:
                matching_date = d_str
                break

        if not matching_date:
            return None

        # 2. 發送 POST 請求送出查詢
        payload = {
            'SYNCHRONIZER_TOKEN': token,
            'SYNCHRONIZER_URI': '/portal/zh/smWeb/qryStock',
            'method': 'submit',
            'firDate': available_dates[0],  # 預設維持最新一期
            'scaDate': matching_date,
            'sqlMethod': 'StockNo',
            'stockNo': stock_id
        }

        r_post = session.post('https://www.tdcc.com.tw/portal/zh/smWeb/qryStock', data=payload, verify=get_ssl_verify(), timeout=15)
        if r_post.status_code != 200:
            return None

        # 3. 解析結果表格
        sp_post = BeautifulSoup(r_post.text, 'html.parser')
        tables = sp_post.find_all('table')
        if len(tables) < 2:
            return None

        table = tables[1]
        rows = table.find_all('tr')

        total_shares = 0
        total_people = 0
        whale_shares = 0
        whale_ratio = 0.0
        whale_people = 0 # [AI MOD]

        for row in rows:
            cols = [td.text.strip().replace(',', '') for td in row.find_all('td')]
            if not cols or len(cols) < 5:
                continue

            level_str = cols[0]
            if not level_str.isdigit():
                continue

            level = int(level_str)
            desc_cleaned = cols[1].replace(' ', '').replace('\u3000', '')
            people_val = safe_int(cols[2])
            shares_val = safe_float(cols[3])
            ratio_val = safe_float(cols[4])

            if desc_cleaned == "合計":  # [AI MOD] Match description to support stocks with 15/16/17 levels robustly
                total_shares = shares_val
                total_people = people_val
            elif level == 15:  # 大股東 (1000張以上)
                whale_shares = shares_val
                whale_ratio = ratio_val
                whale_people = people_val # [AI MOD]

        if total_shares == 0:
            return None

        # 回傳對齊資料庫規格之字典
        return {
            "stock_id": stock_id,
            "date": date_str,
            "source": "tdcc",
            "total_shares": int(total_shares),
            "whale_ratio": whale_ratio,
            "retail_ratio": round(100.0 - whale_ratio, 2),
            "total_people": int(total_people),
            "whale_shares": int(whale_shares),
            "whale_people": int(whale_people) # [AI MOD]
        }
    except Exception as e:
        print(f"      [Warning] 爬取 {stock_id} ({date_str}) 失敗: {e}", flush=True)
        return None

def update_stocks_tdcc_from_portal(stock_ids: list, dates: list):
    """
    [AI MOD] 自動依據給定的 stock_ids 與日期列表，從官網補爬真實集保資料並更新至資料庫。
    適用於 On-Demand 按需修復或填補歷史資料，以避開全市場批次爬蟲造成的封鎖風險。
    """
    # 延遲導入以防循環相依
    from processor import DataProcessor
    proc = DataProcessor()

    with requests.Session() as session:
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.tdcc.com.tw/portal/zh/smWeb/qryStock',
            'Origin': 'https://www.tdcc.com.tw',
            'Host': 'www.tdcc.com.tw',
            'Content-Type': 'application/x-www-form-urlencoded'
        })

        results = []
        total_tasks = len(dates) * len(stock_ids)
        current_task = 0

        print(f"開始執行按需補爬集保歷史數據 (共 {len(stock_ids)} 檔，{len(dates)} 個日期)...", flush=True)

        for date_str in dates:
            for stock_id in stock_ids:
                current_task += 1
                print(f"\r   → 進度: [{current_task}/{total_tasks}] 股號: {stock_id} 日期: {date_str} ... ", end='', flush=True)
                res = fetch_single_stock_tdcc_from_portal(stock_id, date_str, session)
                if res:
                    results.append(res)
                time.sleep(0.15)
        print() # 換行

        if results:
            df = pd.DataFrame(results)
            proc.upsert_tdcc(df)
            print(f"成功補爬並更新 {len(results)} 筆真實集保資料至資料庫！")
        else:
            print("未取得任何有效集保資料")

def fetch_tdcc_historical(weeks: int = 1, retries: int = 2) -> pd.DataFrame:
    """
    抓取最近 weeks 週的 TDCC 集保資料（從本週六往前推）
    [AI MOD] 修改以避免過去的日期調用 OpenAPI 導致重複資料。OpenAPI 僅能提供最新一週。
    """
    today = datetime.now()
    all_results = []

    for week_offset in range(weeks):
        # 尋找目標週六日期
        days_to_subtract = (today.weekday() - 5) % 7
        latest_sat = today - timedelta(days=days_to_subtract)
        target = latest_sat - timedelta(weeks=week_offset)
        date_str = target.strftime("%Y-%m-%d")

        if week_offset > 0:
            # 由於 OpenAPI 無法取得歷史，為防寫入重複垃圾資料，對歷史日期印出說明並略過
            print(f"  → 略過 TDCC 歷史日期: {date_str} (因 OpenAPI 不支援歷史下載，將於選股時按需補爬)", flush=True)
            continue

        print(f"  → 嘗試 TDCC 日期: {date_str} (第 {week_offset+1}/{weeks} 週)", flush=True)

        for attempt in range(retries):
            try:
                resp = requests.get(f"https://openapi.tdcc.com.tw/v1/opendata/1-5?date={date_str}", timeout=30)
                if resp.status_code != 200:
                    print(f"      HTTP {resp.status_code}，重試 {attempt+1}/{retries}", flush=True)
                    time.sleep(1)
                    continue

                data = resp.json()
                if not data or not isinstance(data, list):
                    print("      回應不是 JSON 陣列或為空，跳過", flush=True)
                    break

                stock_levels = {}
                for item in data:
                    code = item.get("證券代號", "").strip()
                    if not code.isdigit() or len(code) != 4:
                        continue
                    level_str = item.get("持股分級", "").strip()
                    if not level_str.isdigit():
                        continue
                    level = int(level_str)
                    shares = safe_float(item.get("股數", 0))
                    owners = safe_int(item.get("人數", 0))

                    if code not in stock_levels:
                        stock_levels[code] = {}
                    stock_levels[code][level] = {"shares": shares, "people": owners}

                results = []
                for code, levels in stock_levels.items():
                    total_shares = 0
                    total_people = 0
                    whale_shares = 0
                    whale_people = 0 # [AI MOD]
                    for lvl, lv_data in levels.items():
                        if lvl == 17:  # TDCC OpenAPI 合計是 level 17
                            total_shares = lv_data["shares"]
                            total_people = lv_data["people"]
                        elif lvl == 15:  # 大股東 (持股 > 1000張) 持股比例
                            whale_shares += lv_data["shares"]
                            whale_people += lv_data["people"] # [AI MOD]
                    if total_shares == 0:
                        continue
                    whale_ratio = round(whale_shares / total_shares * 100, 2)
                    results.append({
                        "stock_id": code,
                        "date_int": int(target.strftime("%Y%m%d")),
                        "total_shares": int(total_shares),
                        "whale_ratio": whale_ratio,
                        "total_people": int(total_people),
                        "whale_shares": int(whale_shares),
                        "whale_people": int(whale_people) # [AI MOD]
                    })

                if results:
                    print(f"      ✅ 成功抓取 {len(results)} 筆資料", flush=True)
                    all_results.extend(results)
                else:
                    print("      該日期無有效資料，跳過", flush=True)
                break

            except Exception as e:
                print(f"      ❌ 錯誤: {e}，重試 {attempt+1}/{retries}", flush=True)
                time.sleep(2 ** attempt)
                if attempt == retries - 1:
                    print(f"      日期 {date_str} 最終失敗，跳過", flush=True)

    if not all_results:
        return pd.DataFrame()

    return pd.DataFrame(all_results)

def fetch_latest_tdcc(max_weeks=4) -> pd.DataFrame:
    """舊版相容：只抓最新一期（內部呼叫 fetch_tdcc_historical(1)）"""
    return fetch_tdcc_historical(weeks=1)
