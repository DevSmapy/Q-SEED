"""StockProvider markets 필터 단위 테스트."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from src.providers.stock_provider import StockProvider


def test_get_all_tickers_markets_filter_calls_only_selected() -> None:
    provider = StockProvider()
    frames = {
        "KOSPI": pd.DataFrame({"Ticker": ["005930.KS"], "Market": ["KOSPI"]}),
        "NASDAQ": pd.DataFrame({"Ticker": ["AAPL"], "Market": ["NASDAQ"]}),
    }

    def fake_get(market: str, max_count: int | None = None) -> pd.DataFrame:
        return frames[market]

    with patch.object(provider, "get_market_tickers", side_effect=fake_get) as mocked:
        result = provider.get_all_tickers(markets=["KOSPI"])

    mocked.assert_called_once_with("KOSPI", max_count=None)
    assert result["Ticker"].tolist() == ["005930.KS"]


def test_get_all_tickers_rejects_unknown_market() -> None:
    provider = StockProvider()
    with pytest.raises(ValueError, match="지원하지 않는 시장"):
        provider.get_all_tickers(markets=["NOT_A_MARKET"])
