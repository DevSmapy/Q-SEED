"""Security metadata 수집 파이프라인."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.fetchers.security_metadata import SecurityMetadataFetchResult, fetch_metadata_batch
from src.repositories.security_repository import SecurityRepository

logger = logging.getLogger("qseed")


@dataclass(frozen=True)
class SecurityMetadataRunOptions:
    """메타데이터 수집 옵션."""

    max_tickers: int | None = None
    sleep_seconds: float = 0.3
    equity_only: bool = False
    prefer_db_universe: bool = True


@dataclass(frozen=True)
class SecurityMetadataRunResult:
    """실행 결과."""

    upserted: int
    fetch: SecurityMetadataFetchResult


class SecurityMetadataPipeline:
    """유니버스 로드 → yfinance fetch → DuckDB upsert."""

    def __init__(self, db_path: Path, ticker_list_path: Path) -> None:
        self.db_path = db_path
        self.ticker_list_path = ticker_list_path

    def run(self, options: SecurityMetadataRunOptions | None = None) -> SecurityMetadataRunResult:
        opts = options or SecurityMetadataRunOptions()
        with SecurityRepository(self.db_path) as repo:
            universe = repo.resolve_universe(
                ticker_list_path=self.ticker_list_path,
                prefer_db=opts.prefer_db_universe,
            )
        if not universe:
            msg = "메타데이터 유니버스가 비어 있습니다. stocks.db 또는 krx_list.csv를 확인하세요."
            raise ValueError(msg)

        if opts.max_tickers is not None:
            universe = universe[: opts.max_tickers]

        logger.info("Security metadata: %s tickers to fetch", len(universe))
        fetch_result = fetch_metadata_batch(
            universe,
            sleep_seconds=opts.sleep_seconds,
            equity_only=opts.equity_only,
        )

        with SecurityRepository(self.db_path) as repo:
            upserted = repo.upsert_rows(fetch_result.rows)

        logger.info(
            "Security metadata done: upserted=%s mapped=%s unclassified=%s errors=%s",
            upserted,
            fetch_result.mapped,
            fetch_result.unclassified,
            fetch_result.errors,
        )
        return SecurityMetadataRunResult(upserted=upserted, fetch=fetch_result)
