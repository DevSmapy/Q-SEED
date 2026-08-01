"""주식 파이프라인 공백 탐지·복구 헬퍼."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from src.pipelines.stock_types import FetchStoreOptions, StockPipelineResult
from src.repositories.gap_detector import detect_gaps

if TYPE_CHECKING:
    from src.repositories.duckdb_builder import DuckDBRepository


@dataclass(frozen=True, slots=True)
class GapRunContext:
    """공백 탐지·복구에 필요한 경로·허용일."""

    gap_tolerance_days: int
    ticker_list_path: Path
    no_data_path: Path
    markets: list[str] | None = None


def _filter_lagging(lagging: pd.DataFrame, markets: list[str] | None) -> pd.DataFrame:
    if markets is None:
        return lagging
    from src.providers.stock_provider import StockProvider

    for market in markets:
        if market not in StockProvider.MARKETS:
            raise ValueError(f"지원하지 않는 시장입니다: {market}")
    if lagging.empty:
        return lagging
    return lagging[lagging["Market"].isin(markets)].copy()


def run_gap_check(repo: DuckDBRepository, ctx: GapRunContext) -> StockPipelineResult:
    """공백 탐지 리포트만 출력."""
    repo.initialize()
    report = detect_gaps(repo.conn, ctx.gap_tolerance_days)
    lagging = _filter_lagging(report.lagging_tickers, ctx.markets)

    print("\n=== Gap Check Report ===")
    print(f"Tolerance: {ctx.gap_tolerance_days} calendar days (per market)")
    if ctx.markets:
        print(f"Markets filter: {','.join(ctx.markets)}")
    print(f"Lagging tickers: {len(lagging)}")
    if not report.market_summary.empty:
        summary = report.market_summary
        if ctx.markets:
            summary = summary[summary["Market"].isin(ctx.markets)]
        if not summary.empty:
            print("\n[Market summary]")
            print(summary.to_string(index=False))
    if not lagging.empty:
        print("\n[Top 20 lagging tickers]")
        print(lagging.head(20).to_string(index=False))

    return StockPipelineResult(
        total_attempted=0,
        success_tickers=[],
        failed_tickers=lagging["Ticker"].tolist() if not lagging.empty else [],
        parquet_files=[],
        ticker_list_path=ctx.ticker_list_path,
        no_data_path=ctx.no_data_path,
    )


def run_gap_repair_with_repo(
    repo: DuckDBRepository,
    ctx: GapRunContext,
    *,
    end_date: str | None,
    fetch_and_store: Callable[[FetchStoreOptions, DuckDBRepository], StockPipelineResult],
) -> StockPipelineResult:
    """시장별 기준일 대비 뒤처진 티커만 재수집."""
    repo.initialize()
    report = detect_gaps(repo.conn, ctx.gap_tolerance_days)
    lagging = _filter_lagging(report.lagging_tickers, ctx.markets)

    if lagging.empty:
        print("공백 티커 없음 — 복구할 데이터가 없습니다.")
        return StockPipelineResult(
            total_attempted=0,
            success_tickers=[],
            failed_tickers=[],
            parquet_files=[],
            ticker_list_path=ctx.ticker_list_path,
            no_data_path=ctx.no_data_path,
        )

    tickers = lagging["Ticker"].tolist()
    ticker_to_market = dict(zip(lagging["Ticker"], lagging["Market"], strict=True))
    ticker_start_dates = dict(
        zip(
            lagging["Ticker"],
            lagging["last_date"].astype(str),
            strict=True,
        )
    )

    print("\n=== Gap Repair ===")
    print(f"Re-fetching {len(tickers)} lagging tickers")

    return fetch_and_store(
        FetchStoreOptions(
            tickers=tickers,
            ticker_to_market=ticker_to_market,
            ticker_start_dates=ticker_start_dates,
            end_date=end_date,
            parquet_prefix="stocks_gap",
        ),
        repo,
    )
