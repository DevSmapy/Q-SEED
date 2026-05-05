"""주식 데이터 수집 파이프라인."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

if typing.TYPE_CHECKING:
    from src.fetchers.yfinance import YFinanceFetcher
    from src.providers.krx import KRXProvider
    from src.qseed.config import AppConfig
    from src.repositories.duckdb import DuckDBRepository
    from src.repositories.parquet import ParquetRepository
    from src.uploaders.gcs import GCSUploader

from src.fetchers.yfinance import YFinanceFetcher
from src.providers.krx import KRXProvider
from src.qseed.config import AppConfig, get_config
from src.repositories.duckdb import DuckDBRepository
from src.repositories.parquet import ParquetRepository
from src.uploaders.gcs import GCSUploader
from src.utils.helpers import (
    chunked,
    format_progress,
    format_summary,
    save_list_to_file,
)

type PipelineMode = typing.Literal["full", "incremental"]


@dataclass(slots=True)
class StockPipelineDependencies:
    """파이프라인 의존성 묶음."""

    config: AppConfig | None = None
    provider: KRXProvider | None = None
    fetcher: YFinanceFetcher | None = None
    repository: DuckDBRepository | None = None
    parquet_repository: ParquetRepository | None = None
    uploader: GCSUploader | None = None


@dataclass(slots=True)
class StockPipelineResult:
    """파이프라인 실행 결과."""

    total_attempted: int
    success_tickers: list[str]
    failed_tickers: list[str]
    parquet_files: list[Path]
    ticker_list_path: Path
    no_data_path: Path

    @property
    def success_count(self) -> int:
        return len(self.success_tickers)

    @property
    def failed_count(self) -> int:
        return len(self.failed_tickers)


class StockDataPipeline:
    """KRX 주식 데이터를 수집하고 저장하는 파이프라인."""

    def __init__(self, deps: StockPipelineDependencies | None = None) -> None:
        deps = deps or StockPipelineDependencies()

        self.config = deps.config or get_config()
        self.provider = deps.provider or KRXProvider()
        self.fetcher = deps.fetcher or YFinanceFetcher(period=self.config.stock.download_period)
        self.repository = deps.repository or DuckDBRepository(db_path=self.config.stock.db_path)
        self.parquet_repository = deps.parquet_repository or ParquetRepository(
            base_dir=self.config.stock.base_dir
        )
        self.uploader = deps.uploader or GCSUploader(
            bucket_name=self.config.gcs.bucket_name,
            blob_prefix=self.config.gcs.ticker_blob_prefix,
        )

    def run(self, mode: PipelineMode = "full") -> StockPipelineResult:
        """데이터 수집 파이프라인 실행.

        Args:
            mode: 실행 모드
                - "full": 최초 전체 적재
                - "incremental": 증분 적재(추후 구현)

        Returns:
            파이프라인 실행 결과

        Raises:
            ValueError: 지원하지 않는 mode가 전달된 경우
            NotImplementedError: incremental 모드가 아직 구현되지 않은 경우
        """
        if mode not in {"full", "incremental"}:
            raise ValueError(f"지원하지 않는 실행 모드입니다: {mode}")

        if mode == "incremental":
            raise NotImplementedError(
                "incremental 모드는 아직 구현되지 않았습니다. " "현재는 full 모드만 지원합니다."
            )

        return self._run_full_load()

    def _run_full_load(self) -> StockPipelineResult:
        """최초 전체 적재 모드 실행."""
        self.config.stock.ensure_directories()

        # 1. 티커 목록 획득 및 저장
        tickers = self.provider.get_tickers(max_count=self.config.stock.max_stocks)
        self.provider.save_tickers_to_csv(
            self.config.stock.ticker_list_path,
            max_count=len(tickers),
        )

        parquet_files: list[Path] = []
        success_tickers: set[str] = set()
        attempted_tickers: list[str] = []

        # 2. 저장소 초기화
        self.parquet_repository.reset()

        # 3. 데이터 수집 및 저장
        with self.repository as repo:
            repo.reset_raw_stocks_table()

            for idx, ticker_chunk in enumerate(
                chunked(tickers, self.config.stock.chunk_size),
                start=1,
            ):
                attempted_tickers.extend(ticker_chunk)

                # 데이터 페칭
                fetch_result = self.fetcher.fetch(ticker_chunk)

                # DB 저장
                if not fetch_result.dataframe.empty:
                    repo.insert_dataframe(fetch_result.dataframe)
                    success_tickers.update(fetch_result.success_tickers)

                    # Parquet 저장
                    parquet_path = self.parquet_repository.save(
                        fetch_result.dataframe,
                        filename=f"stocks_{idx:04d}.parquet",
                    )
                    parquet_files.append(parquet_path)

                    # GCS 업로드
                    if self.config.gcs.is_enabled:
                        self.uploader.upload_file(
                            source_file=parquet_path,
                            destination_blob_name=(
                                f"{self.config.gcs.ticker_blob_prefix}/{parquet_path.name}"
                            ),
                        )

                # 진행 상황 출력
                print(
                    format_progress(
                        success=len(success_tickers),
                        failed=len(attempted_tickers) - len(success_tickers),
                        total=len(attempted_tickers),
                    )
                )

                # 대기
                if self.config.stock.sleep_interval > 0:
                    import time

                    time.sleep(self.config.stock.sleep_interval)

        # 4. 결과 정리
        failed_tickers = sorted(set(attempted_tickers) - success_tickers)
        save_list_to_file(failed_tickers, str(self.config.stock.no_data_path))

        print(
            format_summary(
                total_attempted=len(attempted_tickers),
                success_count=len(success_tickers),
                failed_count=len(failed_tickers),
            )
        )

        return StockPipelineResult(
            total_attempted=len(attempted_tickers),
            success_tickers=sorted(success_tickers),
            failed_tickers=failed_tickers,
            parquet_files=parquet_files,
            ticker_list_path=self.config.stock.ticker_list_path,
            no_data_path=self.config.stock.no_data_path,
        )
