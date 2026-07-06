"""Information Coefficient (IC) 분석."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

MIN_IC_GROUP_SIZE = 5
MIN_UNIQUE_VALUES = 2


@dataclass(frozen=True)
class ICResult:
    """IC 분석 결과."""

    factor_name: str
    forward_horizon: int
    daily_ic: pd.DataFrame
    summary: pd.DataFrame


def _cross_sectional_ic(group: pd.DataFrame) -> float:
    if len(group) < MIN_IC_GROUP_SIZE:
        return np.nan
    if (
        group["factor_value"].nunique() < MIN_UNIQUE_VALUES
        or group["forward_return"].nunique() < MIN_UNIQUE_VALUES
    ):
        return np.nan
    correlation = spearmanr(group["factor_value"], group["forward_return"]).correlation
    if correlation is None or np.isnan(correlation):
        return np.nan
    return float(correlation)


def compute_forward_returns(
    prices: pd.DataFrame,
    horizon: int = 21,
) -> pd.DataFrame:
    """티커별 선행 수익률 계산."""
    frame = prices[["Date", "Ticker", "Close"]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.sort_values(["Ticker", "Date"])
    grouped = frame.groupby("Ticker", sort=False)["Close"]
    frame["forward_return"] = grouped.shift(-horizon) / frame["Close"] - 1.0
    frame["forward_return"] = frame["forward_return"].replace([np.inf, -np.inf], np.nan)
    return frame[["Date", "Ticker", "forward_return"]].dropna(subset=["forward_return"])


def compute_ic(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    *,
    factor_name: str,
    forward_horizon: int = 21,
    min_observations: int = 30,
) -> ICResult:
    """날짜별 단면 Spearman IC 계산."""
    merged = factor_values.merge(forward_returns, on=["Date", "Ticker"], how="inner")
    merged["Date"] = pd.to_datetime(merged["Date"])

    counts = merged.groupby("Date", sort=True).size()
    valid_dates = counts[counts >= min_observations].index
    merged = merged[merged["Date"].isin(valid_dates)]

    ic_records: list[dict[str, object]] = []
    for date, group in merged.groupby("Date", sort=True):
        ic_value = _cross_sectional_ic(group)
        if not np.isnan(ic_value):
            ic_records.append({"Date": date, "ic": ic_value})
    daily_ic = pd.DataFrame(ic_records)

    ic_mean = float(daily_ic["ic"].mean()) if not daily_ic.empty else np.nan
    ic_std = float(daily_ic["ic"].std(ddof=1)) if len(daily_ic) > 1 else np.nan
    ic_ir = ic_mean / ic_std if ic_std not in (0.0, np.nan) and not np.isnan(ic_std) else np.nan
    hit_rate = float((daily_ic["ic"] > 0).mean()) if not daily_ic.empty else np.nan

    summary = pd.DataFrame(
        [
            {
                "factor_name": factor_name,
                "forward_horizon": forward_horizon,
                "ic_mean": ic_mean,
                "ic_std": ic_std,
                "ic_ir": ic_ir,
                "hit_rate": hit_rate,
                "observation_days": len(daily_ic),
            }
        ]
    )

    return ICResult(
        factor_name=factor_name,
        forward_horizon=forward_horizon,
        daily_ic=daily_ic,
        summary=summary,
    )
