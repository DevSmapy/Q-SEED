"""CLI 명령 핸들러."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.pipelines.stock_types import PipelineMode, PipelineRunOptions
from src.qseed import hints

if TYPE_CHECKING:
    from src.pipelines.stock_pipeline import StockDataPipeline


@dataclass(frozen=True)
class ResolvedStockPipelineCli:
    """CLI 플래그를 적용한 뒤의 수집 설정."""

    mode: PipelineMode
    max_stocks: int
    period: str
    chunk_size: int
    sleep_interval: float
    yfinance_threads: bool
    skip_auto_repair: bool
    markets: list[str] | None


@dataclass(frozen=True)
class StockPipelineCliDefaults:
    """파이프라인 객체에서 읽은 CLI 기본값."""

    max_stocks: int
    period: str
    chunk_size: int
    sleep_interval: float
    yfinance_threads: bool


def resolve_stock_pipeline_cli(
    args: argparse.Namespace,
    defaults: StockPipelineCliDefaults,
) -> ResolvedStockPipelineCli:
    """`--build-db` 프리셋 뒤에 `--max-stocks` 등 범위 플래그를 적용한다."""
    mode: PipelineMode = args.mode
    max_stocks = defaults.max_stocks
    period = defaults.period
    if args.build_db:
        max_stocks = 1_000_000
        period = "max"
        mode = "full"
    elif args.update_db:
        max_stocks = 1_000_000
        mode = "incremental"

    if args.max_stocks is not None:
        max_stocks = args.max_stocks
    chunk_size = args.chunk_size if args.chunk_size is not None else defaults.chunk_size
    if args.download_period is not None:
        period = args.download_period
    sleep_interval = (
        args.sleep_interval if args.sleep_interval is not None else defaults.sleep_interval
    )
    yfinance_threads = bool(defaults.yfinance_threads or args.yfinance_threads)
    return ResolvedStockPipelineCli(
        mode=mode,
        max_stocks=max_stocks,
        period=period,
        chunk_size=chunk_size,
        sleep_interval=sleep_interval,
        yfinance_threads=yfinance_threads,
        skip_auto_repair=bool(args.no_gap_repair),
        markets=args.market,
    )


def _log_stock_pipeline_plan(
    args: argparse.Namespace,
    resolved: ResolvedStockPipelineCli,
    logger: logging.Logger,
    *,
    auto_repair_gaps: bool,
) -> None:
    if args.build_db:
        logger.info("모드: 전체 데이터베이스 구축 (--build-db)")
    elif args.update_db:
        logger.info("모드: 데이터베이스 증분 업데이트 (--update-db)")
        logger.info("- 청크별 티커 last_date 기준 수집 (전역 MAX Date 미사용)")
    else:
        logger.info("모드: 주식 파이프라인 (--run-stock-pipeline, mode=%s)", resolved.mode)

    if resolved.markets:
        logger.info("- 대상 시장: %s", ", ".join(resolved.markets))
    else:
        logger.info("- 대상 시장: 전체")
    logger.info("- 시장별 최대 종목 수: %s", resolved.max_stocks)
    logger.info("- 데이터 수집 기간: %s", resolved.period)
    if args.update_db:
        if auto_repair_gaps and not resolved.skip_auto_repair:
            logger.info("- 완료 후 시장별 공백 티커 자동 복구")
        elif resolved.skip_auto_repair:
            logger.info("- 자동 공백 복구 비활성화 (--no-gap-repair)")


def setup_logging(log_file: Path) -> logging.Logger:
    """로깅 설정. 콘솔과 파일 모두에 출력."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 로거 생성
    logger = logging.getLogger("qseed")
    logger.setLevel(logging.INFO)

    # 기존 핸들러 제거 (중복 방지)
    if logger.hasHandlers():
        logger.handlers.clear()

    # 포맷 설정
    log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # 파일 핸들러 (직접 쓰기 방식으로 시도)
    class SimpleFileHandler(logging.Handler):
        def __init__(self, filename: Path) -> None:
            super().__init__()
            self.filename = filename

        def emit(self, record: logging.LogRecord) -> None:
            try:
                msg = self.format(record)
                with open(self.filename, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
                    f.flush()
            except Exception:
                self.handleError(record)

    file_handler = SimpleFileHandler(log_file)
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    # 로거가 전파되지 않도록 설정 (basicConfig와의 간섭 방지)
    logger.propagate = False

    return logger


def _resolve_position_mode(args: argparse.Namespace, default: str) -> str:
    position_mode = args.position_mode or default
    if args.long_only:
        position_mode = "long_only"
    return position_mode


def run_optimize_cli(args: argparse.Namespace) -> int:
    """포트폴리오 최적화 백테스트 CLI 실행."""
    from src.backtest.export import resolve_backtest_output_dir
    from src.optimize.methods import WEIGHT_METHODS
    from src.optimize.runner import OptimizeRunConfig, OptimizeRunner
    from src.qseed.config import get_config
    from src.repositories.backtest_repository import BacktestRepository

    config = get_config()
    if args.data_dir is not None:
        config.stock.base_dir = Path(args.data_dir)

    factor_name = args.factor or config.optimize.default_factor
    position_mode = _resolve_position_mode(args, config.optimize.position_mode)
    weight_method = args.weight_method or config.optimize.weight_method
    if weight_method not in WEIGHT_METHODS:
        logger = setup_logging(config.stock.log_dir / "qseed_run.log")
        logger.error("지원하지 않는 weight_method: %s", weight_method)
        return 1

    configured_output = (
        Path(args.backtest_output_dir)
        if args.backtest_output_dir is not None
        else config.backtest.output_dir
    )
    output_dir = resolve_backtest_output_dir(config.stock.base_dir, configured_output)
    log_path = config.stock.log_dir / "qseed_run.log"
    logger = setup_logging(log_path)
    logger.info(
        "최적화 CLI 실행 시작 (method=%s, 출력: %s)",
        weight_method,
        output_dir,
    )

    if not config.stock.db_path.exists():
        logger.error("%s", hints.missing_db(config.stock.db_path))
        return 1

    with BacktestRepository(config.stock.db_path) as repository:
        runner = OptimizeRunner(repository, output_dir=output_dir)
        runner.run(
            factor_name,
            config=OptimizeRunConfig(
                markets=args.market,
                position_mode=position_mode,  # type: ignore[arg-type]
                rebalance_freq=args.rebalance_freq or config.backtest.rebalance_freq,
                min_observations=config.backtest.min_observations,
                transaction_cost_bps=(
                    args.transaction_cost_bps
                    if args.transaction_cost_bps is not None
                    else config.backtest.transaction_cost_bps
                ),
                initial_capital=config.backtest.initial_capital,
                weight_method=weight_method,  # type: ignore[arg-type]
                opt_lookback=args.opt_lookback or config.optimize.lookback,
                opt_max_assets=args.opt_max_assets or config.optimize.max_assets,
                export_format=args.export_format or config.backtest.export_format,  # type: ignore[arg-type]
            ),
        )
    logger.info("최적화 CLI 실행 완료")
    return 0


def run_backtest_cli(args: argparse.Namespace) -> int:
    """백테스트 CLI 실행."""
    from src.backtest.export import resolve_backtest_output_dir
    from src.backtest.runner import BacktestRunConfig, BacktestRunner
    from src.optimize.methods import WEIGHT_METHODS
    from src.qseed.config import get_config
    from src.repositories.backtest_repository import BacktestRepository

    config = get_config()
    if args.data_dir is not None:
        config.stock.base_dir = Path(args.data_dir)

    factor_name = args.factor or config.backtest.default_factor
    position_mode = _resolve_position_mode(args, config.backtest.position_mode)
    weight_method = args.weight_method or "equal_weight"
    if weight_method not in WEIGHT_METHODS:
        logger = setup_logging(config.stock.log_dir / "qseed_run.log")
        logger.error("지원하지 않는 weight_method: %s", weight_method)
        return 1

    configured_output = (
        Path(args.backtest_output_dir)
        if args.backtest_output_dir is not None
        else config.backtest.output_dir
    )
    output_dir = resolve_backtest_output_dir(config.stock.base_dir, configured_output)
    log_path = config.stock.log_dir / "qseed_run.log"
    logger = setup_logging(log_path)
    logger.info("백테스트 CLI 실행 시작 (출력: %s)", output_dir)

    if not config.stock.db_path.exists():
        logger.error("%s", hints.missing_db(config.stock.db_path))
        return 1

    with BacktestRepository(config.stock.db_path) as repository:
        runner = BacktestRunner(repository, output_dir=output_dir)
        runner.run(
            factor_name,
            config=BacktestRunConfig(
                markets=args.market,
                position_mode=position_mode,  # type: ignore[arg-type]
                rebalance_freq=args.rebalance_freq or config.backtest.rebalance_freq,
                min_observations=config.backtest.min_observations,
                transaction_cost_bps=(
                    args.transaction_cost_bps
                    if args.transaction_cost_bps is not None
                    else config.backtest.transaction_cost_bps
                ),
                initial_capital=config.backtest.initial_capital,
                weight_method=weight_method,  # type: ignore[arg-type]
                opt_lookback=args.opt_lookback or config.optimize.lookback,
                opt_max_assets=args.opt_max_assets or config.optimize.max_assets,
                export_format=args.export_format or config.backtest.export_format,  # type: ignore[arg-type]
            ),
        )
    logger.info("백테스트 CLI 실행 완료")
    return 0


def run_factor_analysis(args: argparse.Namespace) -> int:
    """팩터 분석 CLI 실행."""
    from src.analysis.runner import FactorAnalysisRunner, FactorRunConfig
    from src.factors.registry import list_factors
    from src.qseed.config import get_config
    from src.repositories.factor_repository import FactorRepository

    if args.list_factors:
        for spec in list_factors():
            direction = "높을수록 유리" if spec.higher_is_better else "낮을수록 유리"
            print(f"{spec.name}: {spec.description} ({direction})")
        return 0

    config = get_config()
    if args.data_dir is not None:
        config.stock.base_dir = Path(args.data_dir)

    factor_name = args.factor or config.factor.default_factor
    forward_horizon = args.forward_horizon or config.factor.forward_horizon
    output_dir = config.stock.base_dir / "factor_analysis"

    log_path = config.stock.log_dir / "qseed_run.log"
    logger = setup_logging(log_path)
    logger.info("팩터 분석 CLI 실행 시작")

    if not config.stock.db_path.exists():
        logger.error("%s", hints.missing_db(config.stock.db_path))
        return 1

    with FactorRepository(config.stock.db_path) as repository:
        runner = FactorAnalysisRunner(repository, output_dir=output_dir)
        try:
            runner.run(
                factor_name,
                config=FactorRunConfig(
                    markets=args.market,
                    forward_horizon=forward_horizon,
                    min_observations=config.factor.min_observations,
                ),
            )
        except ValueError as exc:
            logger.error("%s", exc)
            return 1
    logger.info("팩터 분석 CLI 실행 완료")
    return 0


def run_market_pipeline_cli(args: argparse.Namespace, logger: logging.Logger) -> int:
    """시장 지표 파이프라인 CLI 실행."""
    from src.pipelines.market_pipeline import MarketDataPipeline, MarketPipelineOptions
    from src.qseed.config import get_config

    config = get_config()
    if args.data_dir is not None:
        config.stock.base_dir = Path(args.data_dir)

    pipeline = MarketDataPipeline(config=config)
    logger.info("모드: 시장 지표 파이프라인 (--run-market-pipeline)")
    if args.breadth_only:
        logger.info("- breadth만 재계산 (--breadth-only)")
    pipeline.run(
        MarketPipelineOptions(
            breadth_only=args.breadth_only,
            markets=args.market,
        )
    )
    return 0


def run_stock_pipeline_cli(
    args: argparse.Namespace,
    pipeline: StockDataPipeline,
    logger: logging.Logger,
) -> int:
    """주식 파이프라인 CLI 실행."""
    resolved = resolve_stock_pipeline_cli(
        args,
        StockPipelineCliDefaults(
            max_stocks=pipeline.config.stock.max_stocks,
            period=pipeline.fetcher.period,
            chunk_size=pipeline.config.stock.chunk_size,
            sleep_interval=pipeline.config.stock.sleep_interval,
            yfinance_threads=pipeline.config.stock.yfinance_threads,
        ),
    )
    pipeline.config.stock.max_stocks = resolved.max_stocks
    pipeline.config.stock.chunk_size = resolved.chunk_size
    pipeline.config.stock.sleep_interval = resolved.sleep_interval
    pipeline.fetcher.period = resolved.period
    if resolved.yfinance_threads:
        pipeline.config.stock.yfinance_threads = True
        pipeline.fetcher.threads = True

    _log_stock_pipeline_plan(
        args,
        resolved,
        logger,
        auto_repair_gaps=pipeline.config.stock.auto_repair_gaps,
    )

    pipeline.run(
        PipelineRunOptions(
            mode=resolved.mode,
            start_date=args.start_date,
            end_date=args.end_date,
            skip_auto_repair=resolved.skip_auto_repair,
            markets=resolved.markets,
        )
    )
    return 0


def run_security_enrichment_cli(args: argparse.Namespace) -> int:
    """Manual override import / enrichment queue export."""
    from src.metadata.enrichment import export_enrichment_queue, import_security_overrides
    from src.qseed.config import get_config

    config = get_config()
    if args.data_dir is not None:
        config.stock.base_dir = Path(args.data_dir)

    log_path = config.stock.log_dir / "qseed_run.log"
    logger = setup_logging(log_path)

    if args.import_security_overrides:
        import_result = import_security_overrides(
            config.stock.db_path,
            Path(args.import_security_overrides),
        )
        logger.info(
            "Security overrides imported: upserted=%s skipped=%s",
            import_result.imported,
            import_result.skipped,
        )
        return 0

    if args.export_enrichment_queue:
        export_result = export_enrichment_queue(
            config.stock.db_path,
            Path(args.export_enrichment_queue),
        )
        logger.info(
            "Enrichment queue exported: rows=%s source=%s path=%s",
            export_result.row_count,
            export_result.source,
            export_result.output_path,
        )
        return 0

    return -1


def run_security_metadata_cli(args: argparse.Namespace) -> int:
    """종목 메타데이터 수집 CLI."""
    from src.pipelines.security_metadata_pipeline import (
        SecurityMetadataPipeline,
        SecurityMetadataRunOptions,
    )
    from src.qseed.config import get_config

    config = get_config()
    if args.data_dir is not None:
        config.stock.base_dir = Path(args.data_dir)

    log_path = config.stock.log_dir / "qseed_run.log"
    logger = setup_logging(log_path)
    logger.info("Security metadata CLI 시작")

    max_tickers = args.max_tickers
    if max_tickers is None:
        max_tickers = config.security.max_tickers

    sleep_seconds = args.security_sleep
    if sleep_seconds is None:
        sleep_seconds = config.security.sleep_seconds

    equity_only = args.security_equity_only or config.security.equity_only

    pipeline = SecurityMetadataPipeline(
        db_path=config.stock.db_path,
        ticker_list_path=config.stock.ticker_list_path,
    )
    result = pipeline.run(
        SecurityMetadataRunOptions(
            max_tickers=max_tickers,
            sleep_seconds=sleep_seconds,
            equity_only=equity_only,
        )
    )
    logger.info(
        "Security metadata 완료: upserted=%s mapped=%s unclassified=%s errors=%s",
        result.upserted,
        result.fetch.mapped,
        result.fetch.unclassified,
        result.fetch.errors,
    )
    return 0


def run_stock_main_cli(args: argparse.Namespace) -> int:
    """주식 파이프라인·공백 CLI 진입."""
    from src.pipelines.stock_pipeline import StockDataPipeline, StockPipelineDependencies

    if not (
        args.run_stock_pipeline
        or args.build_db
        or args.update_db
        or args.check_gaps
        or args.repair_gaps
    ):
        return -1

    if args.data_dir is not None:
        new_base_dir = Path(args.data_dir)
        from src.qseed.config import get_config

        config = get_config()
        config.stock.base_dir = new_base_dir
        pipeline = StockDataPipeline(deps=StockPipelineDependencies(config=config))
    else:
        pipeline = StockDataPipeline()

    log_path = pipeline.config.stock.log_dir / "qseed_run.log"
    logger = setup_logging(log_path)
    logger.info("Q-SEED CLI 실행 시작")

    if args.check_gaps or args.repair_gaps:
        if args.check_gaps:
            logger.info("모드: 공백 탐지 (--check-gaps)")
            pipeline.run(PipelineRunOptions(check_gaps_only=True, markets=args.market))
        else:
            logger.info("모드: 공백 복구 (--repair-gaps)")
            pipeline.run(
                PipelineRunOptions(
                    repair_gaps=True,
                    end_date=args.end_date,
                    markets=args.market,
                )
            )
        logger.info("Q-SEED CLI 실행 완료")
        return 0

    run_stock_pipeline_cli(args, pipeline, logger)
    logger.info("Q-SEED CLI 실행 완료")
    return 0
