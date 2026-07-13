"""DuckDB에서 주가 데이터를 로드하고 팩터 분석 결과를 저장."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import duckdb
import pandas as pd

from src.repositories.duckdb_builder import DuckDBRepository


@dataclass(frozen=True)
class FactorAnalysisTables:
    """DuckDB에 저장할 팩터 분석 테이블 묶음."""

    factor_name: str
    factor_values: pd.DataFrame
    ic_daily: pd.DataFrame
    ic_summary: pd.DataFrame
    quintile_returns: pd.DataFrame
    quintile_summary: pd.DataFrame


class FactorRepository:
    """팩터 분석용 DuckDB 접근 계층 (단일 연결 세션)."""

    def __init__(self, db_path: Path | str) -> None:
        self._repo = DuckDBRepository(db_path)

    def __enter__(self) -> FactorRepository:
        self._repo.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        self._repo.__exit__(exc_type, exc_val, exc_tb)

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """활성 DuckDB 연결."""
        return self._repo.conn

    def load_prices(
        self,
        *,
        markets: list[str] | None = None,
        tickers: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """raw_stocks에서 OHLCV 로드."""
        conditions: list[str] = ["Close IS NOT NULL", "Volume IS NOT NULL"]
        params: list[object] = []

        if markets:
            placeholders = ", ".join("?" for _ in markets)
            conditions.append(f"Market IN ({placeholders})")
            params.extend(markets)
        if tickers:
            placeholders = ", ".join("?" for _ in tickers)
            conditions.append(f"Ticker IN ({placeholders})")
            params.extend(tickers)
        if start_date:
            conditions.append("Date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("Date <= ?")
            params.append(end_date)

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT
                Date,
                Ticker,
                Market,
                Open,
                High,
                Low,
                Close,
                Volume
            FROM raw_stocks
            WHERE {where_clause}
            ORDER BY Ticker, Date
        """

        return cast(pd.DataFrame, self._repo.conn.execute(query, params).df())

    def save_analysis_tables(self, tables: FactorAnalysisTables) -> None:
        """팩터 분석 결과를 DuckDB 테이블로 저장."""
        conn = self._repo.conn
        values = tables.factor_values.copy()
        values["factor_name"] = tables.factor_name
        conn.register("factor_values_df", values)
        conn.execute(
            """
            CREATE OR REPLACE TABLE factor_values AS
            SELECT * FROM factor_values_df
            """
        )

        conn.register("ic_daily_df", tables.ic_daily)
        conn.execute(
            """
            CREATE OR REPLACE TABLE factor_ic_daily AS
            SELECT * FROM ic_daily_df
            """
        )

        conn.register("ic_summary_df", tables.ic_summary)
        conn.execute(
            """
            CREATE OR REPLACE TABLE factor_ic_summary AS
            SELECT * FROM ic_summary_df
            """
        )

        conn.register("quintile_returns_df", tables.quintile_returns)
        conn.execute(
            """
            CREATE OR REPLACE TABLE factor_quintile_returns AS
            SELECT * FROM quintile_returns_df
            """
        )

        conn.register("quintile_summary_df", tables.quintile_summary)
        conn.execute(
            """
            CREATE OR REPLACE TABLE factor_quintile_summary AS
            SELECT * FROM quintile_summary_df
            """
        )
