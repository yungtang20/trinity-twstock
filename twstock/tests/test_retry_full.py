# -*- coding: utf-8 -*-
"""test_retry_full.py — retry.py 完整覆蓋率測試。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from twstock.retry import retry_get


class TestRetryGet:
    """retry_get 帶重試的 HTTP GET。"""

    @patch("twstock.retry.requests.get")
    def test_success_first_try(self, mock_get):
        """首次成功即回傳 response。"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = retry_get("http://example.com")
        assert result is mock_response
        assert mock_get.call_count == 1

    @patch("twstock.retry.requests.get")
    def test_success_after_retries(self, mock_get):
        """重試後成功。"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.side_effect = [
            __import__("requests").exceptions.HTTPError("500"),
            mock_response,
        ]

        result = retry_get("http://example.com", retries=2)
        assert result is mock_response
        assert mock_get.call_count == 2

    @patch("twstock.retry.requests.get")
    def test_all_retries_exhausted(self, mock_get):
        """所有重試失敗回傳 None。"""
        mock_get.side_effect = __import__("requests").exceptions.HTTPError("500")

        result = retry_get("http://example.com", retries=2)
        assert result is None
        assert mock_get.call_count == 3  # 1 + 2 retries

    @patch("twstock.retry.requests.get")
    def test_request_exception(self, mock_get):
        """RequestException 也觸發重試。"""
        mock_get.side_effect = __import__("requests").exceptions.Timeout("timeout")

        result = retry_get("http://example.com", retries=1)
        assert result is None

    @patch("twstock.retry.requests.get")
    def test_custom_verify(self, mock_get):
        """verify 參數應傳遞。"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        retry_get("http://example.com", verify=True)
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("verify") is True

    @patch("twstock.retry.requests.get")
    def test_custom_headers(self, mock_get):
        """headers 參數應傳遞。"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        retry_get("http://example.com", headers={"User-Agent": "test"})
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("headers") == {"User-Agent": "test"}

    @patch("twstock.retry.requests.get")
    def test_custom_timeout(self, mock_get):
        """timeout 參數應傳遞。"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        retry_get("http://example.com", timeout=10)
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("timeout") == 10

    @patch("twstock.retry.requests.get")
    def test_params_passed(self, mock_get):
        """params 參數應傳遞。"""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        retry_get("http://example.com", params={"key": "value"})
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs.get("params") == {"key": "value"}
