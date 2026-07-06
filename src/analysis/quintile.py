"""분위수(Quintile) 수익률 분석."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

QUINTILE_COUNT = 5
TOP_QUINTILE = 5
BOTTOM_QUINTILE = 1


@dataclass(frozen=True)
class QuintileResult:
    """분위수 분석 결과."""

    factor_name: str
    forward_horizon: int
    quintile_returns: pd.DataFrame
    spread_summary: pd.DataFrame


@dataclass(frozen=True)
class QuintileAnalysisConfig:
    """분위수 분석 설정."""

    factor_name: str
    forward_horizon: int = 21
    higher_is_better: bool = True
    min_observations: int = 30


def compute_quintile_returns(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    config: QuintileAnalysisConfig,
) -> QuintileResult:
    """팩터 분위수별 평균 선행 수익률과 롱숏 스프레드 계산."""
    factor_name = config.factor_name
    forward_horizon = config.forward_horizon
    higher_is_better = config.higher_is_better
    min_observations = config.min_observations
    merged = factor_values.merge(forward_returns, on=["Date", "Ticker"], how="inner")
    merged["Date"] = pd.to_datetime(merged["Date"])

    eligible_dates = (
        merged.groupby("Date", sort=True)
        .size()
        .loc[lambda counts: counts >= min_observations]
        .index
    )
    merged = merged[merged["Date"].isin(eligible_dates)].copy()
    merged["quintile"] = merged.groupby("Date", sort=True)["factor_value"].transform(
        lambda values: pd.qcut(
            values.rank(method="first"),
            QUINTILE_COUNT,
            labels=[1, 2, 3, 4, 5],
        ).astype(int)
    )

    quintile_returns = (
        merged.groupby(["Date", "quintile"], sort=True)["forward_return"]
        .mean()
        .reset_index()
        .rename(columns={"forward_return": "mean_forward_return"})
    )

    avg_by_quintile = (
        quintile_returns.groupby("quintile", sort=True)["mean_forward_return"]
        .mean()
        .reset_index()
        .rename(columns={"mean_forward_return": "avg_return"})
    )

    if avg_by_quintile.empty:
        spread = np.nan
    elif higher_is_better:
        spread = _quintile_spread(avg_by_quintile, TOP_QUINTILE, BOTTOM_QUINTILE)
    else:
        spread = _quintile_spread(avg_by_quintile, BOTTOM_QUINTILE, TOP_QUINTILE)

    spread_summary = pd.DataFrame(
        [
            {
                "factor_name": factor_name,
                "forward_horizon": forward_horizon,
                "long_short_spread": spread,
                "q1_avg_return": _quintile_avg(avg_by_quintile, 1),
                "q2_avg_return": _quintile_avg(avg_by_quintile, 2),
                "q3_avg_return": _quintile_avg(avg_by_quintile, 3),
                "q4_avg_return": _quintile_avg(avg_by_quintile, 4),
                "q5_avg_return": _quintile_avg(avg_by_quintile, 5),
            }
        ]
    )

    return QuintileResult(
        factor_name=factor_name,
        forward_horizon=forward_horizon,
        quintile_returns=quintile_returns,
        spread_summary=spread_summary,
    )


def _quintile_avg(frame: pd.DataFrame, quintile: int) -> float:
    rows = frame.loc[frame["quintile"] == quintile, "avg_return"]
    if rows.empty:
        return float("nan")
    return float(rows.iloc[0])


def _quintile_spread(frame: pd.DataFrame, long_quintile: int, short_quintile: int) -> float:
    return _quintile_avg(frame, long_quintile) - _quintile_avg(frame, short_quintile)
