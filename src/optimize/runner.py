"""포트폴리오 최적화 + 백테스트 오케스트레이터."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.backtest.runner import BacktestResult, BacktestRunConfig, BacktestRunner
from src.optimize.methods import (
    DEFAULT_LOOKBACK,
    DEFAULT_MAX_ASSETS,
    DEFAULT_WEIGHT_METHOD,
    WeightMethod,
)
from src.repositories.backtest_repository import BacktestRepository

logger = logging.getLogger("qseed")

PositionMode = Literal["long_short", "long_only"]


@dataclass(frozen=True)
class OptimizeRunConfig:
    """최적화 가중치 백테스트 실행 설정."""

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
    weight_method: WeightMethod = DEFAULT_WEIGHT_METHOD
    opt_lookback: int = DEFAULT_LOOKBACK
    opt_max_assets: int = DEFAULT_MAX_ASSETS
    save_to_db: bool = True
    save_to_files: bool = True
    export_format: Literal["parquet", "csv", "both"] = "parquet"

    def to_backtest_config(self) -> BacktestRunConfig:
        return BacktestRunConfig(
            markets=self.markets,
            tickers=self.tickers,
            start_date=self.start_date,
            end_date=self.end_date,
            position_mode=self.position_mode,
            long_quintile=self.long_quintile,
            short_quintile=self.short_quintile,
            rebalance_freq=self.rebalance_freq,
            min_observations=self.min_observations,
            transaction_cost_bps=self.transaction_cost_bps,
            initial_capital=self.initial_capital,
            weight_method=self.weight_method,
            opt_lookback=self.opt_lookback,
            opt_max_assets=self.opt_max_assets,
            save_to_db=self.save_to_db,
            save_to_files=self.save_to_files,
            export_format=self.export_format,
        )


@dataclass(frozen=True)
class OptimizeResult:
    """최적화 백테스트 결과 (BacktestResult 래핑)."""

    backtest: BacktestResult

    @property
    def run_id(self) -> str:
        return self.backtest.run_id

    @property
    def weight_method(self) -> WeightMethod:
        return self.backtest.strategy.weight_method


class OptimizeRunner:
    """팩터 선정 + 가중치 최적화 + 백테스트 파이프라인."""

    def __init__(
        self,
        repository: BacktestRepository,
        *,
        output_dir: Path | None = None,
    ) -> None:
        self._backtest_runner = BacktestRunner(repository, output_dir=output_dir)

    def run(
        self,
        factor_name: str,
        config: OptimizeRunConfig | None = None,
    ) -> OptimizeResult:
        """최적화 가중치로 백테스트 실행."""
        run_config = config or OptimizeRunConfig()
        logger.info(
            "최적화 백테스트 시작: factor=%s method=%s lookback=%d",
            factor_name,
            run_config.weight_method,
            run_config.opt_lookback,
        )
        result = self._backtest_runner.run(factor_name, run_config.to_backtest_config())
        return OptimizeResult(backtest=result)
