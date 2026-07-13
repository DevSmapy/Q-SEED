"""리밸런싱일 포트폴리오 구성."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.strategy import BacktestStrategy, resolve_quintiles
from src.factors.base import FactorSpec

QUINTILE_COUNT = 5


def assign_quintiles(factor_values: pd.DataFrame) -> pd.DataFrame:
    """날짜별 팩터값 분위수 부여."""
    frame = factor_values.copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame["quintile"] = frame.groupby("Date", sort=True)["factor_value"].transform(
        lambda values: pd.qcut(
            values.rank(method="first"),
            QUINTILE_COUNT,
            labels=[1, 2, 3, 4, 5],
        ).astype(int)
    )
    return frame


def select_rebalance_dates(
    factor_values: pd.DataFrame,
    *,
    rebalance_freq: int,
    min_observations: int,
) -> pd.DatetimeIndex:
    """최소 종목 수를 만족하는 거래일 중 리밸런싱일을 선택."""
    frame = factor_values.copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    counts = frame.groupby("Date", sort=True).size()
    eligible = counts[counts >= min_observations].index.sort_values()
    if len(eligible) == 0:
        return pd.DatetimeIndex([])
    return pd.DatetimeIndex(eligible[::rebalance_freq])


def build_rebalance_positions(
    factor_values: pd.DataFrame,
    strategy: BacktestStrategy,
    spec: FactorSpec,
    rebalance_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """리밸런싱일별 롱·숏 포지션(동일가중) 생성."""
    long_q, short_q = resolve_quintiles(strategy, spec)
    quintiled = assign_quintiles(factor_values)
    quintiled = quintiled[quintiled["Date"].isin(rebalance_dates)].copy()

    records: list[dict[str, object]] = []
    for rebalance_date, group in quintiled.groupby("Date", sort=True):
        long_tickers = group.loc[group["quintile"] == long_q, "Ticker"]
        if short_q is not None:
            short_tickers = group.loc[group["quintile"] == short_q, "Ticker"]
        else:
            short_tickers = pd.Series(dtype=str)

        long_count = len(long_tickers)
        short_count = len(short_tickers)
        if long_count == 0:
            continue
        if strategy.position_mode == "long_short" and short_count == 0:
            continue

        if strategy.position_mode == "long_short":
            long_weight = 0.5 / long_count
            short_weight = 0.5 / short_count
        else:
            long_weight = 1.0 / long_count
            short_weight = 0.0

        for ticker in long_tickers:
            records.append(
                {
                    "rebalance_date": rebalance_date,
                    "Ticker": ticker,
                    "side": "long",
                    "weight": long_weight,
                }
            )
        if strategy.position_mode == "long_short":
            for ticker in short_tickers:
                records.append(
                    {
                        "rebalance_date": rebalance_date,
                        "Ticker": ticker,
                        "side": "short",
                        "weight": short_weight,
                    }
                )

    if not records:
        return pd.DataFrame(
            columns=["rebalance_date", "Ticker", "side", "weight"],
        )
    return pd.DataFrame(records)


def compute_daily_stock_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """티커별 일간 수익률."""
    frame = prices[["Date", "Ticker", "Close"]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.sort_values(["Ticker", "Date"])
    grouped = frame.groupby("Ticker", sort=False)["Close"]
    frame["daily_return"] = grouped.pct_change()
    frame["daily_return"] = frame["daily_return"].replace([np.inf, -np.inf], np.nan)
    return frame[["Date", "Ticker", "daily_return"]].dropna(subset=["daily_return"])


def compute_benchmark_returns(
    prices: pd.DataFrame,
    rebalance_dates: pd.DatetimeIndex,
    *,
    rebalance_freq: int,
) -> pd.Series:
    """동일 시장 유니버스 동일가중 벤치마크 일간 수익률."""
    daily_returns = compute_daily_stock_returns(prices)
    if rebalance_dates.empty:
        return pd.Series(dtype=float)

    sorted_dates = pd.DatetimeIndex(daily_returns["Date"].drop_duplicates().sort_values())

    records: list[dict[str, object]] = []
    rebalance_list = list(rebalance_dates)
    for period_idx, start_date in enumerate(rebalance_list):
        if period_idx + 1 < len(rebalance_list):
            end_date = rebalance_list[period_idx + 1]
            mask = (sorted_dates > start_date) & (sorted_dates <= end_date)
        else:
            mask = sorted_dates > start_date
        period_dates = sorted_dates[mask]
        if len(period_dates) == 0:
            continue

        for trade_date in period_dates:
            day_returns = daily_returns.loc[daily_returns["Date"] == trade_date, "daily_return"]
            if day_returns.empty:
                continue
            records.append(
                {
                    "Date": trade_date,
                    "benchmark_return": float(day_returns.mean()),
                }
            )

    if not records:
        return pd.Series(dtype=float)

    benchmark_frame = pd.DataFrame(records).drop_duplicates(subset=["Date"], keep="last")
    benchmark_series = pd.Series(
        benchmark_frame["benchmark_return"].to_numpy(),
        index=pd.DatetimeIndex(benchmark_frame["Date"]),
        dtype=float,
    )
    return benchmark_series.sort_index()
