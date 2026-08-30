"""팩터 분석 실행 오케스트레이터."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.analysis.ic import ICResult, compute_forward_returns, compute_ic
from src.analysis.quintile import QuintileAnalysisConfig, QuintileResult, compute_quintile_returns
from src.factors.base import FactorSpec
from src.factors.registry import get_factor
from src.qseed import hints
from src.repositories.factor_repository import FactorAnalysisTables, FactorRepository
from src.utils.provenance import collect_provenance

logger = logging.getLogger("qseed")


def _ensure_enough_price_history(prices: pd.DataFrame, spec: FactorSpec) -> None:
    """팩터 lookback보다 히스토리가 짧으면 원인과 대안을 알려 실패한다."""
    history_days = prices.groupby("Ticker", sort=False)["Date"].nunique()
    longest = int(history_days.max()) if not history_days.empty else 0
    usable = int((history_days >= spec.min_history_days).sum())
    if usable == 0:
        raise ValueError(hints.short_history(spec.name, spec.min_history_days, longest))


@dataclass(frozen=True)
class FactorAnalysisResult:
    """단일 팩터 분석 전체 결과."""

    factor_name: str
    factor_values: pd.DataFrame
    ic: ICResult
    quintile: QuintileResult


@dataclass(frozen=True)
class FactorRunConfig:
    """팩터 분석 실행 설정."""

    markets: list[str] | None = None
    tickers: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    forward_horizon: int = 21
    min_observations: int = 30
    save_to_db: bool = True
    save_to_files: bool = True


class FactorAnalysisRunner:
    """팩터 계산 → IC·분위수 분석 → 결과 저장."""

    def __init__(
        self,
        repository: FactorRepository,
        *,
        output_dir: Path | None = None,
    ) -> None:
        self.repository = repository
        self.output_dir = output_dir

    def run(
        self,
        factor_name: str,
        config: FactorRunConfig | None = None,
    ) -> FactorAnalysisResult:
        """팩터 분석 파이프라인 실행."""
        run_config = config or FactorRunConfig()
        spec = get_factor(factor_name)
        logger.info("팩터 분석 시작: %s", spec.name)

        prices = self.repository.load_prices(
            markets=run_config.markets,
            tickers=run_config.tickers,
            start_date=run_config.start_date,
            end_date=run_config.end_date,
        )
        if prices.empty:
            raise ValueError(hints.empty_prices())

        n_tickers = int(prices["Ticker"].nunique())
        logger.info("로드된 행 수: %s, 티커 수: %s", len(prices), n_tickers)
        _ensure_enough_price_history(prices, spec)
        if n_tickers < run_config.min_observations:
            logger.warning("%s", hints.too_few_names(n_tickers, run_config.min_observations))

        factor_values = spec.compute(prices)
        if factor_values.empty:
            raise ValueError(
                hints.short_history(spec.name, spec.min_history_days, spec.min_history_days)
            )
        forward_returns = compute_forward_returns(prices, horizon=run_config.forward_horizon)

        ic_result = compute_ic(
            factor_values,
            forward_returns,
            factor_name=spec.name,
            forward_horizon=run_config.forward_horizon,
            min_observations=run_config.min_observations,
        )
        quintile_result = compute_quintile_returns(
            factor_values,
            forward_returns,
            QuintileAnalysisConfig(
                factor_name=spec.name,
                forward_horizon=run_config.forward_horizon,
                higher_is_better=spec.higher_is_better,
                min_observations=run_config.min_observations,
            ),
        )

        if run_config.save_to_db:
            self.repository.save_analysis_tables(
                FactorAnalysisTables(
                    factor_name=spec.name,
                    factor_values=factor_values,
                    ic_daily=ic_result.daily_ic,
                    ic_summary=ic_result.summary,
                    quintile_returns=quintile_result.quintile_returns,
                    quintile_summary=quintile_result.spread_summary,
                )
            )
            logger.info("DuckDB에 분석 결과 저장 완료")

        if run_config.save_to_files and self.output_dir is not None:
            self._save_files(
                spec.name,
                factor_values,
                ic_result,
                quintile_result,
            )
            logger.info("파일 출력 완료: %s", self.output_dir)

        if ic_result.daily_ic.empty:
            logger.warning(
                "유효한 일자별 IC가 없습니다. 날짜별 종목 수가 min_observations(%s) "
                "미만이거나 팩터 값이 부족한 경우가 많습니다.",
                run_config.min_observations,
            )

        self._log_summary(ic_result, quintile_result)
        return FactorAnalysisResult(
            factor_name=spec.name,
            factor_values=factor_values,
            ic=ic_result,
            quintile=quintile_result,
        )

    def _save_files(
        self,
        factor_name: str,
        factor_values: pd.DataFrame,
        ic_result: ICResult,
        quintile_result: QuintileResult,
    ) -> None:
        if self.output_dir is None:
            return

        factor_dir = self.output_dir / factor_name
        factor_dir.mkdir(parents=True, exist_ok=True)

        factor_values.to_parquet(factor_dir / "factor_values.parquet", index=False)
        ic_result.daily_ic.to_parquet(factor_dir / "ic_daily.parquet", index=False)
        ic_result.summary.to_parquet(factor_dir / "ic_summary.parquet", index=False)
        quintile_result.quintile_returns.to_parquet(
            factor_dir / "quintile_returns.parquet",
            index=False,
        )
        quintile_result.spread_summary.to_parquet(
            factor_dir / "quintile_summary.parquet",
            index=False,
        )

        report = {
            "factor_name": factor_name,
            "provenance": collect_provenance(self.repository.db_path),
            "ic_summary": ic_result.summary.to_dict(orient="records"),
            "quintile_summary": quintile_result.spread_summary.to_dict(orient="records"),
        }
        (factor_dir / "analysis_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _log_summary(self, ic_result: ICResult, quintile_result: QuintileResult) -> None:
        ic_row = ic_result.summary.iloc[0]
        spread_row = quintile_result.spread_summary.iloc[0]
        logger.info(
            "IC mean=%.4f, IC IR=%.4f, hit rate=%.2f%%, long-short spread=%.4f",
            ic_row["ic_mean"],
            ic_row["ic_ir"],
            ic_row["hit_rate"] * 100 if pd.notna(ic_row["hit_rate"]) else float("nan"),
            spread_row["long_short_spread"],
        )
