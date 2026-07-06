"""티커별 데이터 공백 감지."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import duckdb
import pandas as pd

from src.repositories.duckdb_builder import DuckDBRepository


@dataclass(frozen=True)
class GapReport:
    """공백 감지 결과."""

    lagging_tickers: pd.DataFrame
    market_summary: pd.DataFrame

    @property
    def lagging_count(self) -> int:
        return len(self.lagging_tickers)


def detect_gaps(conn: duckdb.DuckDBPyConnection, tolerance_days: int = 5) -> GapReport:
    """기존 DuckDB 연결에서 시장별 공백 티커를 탐지."""
    lagging = cast(
        pd.DataFrame,
        conn.execute(
            """
            WITH market_max AS (
                SELECT Market, MAX(Date) AS market_max_date
                FROM raw_stocks
                GROUP BY Market
            ),
            ticker_last AS (
                SELECT Ticker, Market, MAX(Date) AS last_date
                FROM raw_stocks
                GROUP BY Ticker, Market
            )
            SELECT
                t.Ticker,
                t.Market,
                CAST(t.last_date AS DATE) AS last_date,
                CAST(m.market_max_date AS DATE) AS market_max_date,
                date_diff(
                    'day',
                    CAST(t.last_date AS DATE),
                    CAST(m.market_max_date AS DATE)
                ) AS lag_days
            FROM ticker_last t
            INNER JOIN market_max m ON t.Market = m.Market
            WHERE date_diff(
                'day',
                CAST(t.last_date AS DATE),
                CAST(m.market_max_date AS DATE)
            ) > ?
            ORDER BY lag_days DESC, t.Market, t.Ticker
            """,
            [tolerance_days],
        ).df(),
    )

    summary = cast(
        pd.DataFrame,
        conn.execute(
            """
            WITH market_max AS (
                SELECT Market, MAX(Date) AS market_max_date
                FROM raw_stocks
                GROUP BY Market
            ),
            ticker_last AS (
                SELECT Ticker, Market, MAX(Date) AS last_date
                FROM raw_stocks
                GROUP BY Ticker, Market
            )
            SELECT
                mm.Market,
                CAST(mm.market_max_date AS DATE) AS market_max_date,
                COUNT(tl.Ticker) AS total_tickers,
                COUNT(*) FILTER (
                    WHERE date_diff(
                        'day',
                        CAST(tl.last_date AS DATE),
                        CAST(mm.market_max_date AS DATE)
                    ) > ?
                ) AS lagging_tickers
            FROM market_max mm
            LEFT JOIN ticker_last tl ON mm.Market = tl.Market
            GROUP BY mm.Market, mm.market_max_date
            ORDER BY mm.Market
            """,
            [tolerance_days],
        ).df(),
    )

    return GapReport(lagging_tickers=lagging, market_summary=summary)


class GapDetector:
    """시장별 기준일 대비 뒤처진 티커를 탐지 (독립 실행용)."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def detect(self, tolerance_days: int = 5) -> GapReport:
        """별도 연결을 열어 공백 티커를 탐지 (--check-gaps 등 단독 실행)."""
        with DuckDBRepository(self.db_path) as repo:
            return detect_gaps(repo.conn, tolerance_days)
