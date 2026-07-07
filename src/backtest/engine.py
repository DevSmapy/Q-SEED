"""백테스트 시뮬레이션 엔진."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.backtest.portfolio import (
    build_rebalance_positions,
    compute_benchmark_returns,
    compute_daily_stock_returns,
    select_rebalance_dates,
)
from src.backtest.strategy import BacktestStrategy
from src.factors.registry import get_factor


@dataclass(frozen=True)
class BacktestEngineResult:
    """백테스트 시뮬레이션 원시 결과."""

    strategy: BacktestStrategy
    daily_returns: pd.DataFrame
    positions: pd.DataFrame
    rebalance_dates: pd.DatetimeIndex


def run_backtest_engine(
    prices: pd.DataFrame,
    factor_values: pd.DataFrame,
    strategy: BacktestStrategy,
) -> BacktestEngineResult:
    """팩터 전략 롱숏/롱온리 백테스트 시뮬레이션."""
    spec = get_factor(strategy.factor_name)
    rebalance_dates = select_rebalance_dates(
        factor_values,
        rebalance_freq=strategy.rebalance_freq,
        min_observations=strategy.min_observations,
    )
    positions = build_rebalance_positions(
        factor_values,
        strategy,
        spec,
        rebalance_dates,
    )
    daily_stock_returns = compute_daily_stock_returns(prices)
    strategy_returns = _simulate_strategy_returns(
        positions,
        daily_stock_returns,
        rebalance_dates=rebalance_dates,
        transaction_cost_bps=strategy.transaction_cost_bps,
    )
    benchmark_returns = compute_benchmark_returns(
        prices,
        rebalance_dates,
        rebalance_freq=strategy.rebalance_freq,
    )

    daily = strategy_returns.to_frame("strategy_return")
    if not benchmark_returns.empty:
        daily = daily.join(benchmark_returns.to_frame("benchmark_return"), how="left")
    else:
        daily["benchmark_return"] = np.nan

    daily = daily.reset_index().rename(columns={"index": "Date"})
    daily["Date"] = pd.to_datetime(daily["Date"])
    daily = daily.sort_values("Date").reset_index(drop=True)

    equity = strategy.initial_capital * (1.0 + daily["strategy_return"].fillna(0.0)).cumprod()
    daily["equity"] = equity
    rolling_max = daily["equity"].cummax()
    daily["drawdown"] = daily["equity"] / rolling_max - 1.0

    return BacktestEngineResult(
        strategy=strategy,
        daily_returns=daily,
        positions=positions,
        rebalance_dates=rebalance_dates,
    )


def _simulate_strategy_returns(
    positions: pd.DataFrame,
    daily_stock_returns: pd.DataFrame,
    *,
    rebalance_dates: pd.DatetimeIndex,
    transaction_cost_bps: float,
) -> pd.Series:
    if positions.empty or rebalance_dates.empty:
        return pd.Series(dtype=float)

    rebalance_list = list(rebalance_dates)
    records: list[dict[str, object]] = []
    previous_weights: dict[str, float] = {}

    for period_idx, start_date in enumerate(rebalance_list):
        period_positions = positions.loc[positions["rebalance_date"] == start_date]
        if period_positions.empty:
            continue

        current_weights = _signed_weights(period_positions)
        turnover = _compute_turnover(previous_weights, current_weights)
        rebalance_cost = turnover * transaction_cost_bps / 10_000.0

        if period_idx + 1 < len(rebalance_list):
            end_date = rebalance_list[period_idx + 1]
            period_mask = (daily_stock_returns["Date"] > start_date) & (
                daily_stock_returns["Date"] <= end_date
            )
        else:
            period_mask = daily_stock_returns["Date"] > start_date

        period_returns = daily_stock_returns.loc[period_mask]
        if period_returns.empty:
            previous_weights = current_weights
            continue

        for trade_date, day_group in period_returns.groupby("Date", sort=True):
            day_return = _portfolio_return_for_day(period_positions, day_group)
            if trade_date == period_returns["Date"].min() and rebalance_cost > 0:
                day_return -= rebalance_cost
            records.append({"Date": trade_date, "strategy_return": day_return})

        previous_weights = current_weights

    if not records:
        return pd.Series(dtype=float)

    result = pd.DataFrame(records).drop_duplicates(subset=["Date"], keep="last")
    return result.set_index("Date")["strategy_return"].sort_index()


def _signed_weights(positions: pd.DataFrame) -> dict[str, float]:
    weights: dict[str, float] = {}
    for _, row in positions.iterrows():
        ticker = str(row["Ticker"])
        side = str(row["side"])
        weight = float(row["weight"])
        signed = weight if side == "long" else -weight
        weights[ticker] = weights.get(ticker, 0.0) + signed
    return weights


def _compute_turnover(
    previous_weights: dict[str, float],
    current_weights: dict[str, float],
) -> float:
    tickers = set(previous_weights) | set(current_weights)
    return sum(
        abs(current_weights.get(ticker, 0.0) - previous_weights.get(ticker, 0.0))
        for ticker in tickers
    )


def _portfolio_return_for_day(
    positions: pd.DataFrame,
    day_returns: pd.DataFrame,
) -> float:
    merged = positions.merge(day_returns, on="Ticker", how="inner")
    if merged.empty:
        return 0.0

    long_ret = merged.loc[merged["side"] == "long", "daily_return"]
    short_ret = merged.loc[merged["side"] == "short", "daily_return"]

    long_component = float((merged.loc[merged["side"] == "long", "weight"] * long_ret).sum())
    short_component = float((merged.loc[merged["side"] == "short", "weight"] * short_ret).sum())
    return long_component - short_component
