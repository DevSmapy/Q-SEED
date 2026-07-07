"""백테스트 성과 지표."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def _return_series(frame: pd.DataFrame, column: str) -> pd.Series:
    series = pd.to_numeric(frame.set_index("Date")[column], errors="coerce").dropna()
    return series.astype("float64")


def _compound_return(returns: pd.Series) -> float:
    values = returns.to_numpy(dtype="float64")
    return float((1.0 + values).prod() - 1.0)


def _qs_metric(value: object) -> float:
    return float(value)  # type: ignore[arg-type]


@dataclass(frozen=True)
class BacktestMetrics:
    """백테스트 요약 성과 지표."""

    factor_name: str
    position_mode: str
    rebalance_freq: int
    total_return: float
    cagr: float
    max_drawdown: float
    sharpe: float
    sortino: float
    calmar: float
    win_rate: float
    benchmark_total_return: float | None
    benchmark_cagr: float | None
    excess_cagr: float | None
    trading_days: int
    rebalance_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "factor_name": self.factor_name,
            "position_mode": self.position_mode,
            "rebalance_freq": self.rebalance_freq,
            "total_return": self.total_return,
            "cagr": self.cagr,
            "max_drawdown": self.max_drawdown,
            "sharpe": self.sharpe,
            "sortino": self.sortino,
            "calmar": self.calmar,
            "win_rate": self.win_rate,
            "benchmark_total_return": self.benchmark_total_return,
            "benchmark_cagr": self.benchmark_cagr,
            "excess_cagr": self.excess_cagr,
            "trading_days": self.trading_days,
            "rebalance_count": self.rebalance_count,
        }


def compute_backtest_metrics(
    daily_returns: pd.DataFrame,
    *,
    factor_name: str,
    position_mode: str,
    rebalance_freq: int,
    rebalance_count: int,
) -> BacktestMetrics:
    """일별 수익률 시계열에서 성과 지표 산출."""
    import quantstats as qs

    returns = _return_series(daily_returns, "strategy_return")
    if returns.empty:
        return _empty_metrics(
            factor_name=factor_name,
            position_mode=position_mode,
            rebalance_freq=rebalance_freq,
            rebalance_count=rebalance_count,
        )

    total_return = _compound_return(returns)
    cagr = _qs_metric(qs.stats.cagr(returns, periods=TRADING_DAYS_PER_YEAR))
    max_drawdown = _qs_metric(qs.stats.max_drawdown(returns))
    sharpe = _qs_metric(qs.stats.sharpe(returns, periods=TRADING_DAYS_PER_YEAR))
    sortino = _qs_metric(qs.stats.sortino(returns, periods=TRADING_DAYS_PER_YEAR))
    calmar = _qs_metric(qs.stats.calmar(returns, periods=TRADING_DAYS_PER_YEAR))
    win_rate = float((returns > 0).mean())

    benchmark_total_return: float | None = None
    benchmark_cagr: float | None = None
    excess_cagr: float | None = None
    if "benchmark_return" in daily_returns.columns:
        benchmark = _return_series(daily_returns, "benchmark_return")
        if not benchmark.empty:
            benchmark_total_return = _compound_return(benchmark)
            benchmark_cagr = _qs_metric(qs.stats.cagr(benchmark, periods=TRADING_DAYS_PER_YEAR))
            excess_cagr = cagr - benchmark_cagr

    return BacktestMetrics(
        factor_name=factor_name,
        position_mode=position_mode,
        rebalance_freq=rebalance_freq,
        total_return=total_return,
        cagr=cagr,
        max_drawdown=max_drawdown,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        win_rate=win_rate,
        benchmark_total_return=benchmark_total_return,
        benchmark_cagr=benchmark_cagr,
        excess_cagr=excess_cagr,
        trading_days=len(returns),
        rebalance_count=rebalance_count,
    )


def _empty_metrics(
    *,
    factor_name: str,
    position_mode: str,
    rebalance_freq: int,
    rebalance_count: int,
) -> BacktestMetrics:
    nan = float("nan")
    return BacktestMetrics(
        factor_name=factor_name,
        position_mode=position_mode,
        rebalance_freq=rebalance_freq,
        total_return=nan,
        cagr=nan,
        max_drawdown=nan,
        sharpe=nan,
        sortino=nan,
        calmar=nan,
        win_rate=nan,
        benchmark_total_return=None,
        benchmark_cagr=None,
        excess_cagr=None,
        trading_days=0,
        rebalance_count=rebalance_count,
    )


def metrics_to_dataframe(metrics: BacktestMetrics) -> pd.DataFrame:
    """DuckDB 저장용 단일 행 DataFrame."""
    return pd.DataFrame([metrics.to_dict()])
