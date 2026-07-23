from types import SimpleNamespace
from unittest.mock import patch

from twstock.market_data.historical_fetcher import DataFetcher, _mis_exchange_prefix


class _Connection:
    def __init__(self, market):
        self._market = market

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        return self

    def fetchone(self):
        return (self._market,) if self._market is not None else None


@patch("twstock.market_data.historical_fetcher.get_connection")
def test_mis_exchange_prefix_uses_otc_metadata(mock_connection):
    mock_connection.return_value = _Connection("OTC")
    assert _mis_exchange_prefix("6488") == "otc"


@patch("twstock.market_data.historical_fetcher.get_connection")
def test_mis_exchange_prefix_falls_back_to_tse(mock_connection):
    mock_connection.return_value = _Connection(None)
    assert _mis_exchange_prefix("2330") == "tse"


@patch("twstock.market_data.historical_fetcher._mis_exchange_prefix", return_value="otc")
@patch("twstock.market_data.historical_fetcher.requests.get")
def test_intraday_snapshot_uses_otc_channel(mock_get, _market):
    mock_get.return_value = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {
            "msgArray": [
                {"o": "10", "h": "11", "l": "9", "z": "10.5", "v": "100"}
            ]
        },
    )

    snapshot = DataFetcher(token="test-token").fetch_intraday_snapshot("6488")

    assert mock_get.call_args.kwargs["params"]["ex_ch"] == "otc_6488.tw"
    assert snapshot["z"] == 10.5
