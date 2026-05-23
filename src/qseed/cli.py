"""Q-SEED CLI 진입점."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.pipelines.stock_pipeline import StockDataPipeline, StockPipelineDependencies


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
        "--build-db",
        action="store_true",
        help="전체 데이터베이스 구축 (모든 시장, 최대 기간)",
    )
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="데이터베이스 증분 업데이트 (마지막 날짜 이후 데이터 수집)",
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
    return parser


def main() -> int:
    """CLI 메인 함수."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.run_stock_pipeline and not args.build_db and not args.update_db:
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

    # --build-db 또는 --update-db 옵션 처리
    mode = args.mode
    if args.build_db:
        pipeline.config.stock.max_stocks = 1000000  # 사실상 제한 없음
        pipeline.fetcher.period = "max"
        mode = "full"
        logger.info("모드: 전체 데이터베이스 구축 (--build-db)")
        logger.info("- 모든 지원 시장의 모든 티커 수집 시도")
        logger.info("- 데이터 수집 기간: max")
    elif args.update_db:
        pipeline.config.stock.max_stocks = 1000000  # 사실상 제한 없음
        mode = "incremental"
        logger.info("모드: 데이터베이스 증분 업데이트 (--update-db)")
        logger.info("- 모든 지원 시장의 모든 티커 수집 시도")
        logger.info("- 데이터베이스의 마지막 날짜 이후부터 업데이트")

    if args.max_stocks is not None:
        pipeline.config.stock.max_stocks = args.max_stocks
    if args.chunk_size is not None:
        pipeline.config.stock.chunk_size = args.chunk_size
    if args.download_period is not None:
        pipeline.fetcher.period = args.download_period
    if args.sleep_interval is not None:
        pipeline.config.stock.sleep_interval = args.sleep_interval

    pipeline.run(
        mode=mode,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    logger.info("Q-SEED CLI 실행 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
