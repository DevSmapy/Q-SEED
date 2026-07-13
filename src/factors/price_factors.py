"""OHLCV 기반 가격·거래량 팩터 계산."""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = frozenset({"Date", "Ticker", "Market", "Open", "High", "Low", "Close", "Volume"})


def _validate_prices(prices: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(prices.columns)
    if missing:
        msg = f"필수 컬럼이 없습니다: {sorted(missing)}"
        raise ValueError(msg)
    frame = prices.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    return frame.sort_values(["Ticker", "Date"]).reset_index(drop=True)


def _factor_frame(
    prices: pd.DataFrame,
    factor_value: pd.Series,
) -> pd.DataFrame:
    result = prices[["Date", "Ticker", "Market"]].copy()
    cleaned = factor_value.replace([np.inf, -np.inf], np.nan)
    result["factor_value"] = cleaned
    return result.dropna(subset=["factor_value"])


def compute_momentum_12_1(prices: pd.DataFrame) -> pd.DataFrame:
    """12개월 수익률에서 최근 1개월을 제외한 모멘텀 (약 252일·21일)."""
    frame = _validate_prices(prices)
    grouped = frame.groupby("Ticker", sort=False)["Close"]
    lag_21 = grouped.shift(21)
    lag_252 = grouped.shift(252)
    momentum = lag_21 / lag_252 - 1.0
    return _factor_frame(frame, momentum)


def compute_momentum_6m(prices: pd.DataFrame) -> pd.DataFrame:
    """6개월(약 126거래일) 모멘텀."""
    frame = _validate_prices(prices)
    close = frame["Close"]
    lag_126 = frame.groupby("Ticker", sort=False)["Close"].shift(126)
    momentum = close / lag_126 - 1.0
    return _factor_frame(frame, momentum)


def compute_reversal_5d(prices: pd.DataFrame) -> pd.DataFrame:
    """5일 단기 반전 팩터 (최근 5일 수익률의 음수)."""
    frame = _validate_prices(prices)
    close = frame["Close"]
    lag_5 = frame.groupby("Ticker", sort=False)["Close"].shift(5)
    reversal = -(close / lag_5 - 1.0)
    return _factor_frame(frame, reversal)


def compute_volatility_60d(prices: pd.DataFrame) -> pd.DataFrame:
    """60일 일간 수익률 표준편차 (변동성)."""
    frame = _validate_prices(prices)
    daily_return = frame.groupby("Ticker", sort=False)["Close"].pct_change()
    volatility = daily_return.groupby(frame["Ticker"], sort=False).transform(
        lambda series: series.rolling(60, min_periods=40).std()
    )
    return _factor_frame(frame, volatility)


def compute_volume_ratio_20d(prices: pd.DataFrame) -> pd.DataFrame:
    """20일 평균 거래량 대비 당일 거래량 비율."""
    frame = _validate_prices(prices)
    volume = frame["Volume"].astype(float)
    avg_volume = volume.groupby(frame["Ticker"], sort=False).transform(
        lambda series: series.rolling(20, min_periods=15).mean()
    )
    ratio = volume / avg_volume
    return _factor_frame(frame, ratio)


def compute_log_dollar_volume(prices: pd.DataFrame) -> pd.DataFrame:
    """로그 달러 거래대금(종가×거래량) — 유동성·규모 프록시."""
    frame = _validate_prices(prices)
    dollar_volume = pd.Series(
        np.log1p(frame["Close"].astype(float) * frame["Volume"].astype(float)),
        index=frame.index,
    )
    return _factor_frame(frame, dollar_volume)
