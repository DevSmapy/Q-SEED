"""리밸런싱일 슬리브별 포트폴리오 가중치 최적화."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from src.optimize.covariance import (
    build_price_panel,
    daily_returns_from_prices,
    estimate_mu_and_cov,
)
from src.optimize.methods import (
    DEFAULT_LOOKBACK,
    DEFAULT_MAX_ASSETS,
    MIN_OBSERVATIONS_FOR_OPTIMIZE,
    MIN_TICKERS_FOR_OPTIMIZE,
    WeightMethod,
)

logger = logging.getLogger("qseed")

LONG_SHORT_SLEEVE_BUDGET = 0.5
LONG_ONLY_SLEEVE_BUDGET = 1.0


@dataclass(frozen=True)
class SleeveOptimizeParams:
    """슬리브 최적화 파라미터."""

    as_of: pd.Timestamp
    method: WeightMethod
    lookback: int = DEFAULT_LOOKBACK
    sleeve_budget: float = LONG_ONLY_SLEEVE_BUDGET
    max_assets: int = DEFAULT_MAX_ASSETS


def equal_weight_map(tickers: list[str], *, sleeve_budget: float) -> dict[str, float]:
    """슬리브 예산 내 동일가중."""
    if not tickers:
        return {}
    weight = sleeve_budget / len(tickers)
    return {ticker: weight for ticker in tickers}


def _scale_to_budget(weights: dict[str, float], *, sleeve_budget: float) -> dict[str, float]:
    positive = {t: max(0.0, w) for t, w in weights.items() if w is not None and w > 0}
    total = sum(positive.values())
    if total <= 0:
        return {}
    return {t: (w / total) * sleeve_budget for t, w in positive.items()}


def optimize_sleeve_weights(
    tickers: list[str],
    prices: pd.DataFrame,
    params: SleeveOptimizeParams,
) -> dict[str, float]:
    """단일 슬리브(long 또는 short) 가중치 산출. 실패 시 동일가중 폴백."""
    unique_tickers = sorted(set(tickers))
    fallback = equal_weight_map(unique_tickers, sleeve_budget=params.sleeve_budget)
    if not unique_tickers:
        return {}
    if params.method == "equal_weight" or len(unique_tickers) < MIN_TICKERS_FOR_OPTIMIZE:
        if params.method != "equal_weight":
            logger.warning(
                "최적화 종목 수 부족 (method=%s, n=%d < %d, as_of=%s) → equal_weight 폴백",
                params.method,
                len(unique_tickers),
                MIN_TICKERS_FOR_OPTIMIZE,
                params.as_of.date(),
            )
        return fallback

    panel = build_price_panel(
        prices,
        unique_tickers,
        as_of=params.as_of,
        lookback=params.lookback,
    )
    returns = daily_returns_from_prices(panel)
    if returns.empty or len(returns) < MIN_OBSERVATIONS_FOR_OPTIMIZE:
        logger.warning(
            "최적화 lookback 부족 (as_of=%s, n=%d) → equal_weight 폴백",
            params.as_of.date(),
            len(returns),
        )
        return fallback

    # 관측치가 많은 종목 우선으로 max_assets 제한 (대규모 분위수 유니버스 대응)
    coverage = returns.notna().sum().sort_values(ascending=False)
    eligible = [t for t in coverage.index.astype(str).tolist() if t in unique_tickers]
    if params.max_assets > 0 and len(eligible) > params.max_assets:
        logger.warning(
            "슬리브 종목 %d → max_assets=%d 로 축소 (method=%s, as_of=%s); "
            "선정 유니버스와 최적화 유니버스가 달라질 수 있습니다",
            len(eligible),
            params.max_assets,
            params.method,
            params.as_of.date(),
        )
        eligible = eligible[: params.max_assets]
    returns = returns[eligible]
    try:
        if params.method == "hrp":
            raw = _solve_hrp(returns, eligible)
        else:
            raw = _solve_efficient_frontier(returns, eligible, params.method)
    except Exception as exc:
        logger.warning(
            "최적화 실패 (method=%s, as_of=%s): %s → equal_weight 폴백",
            params.method,
            params.as_of.date(),
            exc,
        )
        return fallback

    if not raw:
        logger.warning(
            "최적화 결과 비어 있음 (method=%s, as_of=%s) → equal_weight 폴백",
            params.method,
            params.as_of.date(),
        )
        return fallback

    scaled = _scale_to_budget(raw, sleeve_budget=params.sleeve_budget)
    return scaled if scaled else fallback


def reweight_positions(
    positions: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    method: WeightMethod,
    lookback: int = DEFAULT_LOOKBACK,
    max_assets: int = DEFAULT_MAX_ASSETS,
) -> pd.DataFrame:
    """선정된 포지션의 weight 컬럼을 최적화 결과로 교체."""
    if positions.empty or method == "equal_weight":
        return positions.copy()

    frame = positions.copy()
    frame["rebalance_date"] = pd.to_datetime(frame["rebalance_date"])
    records: list[dict[str, object]] = []

    for rebalance_key, group in frame.groupby("rebalance_date", sort=True):
        as_of = pd.Timestamp(str(rebalance_key))
        long_tickers = group.loc[group["side"] == "long", "Ticker"].astype(str).tolist()
        short_tickers = group.loc[group["side"] == "short", "Ticker"].astype(str).tolist()
        has_short = len(short_tickers) > 0
        long_budget = LONG_SHORT_SLEEVE_BUDGET if has_short else LONG_ONLY_SLEEVE_BUDGET
        short_budget = LONG_SHORT_SLEEVE_BUDGET if has_short else 0.0

        long_weights = optimize_sleeve_weights(
            long_tickers,
            prices,
            SleeveOptimizeParams(
                as_of=as_of,
                method=method,
                lookback=lookback,
                sleeve_budget=long_budget,
                max_assets=max_assets,
            ),
        )
        short_weights = (
            optimize_sleeve_weights(
                short_tickers,
                prices,
                SleeveOptimizeParams(
                    as_of=as_of,
                    method=method,
                    lookback=lookback,
                    sleeve_budget=short_budget,
                    max_assets=max_assets,
                ),
            )
            if has_short
            else {}
        )

        for ticker, weight in long_weights.items():
            if weight <= 0:
                continue
            records.append(
                {
                    "rebalance_date": as_of,
                    "Ticker": ticker,
                    "side": "long",
                    "weight": weight,
                }
            )
        for ticker, weight in short_weights.items():
            if weight <= 0:
                continue
            records.append(
                {
                    "rebalance_date": as_of,
                    "Ticker": ticker,
                    "side": "short",
                    "weight": weight,
                }
            )

    if not records:
        return positions.copy()
    return pd.DataFrame(records)


def _solve_efficient_frontier(
    returns: pd.DataFrame,
    tickers: list[str],
    method: WeightMethod,
) -> dict[str, float]:
    """Mean-variance Efficient Frontier (min_volatility / max_sharpe)."""
    from pypfopt import EfficientFrontier, objective_functions

    estimated = estimate_mu_and_cov(returns)
    if estimated is None:
        return {}
    mu, cov = estimated
    available = [t for t in tickers if t in mu.index and t in cov.index]
    if len(available) < MIN_TICKERS_FOR_OPTIMIZE:
        return {}

    ef = EfficientFrontier(
        mu.loc[available],
        cov.loc[available, available],
        weight_bounds=(0, 1),
    )
    # max_sharpe transforms the problem; L2_reg interferes with the solver.
    if method == "min_volatility":
        ef.add_objective(objective_functions.L2_reg, gamma=0.1)
        ef.min_volatility()
    elif method == "max_sharpe":
        ef.max_sharpe()
    else:
        msg = f"unsupported EF method: {method}"
        raise ValueError(msg)
    cleaned = ef.clean_weights()
    return {str(k): float(v) for k, v in cleaned.items() if float(v) > 0}


def _solve_hrp(returns: pd.DataFrame, tickers: list[str]) -> dict[str, float]:
    """Hierarchical Risk Parity."""
    from pypfopt import HRPOpt

    available = [t for t in tickers if t in returns.columns]
    if len(available) < MIN_TICKERS_FOR_OPTIMIZE:
        return {}
    subset = returns[available].dropna(how="any")
    if len(subset) < MIN_OBSERVATIONS_FOR_OPTIMIZE or subset.shape[1] < MIN_TICKERS_FOR_OPTIMIZE:
        valid_cols = [
            c for c in available if returns[c].notna().sum() >= MIN_OBSERVATIONS_FOR_OPTIMIZE
        ]
        if len(valid_cols) < MIN_TICKERS_FOR_OPTIMIZE:
            return {}
        subset = returns[valid_cols].dropna(how="any")
        if len(subset) < MIN_OBSERVATIONS_FOR_OPTIMIZE:
            return {}

    hrp = HRPOpt(subset)
    weights = hrp.optimize()
    return {str(k): float(v) for k, v in weights.items() if float(v) > 0}
