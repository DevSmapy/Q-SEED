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
from src.providers.stock_provider import StockProvider
from src.qseed.config import AppConfig, get_config
from src.repositories.duckdb_builder import DuckDBRepository
from src.repositories.parquet_writer import ParquetRepository
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
    provider: StockProvider | None = None
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
        self.provider = deps.provider or StockProvider()
        self.fetcher = deps.fetcher or YFinanceFetcher(period=self.config.stock.download_period)
        self.repository = deps.repository or DuckDBRepository(db_path=self.config.stock.db_path)
        self.parquet_repository = deps.parquet_repository or ParquetRepository(
            base_dir=self.config.stock.base_dir
        )
        self.uploader = deps.uploader or GCSUploader(
            bucket_name=self.config.gcs.bucket_name,
            blob_prefix=self.config.gcs.ticker_blob_prefix,
        )

    def run(
        self,
        mode: PipelineMode = "full",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> StockPipelineResult:
        """데이터 수집 파이프라인 실행.

        Args:
            mode: 실행 모드
                - "full": 최초 전체 적재
                - "incremental": 증분 적재
            start_date: 시작 날짜 (incremental 모드에서 사용)
            end_date: 종료 날짜 (incremental 모드에서 사용)

        Returns:
            파이프라인 실행 결과

        Raises:
            ValueError: 지원하지 않는 mode가 전달된 경우
        """
        if mode not in {"full", "incremental"}:
            raise ValueError(f"지원하지 않는 실행 모드입니다: {mode}")

        if mode == "incremental":
            return self._run_incremental_load(start_date=start_date, end_date=end_date)

        return self._run_full_load()

    def _get_last_date_from_db(self) -> str | None:
        """데이터베이스에서 가장 최신 날짜를 조회."""
        with self.repository as repo:
            try:
                query = "SELECT MAX(Date) FROM raw_stocks"
                res = repo.conn.execute(query).fetchone()
                if res and res[0]:
                    # DuckDB TIMESTAMP는 datetime 객체로 반환될 수 있음
                    val = res[0]
                    if hasattr(val, "strftime"):
                        return str(val.strftime("%Y-%m-%d"))
                    return str(val).split(" ")[0]  # "2024-01-01 00:00:00" -> "2024-01-01"
                return None
            except Exception:
                return None

    def _run_incremental_load(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> StockPipelineResult:
        """증분 적재 모드 실행."""
        self.config.stock.ensure_directories()

        # 1. 시작 날짜 결정
        if not start_date:
            last_date = self._get_last_date_from_db()
            if last_date:
                # 다음 날부터 수집하기 위해 시작 날짜 조정 로직이 필요할 수 있으나,
                # yfinance 'start'는 포함(inclusive)이므로 중복 제거를 믿고
                # 그대로 사용하거나 +1일 처리
                # 여기서는 중복 제거가 있으므로 안전하게 last_date를 그대로 사용
                start_date = last_date
                print(f"데이터베이스에서 찾은 마지막 날짜: {start_date}")
            else:
                print("데이터베이스에 기존 데이터가 없습니다. 전체 수집(full)을 권장합니다.")

        print(f"증분 수집 시작: start_date={start_date}, end_date={end_date}")

        # 2. 티커 목록 획득
        max_per_market = self.config.stock.max_stocks
        tickers_df = self.provider.get_all_tickers(max_per_market=max_per_market)
        tickers = tickers_df["Ticker"].tolist()
        ticker_to_market = dict(zip(tickers_df["Ticker"], tickers_df["Market"]))

        success_tickers: set[str] = set()
        attempted_tickers: list[str] = []
        parquet_files: list[Path] = []

        # 3. 데이터 수집 및 저장
        with self.repository as repo:
            repo.initialize()  # 테이블이 없으면 생성

            for idx, ticker_chunk in enumerate(
                chunked(tickers, self.config.stock.chunk_size),
                start=1,
            ):
                attempted_tickers.extend(ticker_chunk)

                # 데이터 페칭
                fetch_result = self.fetcher.fetch(
                    ticker_chunk,
                    ticker_to_market=ticker_to_market,
                    start_date=start_date,
                    end_date=end_date,
                )

                # DB 저장
                if not fetch_result.dataframe.empty:
                    repo.insert_dataframe(fetch_result.dataframe)
                    success_tickers.update(fetch_result.success_tickers)

                    # Parquet 저장 (증분용 파일명)
                    from datetime import datetime

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    parquet_path = self.parquet_repository.save(
                        fetch_result.dataframe,
                        filename=f"stocks_inc_{timestamp}_{idx:04d}.parquet",
                    )
                    parquet_files.append(parquet_path)

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

            # 4. 데이터베이스 내 최종 중복 제거 (증분 적재 시 필수)
            repo.deduplicate_raw_stocks()

        # 5. 결과 기록 및 반환
        self._record_results(attempted_tickers, success_tickers, parquet_files)

        return StockPipelineResult(
            total_attempted=len(attempted_tickers),
            success_tickers=sorted(success_tickers),
            failed_tickers=sorted(set(attempted_tickers) - success_tickers),
            parquet_files=parquet_files,
            ticker_list_path=self.config.stock.ticker_list_path,
            no_data_path=self.config.stock.no_data_path,
        )

    def _record_results(
        self,
        attempted_tickers: list[str],
        success_tickers: set[str],
        parquet_files: list[Path],
    ) -> None:
        """수집 결과를 파일에 기록."""
        failed_tickers = sorted(set(attempted_tickers) - success_tickers)
        save_list_to_file(failed_tickers, str(self.config.stock.no_data_path))
        save_list_to_file(sorted(success_tickers), str(self.config.stock.completed_data_path))

        # 마지막 수집 날짜 기록
        last_date_str = self._get_last_date_from_db() or "None"
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

            # 4. 데이터베이스 내 최종 중복 제거
            repo.deduplicate_raw_stocks()

        # 4. 결과 정리
        self._record_results(attempted_tickers, success_tickers, parquet_files)

        return StockPipelineResult(
            total_attempted=len(attempted_tickers),
            success_tickers=sorted(success_tickers),
            failed_tickers=sorted(set(attempted_tickers) - success_tickers),
            parquet_files=parquet_files,
            ticker_list_path=self.config.stock.ticker_list_path,
            no_data_path=self.config.stock.no_data_path,
        )
