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
        """팩터 분석 결과를 DuckDB에 저장 (동일 factor_name 행만 교체)."""
        conn = self._repo.conn
        factor_name = tables.factor_name

        values = tables.factor_values.copy()
        values["factor_name"] = factor_name
        _replace_factor_rows(
            conn,
            table_name="factor_values",
            register_name="factor_values_df",
            frame=values,
            factor_name=factor_name,
        )

        ic_daily = tables.ic_daily.copy()
        ic_daily["factor_name"] = factor_name
        _replace_factor_rows(
            conn,
            table_name="factor_ic_daily",
            register_name="ic_daily_df",
            frame=ic_daily,
            factor_name=factor_name,
        )

        ic_summary = tables.ic_summary.copy()
        if "factor_name" not in ic_summary.columns:
            ic_summary["factor_name"] = factor_name
        _replace_factor_rows(
            conn,
            table_name="factor_ic_summary",
            register_name="ic_summary_df",
            frame=ic_summary,
            factor_name=factor_name,
        )

        quintile_returns = tables.quintile_returns.copy()
        quintile_returns["factor_name"] = factor_name
        _replace_factor_rows(
            conn,
            table_name="factor_quintile_returns",
            register_name="quintile_returns_df",
            frame=quintile_returns,
            factor_name=factor_name,
        )

        quintile_summary = tables.quintile_summary.copy()
        if "factor_name" not in quintile_summary.columns:
            quintile_summary["factor_name"] = factor_name
        _replace_factor_rows(
            conn,
            table_name="factor_quintile_summary",
            register_name="quintile_summary_df",
            frame=quintile_summary,
            factor_name=factor_name,
        )


def _replace_factor_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    table_name: str,
    register_name: str,
    frame: pd.DataFrame,
    factor_name: str,
) -> None:
    """단일 factor_name 행을 교체 (백테스트 run_id 패턴과 동일)."""
    conn.register(register_name, frame)
    try:
        existing = cast(
            list[tuple[str]],
            conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main' AND table_name = ?
                """,
                [table_name],
            ).fetchall(),
        )
        if existing:
            columns = [
                str(row[0])
                for row in cast(
                    list[tuple[object, ...]],
                    conn.execute(f"DESCRIBE {table_name}").fetchall(),
                )
            ]
            if "factor_name" not in columns:
                # 레거시 CREATE OR REPLACE 스키마 → 한 번 버리고 다중 팩터 스키마로 전환
                conn.execute(f"DROP TABLE {table_name}")
                existing = []

        if not existing:
            conn.execute(
                f"""
                CREATE TABLE {table_name} AS
                SELECT * FROM {register_name} WHERE 1 = 0
                """
            )

        conn.execute(f"DELETE FROM {table_name} WHERE factor_name = ?", [factor_name])
        if not frame.empty:
            conn.execute(
                f"""
                INSERT INTO {table_name} BY NAME
                SELECT * FROM {register_name}
                """
            )
    finally:
        conn.unregister(register_name)
