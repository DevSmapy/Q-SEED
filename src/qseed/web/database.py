"""DuckDB 기반 웹 검색 저장소 모듈."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


class DuckDBSearchRepository:
    """DuckDB 테이블 검색용 읽기 전용 저장소."""

    def __init__(self, database_path: Path | str, table_name: str) -> None:
        """DuckDBSearchRepository 초기화.

        Args:
            database_path: DuckDB 데이터베이스 파일 경로
            table_name: 검색 대상 테이블명
        """
        self.database_path = Path(database_path)
        self.table_name = table_name

    def list_tables(self) -> list[str]:
        """데이터베이스 내 테이블 목록 조회.

        Returns:
            테이블명 목록
        """
        with self._connect() as conn:
            rows = conn.execute("SHOW TABLES").fetchall()

        return [str(row[0]) for row in rows]

    def describe_table(self) -> list[dict[str, Any]]:
        """검색 대상 테이블 스키마 조회.

        Returns:
            컬럼 정보 목록
        """
        table_identifier = self._quote_identifier(self.table_name)

        with self._connect() as conn:
            result = conn.execute(f"DESCRIBE {table_identifier}")
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()

        return [dict(zip(columns, row, strict=True)) for row in rows]

    def get_summary(self) -> dict[str, Any]:
        """검색 대상 테이블의 기본 요약 정보 조회.

        Returns:
            row_count, ticker_count, min_date, max_date 등의 요약 정보
        """
        table_identifier = self._quote_identifier(self.table_name)

        with self._connect() as conn:
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_identifier}").fetchone()[0]
            ticker_count = conn.execute(
                f"SELECT COUNT(DISTINCT Ticker) FROM {table_identifier}"
            ).fetchone()[0]
            date_range = conn.execute(
                f"SELECT MIN(Date), MAX(Date) FROM {table_identifier}"
            ).fetchone()

        return {
            "table_name": self.table_name,
            "row_count": int(row_count),
            "ticker_count": int(ticker_count),
            "min_date": str(date_range[0]) if date_range[0] else None,
            "max_date": str(date_range[1]) if date_range[1] else None,
        }

    def search(self, keyword: str, limit: int) -> list[dict[str, Any]]:
        """검색어를 사용해 테이블 전체 컬럼을 문자열 검색.

        Args:
            keyword: 검색어
            limit: 최대 반환 행 수

        Returns:
            검색 결과 행 목록
        """
        keyword = keyword.strip()

        with self._connect() as conn:
            searchable_columns = self._get_columns(conn)

            if not searchable_columns:
                return []

            table_identifier = self._quote_identifier(self.table_name)

            if keyword:
                where_clause = " OR ".join(
                    f"CAST({self._quote_identifier(column)} AS VARCHAR) ILIKE ?"
                    for column in searchable_columns
                )
                query = f"""
                    SELECT *
                    FROM {table_identifier}
                    WHERE {where_clause}
                    LIMIT ?
                """
                params: list[Any] = [f"%{keyword}%"] * len(searchable_columns)
                params.append(limit)
                result = conn.execute(query, params)
            else:
                query = f"""
                    SELECT *
                    FROM {table_identifier}
                    LIMIT ?
                """
                result = conn.execute(query, [limit])

            result_columns = [desc[0] for desc in result.description]
            rows = result.fetchall()

        return [dict(zip(result_columns, row, strict=True)) for row in rows]

    def search_by_ticker(self, ticker: str, limit: int) -> list[dict[str, Any]]:
        """Ticker 컬럼 기준으로 데이터 조회.

        Args:
            ticker: 조회할 티커
            limit: 최대 반환 행 수

        Returns:
            티커별 검색 결과
        """
        table_identifier = self._quote_identifier(self.table_name)

        with self._connect() as conn:
            result = conn.execute(
                f"""
                SELECT *
                FROM {table_identifier}
                WHERE Ticker = ?
                ORDER BY Date DESC
                LIMIT ?
                """,
                [ticker, limit],
            )
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()

        return [dict(zip(columns, row, strict=True)) for row in rows]

    def search_by_market(self, market: str, limit: int) -> list[dict[str, Any]]:
        """Market 컬럼 기준으로 데이터 조회.

        Args:
            market: 조회할 시장명
            limit: 최대 반환 행 수

        Returns:
            시장별 검색 결과
        """
        table_identifier = self._quote_identifier(self.table_name)

        with self._connect() as conn:
            result = conn.execute(
                f"""
                SELECT *
                FROM {table_identifier}
                WHERE Market = ?
                ORDER BY Date DESC
                LIMIT ?
                """,
                [market, limit],
            )
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()

        return [dict(zip(columns, row, strict=True)) for row in rows]

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """DuckDB 읽기 전용 연결 생성.

        Returns:
            DuckDB 연결 객체
        """
        return duckdb.connect(str(self.database_path), read_only=True)

    def _get_columns(self, conn: duckdb.DuckDBPyConnection) -> list[str]:
        """테이블 컬럼명 목록 조회.

        Args:
            conn: DuckDB 연결 객체

        Returns:
            컬럼명 목록
        """
        table_identifier = self._quote_identifier(self.table_name)
        rows = conn.execute(f"DESCRIBE {table_identifier}").fetchall()
        return [str(row[0]) for row in rows]

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """SQL identifier를 안전하게 double quote 처리.

        Args:
            identifier: 테이블명 또는 컬럼명

        Returns:
            double quote 처리된 identifier
        """
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'
