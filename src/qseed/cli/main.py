"""CLI 메인 라우팅."""

from __future__ import annotations

from pathlib import Path

from src.qseed.cli.commands import (
    run_backtest_cli,
    run_factor_analysis,
    run_market_pipeline_cli,
    run_optimize_cli,
    run_security_enrichment_cli,
    run_security_metadata_cli,
    run_stock_main_cli,
    setup_logging,
)
from src.qseed.cli.parser import build_parser
from src.utils.helpers import raise_open_file_limit


def main() -> int:
    """CLI 메인 함수."""
    raise_open_file_limit()
    parser = build_parser()
    args = parser.parse_args()

    analysis_or_backtest = (
        args.list_factors or args.run_factor_analysis or args.run_optimize or args.run_backtest
    )
    if args.update_security_metadata:
        return run_security_metadata_cli(args)

    if args.import_security_overrides or args.export_enrichment_queue:
        exit_code = run_security_enrichment_cli(args)
        if exit_code >= 0:
            return exit_code

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

    stock_exit = run_stock_main_cli(args)
    if stock_exit >= 0:
        return stock_exit

    parser.print_help()
    return 0
