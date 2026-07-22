"""주식 데이터 수집 파이프라인."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

if typing.TYPE_CHECKING:
    from src.fetchers.yfinance import YFinanceFetcher
    from src.providers.stock_provider import StockProvider
    from src.qseed.config import AppConfig
    from src.repositories.duckdb_builder import DuckDBRepository
    from src.repositories.parquet_writer import ParquetRepository
    from src.uploaders.gcs import GCSUploader

from src.fetchers.yfinance import YFinanceFetcher
from src.pipelines.stock_gap import GapRunContext, run_gap_check, run_gap_repair_with_repo
from src.pipelines.stock_types import (
    FetchStoreOptions,
    PipelineMode,
    PipelineRunOptions,
    StockPipelineResult,
)
from src.providers.stock_provider import StockProvider
from src.qseed.config import AppConfig, get_config
from src.repositories.duckdb_builder import DuckDBRepository
from src.repositories.parquet_writer import ParquetRepository
from src.utils.helpers import (
    chunked,
    cleanup_after_chunk,
    format_progress,
    format_summary,
    save_list_to_file,
)

__all__ = [
    "FetchStoreOptions",
    "PipelineMode",
    "PipelineRunOptions",
    "StockDataPipeline",
    "StockPipelineDependencies",
    "StockPipelineResult",
]


@dataclass(slots=True)
class StockPipelineDependencies:
    """파이프라인 의존성 묶음."""

    config: AppConfig | None = None
    provider: StockProvider | None = None
    fetcher: YFinanceFetcher | None = None
    repository: DuckDBRepository | None = None
    parquet_repository: ParquetRepository | None = None
    uploader: GCSUploader | None = None


class StockDataPipeline:
    """KRX 주식 데이터를 수집하고 저장하는 파이프라인."""

    def __init__(self, deps: StockPipelineDependencies | None = None) -> None:
        deps = deps or StockPipelineDependencies()

        self.config = deps.config or get_config()
        self.provider = deps.provider or StockProvider()
        self.fetcher = deps.fetcher or YFinanceFetcher(
            period=self.config.stock.download_period,
            threads=self.config.stock.yfinance_threads,
        )
        self.repository = deps.repository or DuckDBRepository(db_path=self.config.stock.db_path)
        self.parquet_repository = deps.parquet_repository or ParquetRepository(
            base_dir=self.config.stock.base_dir
        )
        if deps.uploader is not None:
            self.uploader = deps.uploader
        else:
            # google.cloud은 upload 경로에서만 import (lazy)
            from src.uploaders.gcs import GCSUploader

            self.uploader = GCSUploader(
                bucket_name=self.config.gcs.bucket_name,
                blob_prefix=self.config.gcs.ticker_blob_prefix,
            )

    def run(self, options: PipelineRunOptions | None = None) -> StockPipelineResult:
        """데이터 수집 파이프라인 실행."""
        opts = options or PipelineRunOptions()

        if opts.check_gaps_only:
            return self._run_gap_check()

        if opts.repair_gaps:
            return self._run_gap_repair(end_date=opts.end_date)

        if opts.mode not in {"full", "incremental"}:
            raise ValueError(f"지원하지 않는 실행 모드입니다: {opts.mode}")

        if opts.mode == "incremental":
            with self.repository as repo:
                result = self._run_incremental_load(
                    start_date=opts.start_date,
                    end_date=opts.end_date,
                    repo=repo,
                )
                if self.config.stock.auto_repair_gaps and not opts.skip_auto_repair:
                    repair_result = self._run_gap_repair(end_date=opts.end_date, repo=repo)
                    return self._merge_results(result, repair_result)
            return result

        return self._run_full_load()

    def _get_last_date_from_db(self, repo: DuckDBRepository | None = None) -> str | None:
        """데이터베이스에서 가장 최신 날짜를 조회 (레거시 폴백용)."""
        if repo is not None:
            try:
                return repo.get_max_date()
            except Exception:
                return None

        with self.repository as managed_repo:
            try:
                return managed_repo.get_max_date()
            except Exception:
                return None

    def _resolve_chunk_start_date(
        self,
        ticker_chunk: list[str],
        explicit_start_date: str | None,
        repo: DuckDBRepository,
        ticker_start_dates: dict[str, str] | None = None,
    ) -> str | None:
        """청크 내 티커별 마지막 날짜 중 가장 이른 날짜를 시작일로 사용."""
        if explicit_start_date:
            return explicit_start_date

        if ticker_start_dates:
            chunk_dates = [
                ticker_start_dates[ticker]
                for ticker in ticker_chunk
                if ticker in ticker_start_dates
            ]
            if chunk_dates:
                return min(chunk_dates)

        last_dates = repo.get_ticker_last_dates(ticker_chunk)
        if last_dates:
            return min(last_dates.values())

        return repo.get_max_date()

    def _gap_context(self) -> GapRunContext:
        return GapRunContext(
            gap_tolerance_days=self.config.stock.gap_tolerance_days,
            ticker_list_path=self.config.stock.ticker_list_path,
            no_data_path=self.config.stock.no_data_path,
        )

    def _run_gap_check(self) -> StockPipelineResult:
        """공백 탐지 리포트만 출력."""
        self.config.stock.ensure_directories()
        with self.repository as repo:
            return run_gap_check(repo, self._gap_context())

    def _run_gap_repair(
        self,
        end_date: str | None = None,
        *,
        repo: DuckDBRepository | None = None,
    ) -> StockPipelineResult:
        """시장별 기준일 대비 뒤처진 티커만 재수집."""
        self.config.stock.ensure_directories()

        if repo is not None:
            return self._run_gap_repair_with_repo(repo, end_date=end_date)

        with self.repository as managed_repo:
            return self._run_gap_repair_with_repo(managed_repo, end_date=end_date)

    def _run_gap_repair_with_repo(
        self,
        repo: DuckDBRepository,
        *,
        end_date: str | None = None,
    ) -> StockPipelineResult:
        return run_gap_repair_with_repo(
            repo,
            self._gap_context(),
            end_date=end_date,
            fetch_and_store=self._fetch_and_store_with_repo,
        )

    def _fetch_and_store_tickers(
        self,
        options: FetchStoreOptions,
        *,
        repo: DuckDBRepository | None = None,
    ) -> StockPipelineResult:
        """티커 목록을 청크 단위로 수집·저장."""
        if repo is not None:
            return self._fetch_and_store_with_repo(options, repo)

        with self.repository as managed_repo:
            return self._fetch_and_store_with_repo(options, managed_repo)

    def _fetch_and_store_with_repo(
        self,
        options: FetchStoreOptions,
        repo: DuckDBRepository,
    ) -> StockPipelineResult:
        """활성 DuckDB 연결을 사용해 청크 수집·저장."""
        success_tickers: set[str] = set()
        attempted_tickers: list[str] = []
        parquet_files: list[Path] = []

        repo.initialize()

        for idx, ticker_chunk in enumerate(
            chunked(options.tickers, self.config.stock.chunk_size),
            start=1,
        ):
            attempted_tickers.extend(ticker_chunk)
            chunk_start = self._resolve_chunk_start_date(
                ticker_chunk,
                options.explicit_start_date,
                repo,
                options.ticker_start_dates,
            )

            fetch_result = self.fetcher.fetch(
                ticker_chunk,
                ticker_to_market=options.ticker_to_market,
                start_date=chunk_start,
                end_date=options.end_date,
            )

            if not fetch_result.dataframe.empty:
                repo.insert_dataframe(fetch_result.dataframe)
                success_tickers.update(fetch_result.success_tickers)

                from datetime import datetime

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                parquet_path = self.parquet_repository.save(
                    fetch_result.dataframe,
                    filename=f"{options.parquet_prefix}_{timestamp}_{idx:04d}.parquet",
                )
                parquet_files.append(parquet_path)

            print(
                format_progress(
                    success=len(success_tickers),
                    failed=len(attempted_tickers) - len(success_tickers),
                    total=len(attempted_tickers),
                )
            )

            if self.config.stock.sleep_interval > 0:
                import time

                time.sleep(self.config.stock.sleep_interval)

            cleanup_after_chunk()

        repo.deduplicate_raw_stocks()

        self._record_results(attempted_tickers, success_tickers, parquet_files, repo=repo)

        return StockPipelineResult(
            total_attempted=len(attempted_tickers),
            success_tickers=sorted(success_tickers),
            failed_tickers=sorted(set(attempted_tickers) - success_tickers),
            parquet_files=parquet_files,
            ticker_list_path=self.config.stock.ticker_list_path,
            no_data_path=self.config.stock.no_data_path,
        )

    @staticmethod
    def _merge_results(
        primary: StockPipelineResult,
        secondary: StockPipelineResult,
    ) -> StockPipelineResult:
        """증분 적재와 공백 복구 결과 병합."""
        success = sorted(set(primary.success_tickers) | set(secondary.success_tickers))
        attempted = primary.total_attempted + secondary.total_attempted
        failed = sorted(set(primary.failed_tickers) | set(secondary.failed_tickers) - set(success))
        return StockPipelineResult(
            total_attempted=attempted,
            success_tickers=success,
            failed_tickers=failed,
            parquet_files=primary.parquet_files + secondary.parquet_files,
            ticker_list_path=primary.ticker_list_path,
            no_data_path=primary.no_data_path,
        )

    def _run_incremental_load(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        *,
        repo: DuckDBRepository | None = None,
    ) -> StockPipelineResult:
        """증분 적재 모드 실행."""
        self.config.stock.ensure_directories()

        if not start_date:
            last_date = self._get_last_date_from_db(repo)
            if last_date:
                print(f"데이터베이스 전역 최신일 (참고): {last_date}")
                print("청크별 수집 시작일은 티커별 last_date 최솟값을 사용합니다.")
            else:
                print("데이터베이스에 기존 데이터가 없습니다. 전체 수집(full)을 권장합니다.")

        print(f"증분 수집 시작: start_date={start_date or 'per-ticker'}, end_date={end_date}")

        max_per_market = self.config.stock.max_stocks
        tickers_df = self.provider.get_all_tickers(max_per_market=max_per_market)
        tickers = tickers_df["Ticker"].tolist()
        ticker_to_market = dict(zip(tickers_df["Ticker"], tickers_df["Market"], strict=True))

        return self._fetch_and_store_tickers(
            FetchStoreOptions(
                tickers=tickers,
                ticker_to_market=ticker_to_market,
                end_date=end_date,
                parquet_prefix="stocks_inc",
                explicit_start_date=start_date,
            ),
            repo=repo,
        )

    def _record_results(
        self,
        attempted_tickers: list[str],
        success_tickers: set[str],
        parquet_files: list[Path],
        *,
        repo: DuckDBRepository | None = None,
    ) -> None:
        """수집 결과를 파일에 기록."""
        failed_tickers = sorted(set(attempted_tickers) - success_tickers)
        save_list_to_file(failed_tickers, str(self.config.stock.no_data_path))
        save_list_to_file(sorted(success_tickers), str(self.config.stock.completed_data_path))

        # 마지막 수집 날짜 기록
        last_date_str = self._get_last_date_from_db(repo) or "None"
        with open(self.config.stock.last_date_path, "w", encoding="utf-8") as f:
            f.write(last_date_str)

        print(
            format_summary(
                total_attempted=len(attempted_tickers),
                success_count=len(success_tickers),
                failed_count=len(failed_tickers),
            )
        )

    def _run_full_load(self) -> StockPipelineResult:
        """최초 전체 적재 모드 실행."""
        self.config.stock.ensure_directories()

        # 1. 티커 목록 획득 및 저장
        # 사용자가 설정한 max_stocks를 시장당 최대 종목 수로 사용
        max_per_market = self.config.stock.max_stocks
        tickers_df = self.provider.get_all_tickers(max_per_market=max_per_market)
        self.provider.save_tickers_to_csv(
            self.config.stock.ticker_list_path,
            tickers_df,
        )

        tickers = tickers_df["Ticker"].tolist()
        ticker_to_market = dict(zip(tickers_df["Ticker"], tickers_df["Market"]))

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

                # 데이터 페칭 (시장 정보 전달)
                fetch_result = self.fetcher.fetch(ticker_chunk, ticker_to_market=ticker_to_market)

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

                cleanup_after_chunk()

            # 4. 데이터베이스 내 최종 중복 제거
            repo.deduplicate_raw_stocks()
            self._record_results(attempted_tickers, success_tickers, parquet_files, repo=repo)

        return StockPipelineResult(
            total_attempted=len(attempted_tickers),
            success_tickers=sorted(success_tickers),
            failed_tickers=sorted(set(attempted_tickers) - success_tickers),
            parquet_files=parquet_files,
            ticker_list_path=self.config.stock.ticker_list_path,
            no_data_path=self.config.stock.no_data_path,
        )
