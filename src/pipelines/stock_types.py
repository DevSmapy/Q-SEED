"""주식 파이프라인 공유 타입."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

type PipelineMode = typing.Literal["full", "incremental"]


@dataclass(slots=True)
class PipelineRunOptions:
    """파이프라인 실행 옵션."""

    mode: PipelineMode = "full"
    start_date: str | None = None
    end_date: str | None = None
    repair_gaps: bool = False
    check_gaps_only: bool = False
    skip_auto_repair: bool = False


@dataclass(slots=True)
class FetchStoreOptions:
    """청크 수집·저장 옵션."""

    tickers: list[str]
    ticker_to_market: dict[str, str]
    ticker_start_dates: dict[str, str] | None = None
    end_date: str | None = None
    parquet_prefix: str = "stocks_inc"
    explicit_start_date: str | None = None


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
