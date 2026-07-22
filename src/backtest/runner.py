"""백테스트 실행 오케스트레이터."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pandas as pd

from src.backtest.engine import BacktestEngineResult, run_backtest_engine
from src.backtest.export import BacktestExportPayload, BacktestRunScope, save_backtest_run
from src.backtest.metrics import BacktestMetrics, compute_backtest_metrics, metrics_to_dataframe
from src.backtest.strategy import (
    BacktestStrategy,
    BacktestStrategyOverrides,
    build_strategy_from_factor,
)
from src.factors.registry import get_factor
from src.optimize.methods import DEFAULT_LOOKBACK, DEFAULT_MAX_ASSETS, WeightMethod
from src.repositories.backtest_repository import BacktestRepository, BacktestTables
from src.utils.labels import markets_label

logger = logging.getLogger("qseed")

PositionMode = Literal["long_short", "long_only"]


@dataclass(frozen=True)
class BacktestRunConfig:
    """백테스트 실행 범위 설정 (웹 API 요청 바디와 1:1 매핑 가능)."""

    markets: list[str] | None = None
    tickers: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    position_mode: PositionMode = "long_short"
    long_quintile: int | None = None
    short_quintile: int | None = None
    rebalance_freq: int = 21
    min_observations: int = 30
    transaction_cost_bps: float = 0.0
    initial_capital: float = 100_000_000.0
    weight_method: WeightMethod = "equal_weight"
    opt_lookback: int = DEFAULT_LOOKBACK
    opt_max_assets: int = DEFAULT_MAX_ASSETS
    save_to_db: bool = True
    save_to_files: bool = True
    export_format: Literal["parquet", "csv", "both"] = "parquet"


@dataclass(frozen=True)
class BacktestResult:
    """백테스트 전체 결과."""

    run_id: str
    strategy: BacktestStrategy
    engine: BacktestEngineResult
    metrics: BacktestMetrics
    output_dir: Path | None = None


class BacktestRunner:
    """팩터 백테스트 파이프라인."""

    def __init__(
        self,
        repository: BacktestRepository,
        *,
        output_dir: Path | None = None,
    ) -> None:
        self.repository = repository
        self.output_dir = output_dir

    def run(
        self,
        factor_name: str,
        config: BacktestRunConfig | None = None,
    ) -> BacktestResult:
        """팩터 전략 백테스트 실행."""
        run_config = config or BacktestRunConfig()
        _ = get_factor(factor_name)
        strategy = build_strategy_from_factor(
            factor_name,
            BacktestStrategyOverrides(
                position_mode=run_config.position_mode,
                long_quintile=run_config.long_quintile,
                short_quintile=run_config.short_quintile,
                rebalance_freq=run_config.rebalance_freq,
                min_observations=run_config.min_observations,
                transaction_cost_bps=run_config.transaction_cost_bps,
                initial_capital=run_config.initial_capital,
                weight_method=run_config.weight_method,
                opt_lookback=run_config.opt_lookback,
                opt_max_assets=run_config.opt_max_assets,
            ),
        )
        run_id = _generate_run_id(factor_name, run_config.weight_method)

        logger.info(
            "백테스트 시작: %s (run_id=%s, weight_method=%s)",
            factor_name,
            run_id,
            run_config.weight_method,
        )

        prices = self.repository.load_prices(
            markets=run_config.markets,
            tickers=run_config.tickers,
            start_date=run_config.start_date,
            end_date=run_config.end_date,
        )
        if prices.empty:
            msg = "백테스트할 주가 데이터가 없습니다. stocks.db를 먼저 구축하세요."
            raise ValueError(msg)

        spec = get_factor(factor_name)
        factor_values = spec.compute(prices)
        engine_result = run_backtest_engine(prices, factor_values, strategy)
        metrics = compute_backtest_metrics(
            engine_result.daily_returns,
            factor_name=factor_name,
            position_mode=strategy.position_mode,
            rebalance_freq=strategy.rebalance_freq,
            rebalance_count=len(engine_result.rebalance_dates),
        )

        scope = BacktestRunScope(
            markets=run_config.markets,
            start_date=run_config.start_date,
            end_date=run_config.end_date,
            ticker_count=int(prices["Ticker"].nunique()),
            trading_days=len(engine_result.daily_returns),
            rebalance_count=len(engine_result.rebalance_dates),
        )
        summary = metrics_to_dataframe(metrics)
        summary["markets"] = markets_label(run_config.markets)
        summary["ticker_count"] = scope.ticker_count
        summary["output_path"] = str(self.output_dir / run_id) if self.output_dir else None

        if run_config.save_to_db:
            self.repository.save_backtest_tables(
                BacktestTables(
                    run_id=run_id,
                    strategy=strategy,
                    scope=scope,
                    daily_returns=engine_result.daily_returns,
                    positions=engine_result.positions,
                    summary=summary,
                )
            )
            logger.info("DuckDB에 백테스트 결과 저장 완료")

        export_dir: Path | None = None
        if run_config.save_to_files and self.output_dir is not None:
            export_result = save_backtest_run(
                self.output_dir,
                BacktestExportPayload(
                    run_id=run_id,
                    strategy=strategy,
                    scope=scope,
                    daily_returns=engine_result.daily_returns,
                    positions=engine_result.positions,
                    metrics=metrics,
                    export_format=run_config.export_format,
                ),
            )
            export_dir = export_result.run_dir
            logger.info("파일 출력 완료: %s", export_result.manifest_path)

        self._log_summary(metrics)
        return BacktestResult(
            run_id=run_id,
            strategy=strategy,
            engine=engine_result,
            metrics=metrics,
            output_dir=export_dir,
        )

    def _log_summary(self, metrics: BacktestMetrics) -> None:
        logger.info(
            "CAGR=%.2f%%, MDD=%.2f%%, Sharpe=%.2f, Win rate=%.1f%%",
            metrics.cagr * 100 if pd.notna(metrics.cagr) else float("nan"),
            metrics.max_drawdown * 100 if pd.notna(metrics.max_drawdown) else float("nan"),
            metrics.sharpe if pd.notna(metrics.sharpe) else float("nan"),
            metrics.win_rate * 100 if pd.notna(metrics.win_rate) else float("nan"),
        )


def _generate_run_id(factor_name: str, weight_method: WeightMethod = "equal_weight") -> str:
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    if weight_method == "equal_weight":
        return f"{factor_name}_{timestamp}"
    return f"{factor_name}_{weight_method}_{timestamp}"
