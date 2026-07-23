# -*- coding: utf-8 -*-
"""Safe retry support for outbound HTTP GET requests.

TLS certificate validation is never disabled automatically.  A certificate
error is actionable configuration information, not a transient condition that
should be bypassed.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


def retry_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = 10,
    retries: int = 3,
    backoff: float = 1.0,
    verify: bool | str = True,
    headers: dict[str, str] | None = None,
    ssl_fallback: bool = False,
) -> requests.Response | None:
    """Return a successful GET response after bounded retries.

    ``ssl_fallback`` remains accepted for source compatibility with older
    callers, but it is deliberately ignored: falling back to ``verify=False``
    defeats TLS authentication and can expose tokens or market data to a
    man-in-the-middle attack.  Callers that explicitly pass ``verify=False``
    still retain that explicit requests-level choice; this helper never makes
    the choice on their behalf.
    """
    if retries < 0:
        raise ValueError("retries must be non-negative")
    if backoff < 0:
        raise ValueError("backoff must be non-negative")
    last_error: requests.RequestException | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=timeout,
                verify=verify,
                headers=headers,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.SSLError as exc:
            last_error = exc
            logger.warning(
                "TLS certificate/handshake error on attempt %d/%d for %s: %s",
                attempt + 1,
                retries + 1,
                url,
                exc,
            )
        except requests.exceptions.RequestException as exc:
            last_error = exc
            logger.warning(
                "Request error on attempt %d/%d for %s: %s",
                attempt + 1,
                retries + 1,
                url,
                exc,
            )

        if attempt < retries:
            delay = backoff * (2**attempt)
            logger.info("Retrying %s in %.1fs", url, delay)
            time.sleep(delay)

    # ponytail: ssl_fallback for known-broken remote certs (TPEx missing SKI).
    # Ceiling: disables TLS — only safe for public, no-auth data. Upgrade path
    # is the remote server fixing its certificate.
    if ssl_fallback and isinstance(last_error, requests.exceptions.SSLError):
        logger.warning("ssl_fallback enabled — retrying with verify=False for %s", url)
        try:
            response = requests.get(
                url,
                params=params,
                timeout=timeout,
                verify=False,
                headers=headers,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            last_error = exc
            logger.error("ssl_fallback also failed for %s: %s", url, exc)

    logger.error("All %d attempts failed for %s: %s", retries + 1, url, last_error)
    return None
