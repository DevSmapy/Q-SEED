"""주식 데이터 수집 파이프라인."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.fetchers.yfinance import FetchResult, YFinanceFetcher
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

    def run(self) -> StockPipelineResult:
        """전체 데이터 수집 파이프라인 실행."""
        self.config.stock.ensure_directories()

        tickers = self.provider.get_tickers(max_count=self.config.stock.max_stocks)
        self.provider.save_tickers_to_csv(
            self.config.stock.ticker_list_path, max_count=len(tickers)
        )

        parquet_files: list[Path] = []
        success_tickers: set[str] = set()
        attempted_tickers: list[str] = []

        self.repository.initialize()

        try:
            for idx, ticker_chunk in enumerate(
                chunked(tickers, self.config.stock.chunk_size), start=1
            ):
                attempted_tickers.extend(ticker_chunk)

                fetch_result = self.fetcher.fetch(ticker_chunk)
                self._store_fetch_result(fetch_result)

                success_tickers.update(fetch_result.success_tickers)

                parquet_path = self.parquet_repository.save(
                    fetch_result.dataframe,
                    filename=f"stocks_{idx:04d}.parquet",
                )
                parquet_files.append(parquet_path)

                failed_count = len(attempted_tickers) - len(success_tickers)
                print(
                    format_progress(
                        success=len(success_tickers),
                        failed=failed_count,
                        total=len(attempted_tickers),
                    )
                )

                if self.config.gcs.is_enabled:
                    self.uploader.upload_file(
                        source_file=parquet_path,
                        destination_blob_name=f"{self.config.gcs.ticker_blob_prefix}/{parquet_path.name}",
                    )

                if self.config.stock.sleep_interval > 0:
                    import time

                    time.sleep(self.config.stock.sleep_interval)
        finally:
            self.repository.close()

        failed_tickers = list(set(attempted_tickers) - success_tickers)
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
            failed_tickers=sorted(failed_tickers),
            parquet_files=parquet_files,
            ticker_list_path=self.config.stock.ticker_list_path,
            no_data_path=self.config.stock.no_data_path,
        )

    def _store_fetch_result(self, result: FetchResult) -> None:
        """수집 결과를 저장소에 반영."""
        if result.dataframe.empty:
            return

        self.repository.insert_dataframe(result.dataframe)
