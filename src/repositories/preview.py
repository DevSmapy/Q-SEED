"""DuckDB 미리보기/조회용 저장소 모듈."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import duckdb
import pandas as pd


class DuckDBPreviewRepository:
    """DuckDB에 저장된 주식 데이터를 조회하는 저장소."""

    def __init__(self, db_path: Path | str) -> None:
        """DuckDBPreviewRepository 초기화.

        Args:
            db_path: DuckDB 파일 경로
        """
        self.db_path = Path(db_path)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """활성 DuckDB 연결 객체."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self.db_path))
        return self._conn

    def preview_all(self, limit: int = 10) -> pd.DataFrame:
        """전체 데이터 일부 미리보기.

        Args:
            limit: 조회할 행 수

        Returns:
            미리보기 DataFrame
        """
        query = f"""
        SELECT *
        FROM raw_stocks
        ORDER BY Date DESC
        LIMIT {limit}
        """
        return cast(pd.DataFrame, self.conn.execute(query).df())

    def preview_recent(self, limit: int = 20) -> pd.DataFrame:
        """최근 데이터 일부 미리보기.

        Args:
            limit: 조회할 행 수

        Returns:
            최근 데이터 DataFrame
        """
        return self.preview_all(limit=limit)

    def preview_by_ticker(self, ticker: str, limit: int = 20) -> pd.DataFrame:
        """특정 티커의 데이터 미리보기.

        Args:
            ticker: 조회할 티커
            limit: 조회할 행 수

        Returns:
            티커별 데이터 DataFrame
        """
        query = f"""
        SELECT *
        FROM raw_stocks
        WHERE Ticker = '{ticker}'
        ORDER BY Date DESC
        LIMIT {limit}
        """
        return cast(pd.DataFrame, self.conn.execute(query).df())

    def preview_by_date_range(
        self,
        start_date: str,
        end_date: str,
        limit: int = 50,
    ) -> pd.DataFrame:
        """날짜 범위로 데이터 조회.

        Args:
            start_date: 시작일 (예: "2024-01-01")
            end_date: 종료일 (예: "2024-12-31")
            limit: 조회할 최대 행 수

        Returns:
            날짜 범위 데이터 DataFrame
        """
        query = f"""
        SELECT *
        FROM raw_stocks
        WHERE Date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY Date DESC
        LIMIT {limit}
        """
        return cast(pd.DataFrame, self.conn.execute(query).df())

    def get_tickers(self) -> list[str]:
        """저장된 티커 목록 조회.

        Returns:
            티커 목록
        """
        query = """
        SELECT DISTINCT Ticker
        FROM raw_stocks
        ORDER BY Ticker
        """
        df = cast(pd.DataFrame, self.conn.execute(query).df())
        if "Ticker" not in df.columns:
            return []
        return df["Ticker"].astype(str).tolist()

    def get_date_range(self) -> tuple[str | None, str | None]:
        """저장된 데이터의 날짜 범위 조회.

        Returns:
            (최소 날짜, 최대 날짜)
        """
        query = """
        SELECT
            MIN(Date) AS min_date,
            MAX(Date) AS max_date
        FROM raw_stocks
        """
        df = cast(pd.DataFrame, self.conn.execute(query).df())

        if df.empty:
            return None, None

        min_date = df.iloc[0]["min_date"]
        max_date = df.iloc[0]["max_date"]

        return (
            None if pd.isna(min_date) else str(min_date),
            None if pd.isna(max_date) else str(max_date),
        )

    def get_basic_summary(self) -> dict[str, int | str | None]:
        """기본 요약 정보 조회.

        Returns:
            요약 정보 딕셔너리
        """
        count_query = """
        SELECT
            COUNT(*) AS row_count,
            COUNT(DISTINCT Ticker) AS ticker_count
        FROM raw_stocks
        """
        count_df = cast(pd.DataFrame, self.conn.execute(count_query).df())
        min_date, max_date = self.get_date_range()

        if count_df.empty:
            return {
                "row_count": 0,
                "ticker_count": 0,
                "min_date": min_date,
                "max_date": max_date,
            }

        return {
            "row_count": int(count_df.iloc[0]["row_count"]),
            "ticker_count": int(count_df.iloc[0]["ticker_count"]),
            "min_date": min_date,
            "max_date": max_date,
        }

    def find_duplicates(self) -> pd.DataFrame:
        """중복 데이터 조회 (Ticker + Date 기준).

        Returns:
            중복 행 DataFrame
        """
        query = """
        SELECT
            Ticker,
            Date,
            COUNT(*) AS duplicate_count
        FROM raw_stocks
        GROUP BY Ticker, Date
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, Ticker, Date
        """
        return cast(pd.DataFrame, self.conn.execute(query).df())

    def close(self) -> None:
        """DB 연결 종료."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
