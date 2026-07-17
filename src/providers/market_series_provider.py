"""시장 지표 시리즈 스펙 레지스트리."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SeriesBackend = Literal["fdr", "yfinance", "yfinance_spread"]


@dataclass(frozen=True, slots=True)
class MarketSeriesSpec:
    """외부 시장 지표 시리즈 정의."""

    series_id: str
    name: str
    category: str
    backend: SeriesBackend
    symbol: str
    # multi-column FDR frames: substring used to pick the value column
    value_column: str | None = None


# 1차 구현 대상만. Put/Call · Fear&Greed · 신용융자는 후속.
MARKET_SERIES_SPECS: tuple[MarketSeriesSpec, ...] = (
    MarketSeriesSpec(
        series_id="vix",
        name="VIX",
        category="sentiment_volatility",
        backend="fdr",
        symbol="VIX",
    ),
    MarketSeriesSpec(
        series_id="dxy",
        name="US Dollar Index",
        category="liquidity_macro",
        backend="yfinance",
        symbol="DX-Y.NYB",
    ),
    MarketSeriesSpec(
        series_id="us_t10y2y",
        name="US 10Y-2Y Treasury Yield Spread",
        category="liquidity_macro",
        backend="yfinance_spread",
        # high|low — 심볼 실패 시 파이프라인이 해당 시리즈만 스킵
        symbol="^TNX|2YY=F",
    ),
    MarketSeriesSpec(
        series_id="kr_investor_deposit",
        name="KR Investor Deposit",
        category="liquidity_macro",
        backend="fdr",
        symbol="ECOS/SNAP/532",
        value_column="예탁금",
    ),
)


def get_series_specs() -> tuple[MarketSeriesSpec, ...]:
    """등록된 시리즈 스펙 반환."""
    return MARKET_SERIES_SPECS
