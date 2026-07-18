"""Q-SEED CLI 진입점."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.pipelines.market_pipeline import MarketDataPipeline, MarketPipelineOptions
from src.pipelines.stock_pipeline import (
    PipelineMode,
    PipelineRunOptions,
    StockDataPipeline,
    StockPipelineDependencies,
)
from src.utils.helpers import raise_open_file_limit


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


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성."""
    parser = argparse.ArgumentParser(
        prog="qseed",
        description="Q-SEED 주식 데이터 수집 도구",
    )
    parser.add_argument(
        "--run-stock-pipeline",
        action="store_true",
        help="주식 데이터 수집 파이프라인 실행",
    )
    parser.add_argument(
        "--run-market-pipeline",
        action="store_true",
        help="시장 지표 시계열 수집 및 breadth 파생 적재",
    )
    parser.add_argument(
        "--breadth-only",
        action="store_true",
        help="--run-market-pipeline 시 외부 시계열 수집 없이 breadth만 재계산",
    )
    parser.add_argument(
        "--build-db",
        action="store_true",
        help="전체 데이터베이스 구축 (모든 시장, 최대 기간)",
    )
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="데이터베이스 증분 업데이트 (마지막 날짜 이후 데이터 수집, 종료 후 공백 자동 복구)",
    )
    parser.add_argument(
        "--check-gaps",
        action="store_true",
        help="시장별 기준일 대비 뒤처진 티커 공백 탐지 (수집 없음)",
    )
    parser.add_argument(
        "--repair-gaps",
        action="store_true",
        help="공백이 감지된 티커만 재수집",
    )
    parser.add_argument(
        "--no-gap-repair",
        action="store_true",
        help="--update-db 실행 시 종료 후 자동 공백 복구 비활성화",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="full",
        choices=["full", "incremental"],
        help="실행 모드 (full 또는 incremental)",
    )
    parser.add_argument(
        "--max-stocks",
        type=int,
        default=None,
        help="시장별 최대 수집 종목 수 (입력값이 시스템 최대치를 초과하면 시스템 최대치로 제한됨)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="한 번에 처리할 종목 수",
    )
    parser.add_argument(
        "--download-period",
        type=str,
        default=None,
        help='yfinance 다운로드 기간 (예: "1y", "5y", "max")',
    )
    parser.add_argument(
        "--sleep-interval",
        type=float,
        default=None,
        help="청크 간 대기 시간(초)",
    )
    parser.add_argument(
        "--yfinance-threads",
        action="store_true",
        help="yfinance 멀티스레드 다운로드 활성화 (대량 청크 시 FD 부족 위험)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="수집 시작 날짜 (YYYY-MM-DD, incremental 모드 전용)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="수집 종료 날짜 (YYYY-MM-DD, incremental 모드 전용)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help='데이터 디렉토리 경로 (기본값: "./data")',
    )
    parser.add_argument(
        "--run-factor-analysis",
        action="store_true",
        help="팩터 IC·분위수 분석 실행",
    )
    parser.add_argument(
        "--factor",
        type=str,
        default=None,
        help="분석할 팩터 이름 (예: momentum_12_1, reversal_5d)",
    )
    parser.add_argument(
        "--list-factors",
        action="store_true",
        help="등록된 팩터 목록 출력",
    )
    parser.add_argument(
        "--market",
        type=str,
        action="append",
        default=None,
        help="분석 대상 시장 (반복 지정 가능, 예: --market KOSPI --market KOSDAQ)",
    )
    parser.add_argument(
        "--forward-horizon",
        type=int,
        default=None,
        help="선행 수익률 기간(거래일, 기본값: 21)",
    )
    parser.add_argument(
        "--run-backtest",
        action="store_true",
        help="팩터 롱숏/롱온리 백테스트 실행",
    )
    parser.add_argument(
        "--rebalance-freq",
        type=int,
        default=None,
        help="리밸런싱 주기(거래일, 기본값: 21)",
    )
    parser.add_argument(
        "--position-mode",
        type=str,
        default=None,
        choices=["long_short", "long_only"],
        help="포지션 모드 (long_short 또는 long_only)",
    )
    parser.add_argument(
        "--long-only",
        action="store_true",
        help="롱온리 모드 (--position-mode long_only 와 동일)",
    )
    parser.add_argument(
        "--transaction-cost-bps",
        type=float,
        default=None,
        help="거래비용 (bps, 기본값: 0)",
    )
    parser.add_argument(
        "--backtest-output-dir",
        type=str,
        default=None,
        help='백테스트 결과 출력 경로 (기본값: "{data_dir}/backtest/case_study_kr")',
    )
    parser.add_argument(
        "--export-format",
        type=str,
        default=None,
        choices=["parquet", "csv", "both"],
        help="백테스트 결과 파일 형식 (기본값: parquet)",
    )
    parser.add_argument(
        "--run-optimize",
        action="store_true",
        help="팩터 선정 + 포트폴리오 가중치 최적화 백테스트 실행",
    )
    parser.add_argument(
        "--weight-method",
        type=str,
        default=None,
        choices=["equal_weight", "min_volatility", "max_sharpe", "hrp"],
        help="가중치 방법 (기본: backtest=equal_weight, optimize=min_volatility)",
    )
    parser.add_argument(
        "--opt-lookback",
        type=int,
        default=None,
        help="최적화 lookback 거래일 (기본값: 252)",
    )
    parser.add_argument(
        "--opt-max-assets",
        type=int,
        default=None,
        help="슬리브당 최적화 최대 종목 수 (기본값: 50)",
    )
    return parser


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
        logger.error("DuckDB 파일이 없습니다: %s", config.stock.db_path)
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
        logger.error("DuckDB 파일이 없습니다: %s", config.stock.db_path)
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
        logger.error("DuckDB 파일이 없습니다: %s", config.stock.db_path)
        return 1

    with FactorRepository(config.stock.db_path) as repository:
        runner = FactorAnalysisRunner(repository, output_dir=output_dir)
        runner.run(
            factor_name,
            config=FactorRunConfig(
                markets=args.market,
                forward_horizon=forward_horizon,
                min_observations=config.factor.min_observations,
            ),
        )
    logger.info("팩터 분석 CLI 실행 완료")
    return 0


