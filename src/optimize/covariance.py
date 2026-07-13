"""공분산·기대수익 추정 유틸."""

from __future__ import annotations

import logging

import pandas as pd

from src.optimize.methods import MIN_TICKERS_FOR_OPTIMIZE

logger = logging.getLogger("qseed")


def build_price_panel(
    prices: pd.DataFrame,
    tickers: list[str],
    *,
    as_of: pd.Timestamp,
    lookback: int,
) -> pd.DataFrame:
    """리밸런싱일 기준 lookback 거래일 Close 패널 (Date x Ticker)."""
    frame = prices.loc[prices["Ticker"].isin(tickers), ["Date", "Ticker", "Close"]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.loc[frame["Date"] <= as_of]
    if frame.empty:
        return pd.DataFrame()

    panel = frame.pivot(index="Date", columns="Ticker", values="Close").sort_index()
    panel = panel.dropna(axis=1, how="all")
    if len(panel) > lookback:
        panel = panel.iloc[-lookback:]
    return panel


def daily_returns_from_prices(price_panel: pd.DataFrame) -> pd.DataFrame:
    """Close 패널에서 일간 수익률 산출."""
    if price_panel.empty:
        return pd.DataFrame()
    returns = price_panel.pct_change(fill_method=None).replace(
        [float("inf"), float("-inf")],
        pd.NA,
    )
    return returns.dropna(how="all")


def _has_min_assets(frame: pd.DataFrame) -> bool:
    return frame.shape[1] >= MIN_TICKERS_FOR_OPTIMIZE and len(frame) >= MIN_TICKERS_FOR_OPTIMIZE


def estimate_mu_and_cov(
    returns: pd.DataFrame,
) -> tuple[pd.Series, pd.DataFrame] | None:
    """pyportfolioopt 기본 추정기로 기대수익·공분산 산출."""
    if returns.empty or returns.shape[1] < MIN_TICKERS_FOR_OPTIMIZE:
        return None

    clean = returns.dropna(axis=1, how="any")
    if not _has_min_assets(clean):
        # 완전 교차 관측이 부족하면 행 기준 dropna 후 재시도
        clean = returns.dropna(axis=0, how="any")
        if not _has_min_assets(clean):
            return None

    try:
        from pypfopt import expected_returns, risk_models

        mu = expected_returns.mean_historical_return(clean, returns_data=True, compounding=True)
        cov = risk_models.CovarianceShrinkage(clean, returns_data=True).ledoit_wolf()
        common = sorted(set(mu.index) & set(cov.index) & set(cov.columns))
        if len(common) < MIN_TICKERS_FOR_OPTIMIZE:
            return None
        return mu.loc[common], cov.loc[common, common]
    except Exception:
        logger.warning("기대수익·공분산 추정 실패", exc_info=True)
        return None
