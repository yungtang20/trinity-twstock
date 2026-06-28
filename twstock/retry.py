# -*- coding: utf-8 -*-
"""
retry.py — 統一的 HTTP GET 重試包裝器

所有官方 API Fetcher 都應使用此模組的 retry_get() 替代直接 requests.get()，
以確保網路暫時故障時能自動重試。
"""
import time
import logging
import requests

logger = logging.getLogger(__name__)


def retry_get(
    url: str,
    *,
    params: dict = None,
    timeout: int = 10,
    retries: int = 3,
    backoff: float = 1.0,
    verify: bool = True,
    headers: dict = None,
) -> requests.Response | None:
    """
    帶重試機制的 requests.get() 包裝器。

    Args:
        url: 目標 URL
        params: 查詢參數
        timeout: 每次請求的 timeout（秒）
        retries: 最大重試次數（不含首次）
        backoff: 初始退避時間（秒），每次重試翻倍
        verify: SSL 驗證（預設 True）
        headers: 額外請求頭

    Returns:
        requests.Response 或 None（所有重試都失敗）
    """
    last_err = None
    for attempt in range(1 + retries):
        try:
            resp = requests.get(
                url,
                params=params,
                timeout=timeout,
                verify=verify,
                headers=headers,
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            last_err = e
            logger.warning(
                "HTTP error on attempt %d/%d for %s: %s",
                attempt + 1, 1 + retries, url, e,
            )
        except requests.exceptions.RequestException as e:
            last_err = e
            logger.warning(
                "Request error on attempt %d/%d for %s: %s",
                attempt + 1, 1 + retries, url, e,
            )

        if attempt < retries:
            sleep_time = backoff * (2 ** attempt)
            logger.info("Retrying in %.1fs...", sleep_time)
            time.sleep(sleep_time)

    logger.error("All %d attempts failed for %s: %s", 1 + retries, url, last_err)
    return None