def run_market_pipeline_cli(args: argparse.Namespace, logger: logging.Logger) -> int:
    """시장 지표 파이프라인 CLI 실행."""
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
    mode: PipelineMode = args.mode
    if args.build_db:
        pipeline.config.stock.max_stocks = 1000000
        pipeline.fetcher.period = "max"
        mode = "full"
        logger.info("모드: 전체 데이터베이스 구축 (--build-db)")
        logger.info("- 모든 지원 시장의 모든 티커 수집 시도")
        logger.info("- 데이터 수집 기간: max")
    elif args.update_db:
        pipeline.config.stock.max_stocks = 1000000
        mode = "incremental"
        logger.info("모드: 데이터베이스 증분 업데이트 (--update-db)")
        logger.info("- 모든 지원 시장의 모든 티커 수집 시도")
        logger.info("- 청크별 티커 last_date 기준 수집 (전역 MAX Date 미사용)")
        if pipeline.config.stock.auto_repair_gaps and not args.no_gap_repair:
            logger.info("- 완료 후 시장별 공백 티커 자동 복구")
        elif args.no_gap_repair:
            logger.info("- 자동 공백 복구 비활성화 (--no-gap-repair)")

    if args.max_stocks is not None:
        pipeline.config.stock.max_stocks = args.max_stocks
    if args.chunk_size is not None:
        pipeline.config.stock.chunk_size = args.chunk_size
    if args.download_period is not None:
        pipeline.fetcher.period = args.download_period
    if args.sleep_interval is not None:
        pipeline.config.stock.sleep_interval = args.sleep_interval
    if args.yfinance_threads:
        pipeline.config.stock.yfinance_threads = True
        pipeline.fetcher.threads = True

    pipeline.run(
        PipelineRunOptions(
            mode=mode,
            start_date=args.start_date,
            end_date=args.end_date,
            skip_auto_repair=args.no_gap_repair,
        )
    )
    return 0


def main() -> int:
    """CLI 메인 함수."""
    raise_open_file_limit()
    parser = build_parser()
    args = parser.parse_args()

    analysis_or_backtest = (
        args.list_factors or args.run_factor_analysis or args.run_optimize or args.run_backtest
    )
    if analysis_or_backtest:
        if args.list_factors or args.run_factor_analysis:
            exit_code = run_factor_analysis(args)
        elif args.run_optimize:
            exit_code = run_optimize_cli(args)
        else:
            exit_code = run_backtest_cli(args)
        return exit_code

    if args.run_market_pipeline:
        from src.qseed.config import get_config

        config = get_config()
        if args.data_dir is not None:
            config.stock.base_dir = Path(args.data_dir)
        log_path = config.stock.log_dir / "qseed_run.log"
        logger = setup_logging(log_path)
        logger.info("Q-SEED CLI 실행 시작")
        exit_code = run_market_pipeline_cli(args, logger)
        logger.info("Q-SEED CLI 실행 완료")
        return exit_code

    if not (
        args.run_stock_pipeline
        or args.build_db
        or args.update_db
        or args.check_gaps
        or args.repair_gaps
    ):
        parser.print_help()
        return 0

    if args.data_dir is not None:
        new_base_dir = Path(args.data_dir)
        # config의 base_dir를 직접 수정 (pydantic-settings 모델)
        from src.qseed.config import get_config

        config = get_config()
        config.stock.base_dir = new_base_dir
        pipeline = StockDataPipeline(deps=StockPipelineDependencies(config=config))
    else:
        pipeline = StockDataPipeline()

    # 로깅 설정 (data/data_log/ 디렉토리 내에 로그 파일 생성)
    log_path = pipeline.config.stock.log_dir / "qseed_run.log"
    logger = setup_logging(log_path)

    logger.info("Q-SEED CLI 실행 시작")

    if args.check_gaps or args.repair_gaps:
        if args.check_gaps:
            logger.info("모드: 공백 탐지 (--check-gaps)")
            pipeline.run(PipelineRunOptions(check_gaps_only=True))
        else:
            logger.info("모드: 공백 복구 (--repair-gaps)")
            pipeline.run(PipelineRunOptions(repair_gaps=True, end_date=args.end_date))
        logger.info("Q-SEED CLI 실행 완료")
        return 0

    run_stock_pipeline_cli(args, pipeline, logger)
    logger.info("Q-SEED CLI 실행 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
