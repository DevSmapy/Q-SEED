"""Q-SEED CLI 진입점."""

from __future__ import annotations

import argparse

from src.pipelines.stock_pipeline import StockDataPipeline


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
        "--max-stocks",
        type=int,
        default=None,
        help="최대 수집 종목 수",
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
    return parser


def main() -> int:
    """CLI 메인 함수."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.run_stock_pipeline:
        parser.print_help()
        return 0

    pipeline = StockDataPipeline()

    if args.max_stocks is not None:
        pipeline.config.stock.max_stocks = args.max_stocks
    if args.chunk_size is not None:
        pipeline.config.stock.chunk_size = args.chunk_size
    if args.download_period is not None:
        pipeline.fetcher.period = args.download_period
    if args.sleep_interval is not None:
        pipeline.config.stock.sleep_interval = args.sleep_interval

    pipeline.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
