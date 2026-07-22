"""DuckDB 저장소 모듈."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import duckdb
import pandas as pd

from src.repositories.duckdb_conn import connect


def _format_date_value(value: object) -> str:
    if hasattr(value, "strftime"):
        return str(value.strftime("%Y-%m-%d"))
    return str(value).split(" ")[0]


class DuckDBRepository:
    """주식 데이터용 DuckDB 저장소."""

    def __init__(self, db_path: Path | str) -> None:
        """DuckDBRepository 초기화.

        Args:
            db_path: DuckDB 파일 경로
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def __enter__(self) -> DuckDBRepository:
        """컨텍스트 매니저 진입."""
        _ = self.conn
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """컨텍스트 매니저 종료."""
        self.close()

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """활성 DuckDB 연결 객체."""
        if self._conn is None:
            self._conn = connect(self.db_path)
        return self._conn

    def ensure_database_file(self) -> None:
        """DuckDB 파일 생성과 연결을 보장."""
        _ = self.conn

    def initialize(self) -> None:
        """기본 테이블 생성."""
        self.ensure_database_file()
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_stocks (
                Date TIMESTAMP,
                Ticker TEXT,
                Market TEXT,
                Open DOUBLE,
                High DOUBLE,
                Low DOUBLE,
                Close DOUBLE,
                Volume BIGINT,
                Dividends DOUBLE,
                Split DOUBLE
            )
            """
        )

    def reset_raw_stocks_table(self) -> None:
        """raw_stocks 테이블을 초기화하고 다시 생성."""
        self.ensure_database_file()
        self.conn.execute("DROP TABLE IF EXISTS raw_stocks")
        self.initialize()

    def insert_dataframe(self, dataframe: pd.DataFrame) -> None:
        """DataFrame을 raw_stocks 테이블에 적재.

        Args:
            dataframe: 적재할 주가 데이터 DataFrame
        """
        if dataframe.empty:
            return

        conn = self.conn
        conn.register("df_to_insert", dataframe)
        try:
            conn.execute("INSERT INTO raw_stocks BY NAME SELECT * FROM df_to_insert")
        finally:
            try:
                conn.unregister("df_to_insert")
            except duckdb.CatalogException:
                pass

    def checkpoint(self) -> None:
        """WAL을 메인 DB 파일로 플러시하여 열린 파일 디스크립터를 줄임."""
        self.ensure_database_file()
        self.conn.execute("CHECKPOINT")

    def deduplicate_raw_stocks(self) -> None:
        """raw_stocks 테이블의 중복 데이터를 제거 (Ticker, Date 기준).

        프라이머리 키가 없는 상태에서 (Ticker, Date)가 동일한 행들 중
        하나만 남기고 삭제합니다. 최신 데이터(Market 정보가 있는 등)를 우선순위로 둘 수 있도록
        정렬 기준을 정교화합니다.
        """
        self.ensure_database_file()
        # 대량 청크 적재 후 WAL 정리 — FD 부족 시 커밋 실패 방지
        self.conn.execute("CHECKPOINT")
        # DuckDB에서 중복 제거를 위한 효율적인 방법:
        # 1. 고유한 행만 선택하여 임시 테이블 생성
        # 2. 원본 테이블 교체
        # ORDER BY에서 Market을 추가하여 Unknown이 아닌 실제 시장 정보를 우선하도록 함
        self.conn.execute(
            """
            CREATE TABLE raw_stocks_tmp AS
            SELECT Date, Ticker, Market, Open, High, Low, Close, Volume, Dividends, Split
            FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY Ticker, Date
                           ORDER BY CASE WHEN Market = 'Unknown' THEN 1 ELSE 0 END, Market
                       ) as row_num
                FROM raw_stocks
            )
            WHERE row_num = 1;
            """
        )
        self.conn.execute("DROP TABLE raw_stocks")
        self.conn.execute("ALTER TABLE raw_stocks_tmp RENAME TO raw_stocks")
        self.conn.execute("CHECKPOINT")
        print("데이터베이스 내 중복 데이터 제거 완료.")

    def get_max_date(self) -> str | None:
        """raw_stocks 테이블의 최신 거래일(YYYY-MM-DD)."""
        self.ensure_database_file()
        res = self.conn.execute("SELECT MAX(Date) FROM raw_stocks").fetchone()
        if not res or res[0] is None:
            return None
        return _format_date_value(res[0])

    def get_ticker_last_dates(self, tickers: list[str]) -> dict[str, str]:
        """티커별 DB 내 마지막 거래일(YYYY-MM-DD) 조회."""
        if not tickers:
            return {}

        placeholders = ", ".join("?" for _ in tickers)
        query = f"""
            SELECT Ticker, MAX(Date) AS last_date
            FROM raw_stocks
            WHERE Ticker IN ({placeholders})
            GROUP BY Ticker
        """
        rows = self.conn.execute(query, tickers).fetchall()
        result: dict[str, str] = {}
        for ticker, last_date in rows:
            if last_date is None:
                continue
            result[str(ticker)] = _format_date_value(last_date)
        return result

    def fetch_all(self) -> pd.DataFrame:
        """저장된 전체 데이터 조회."""
        self.ensure_database_file()
        return cast(pd.DataFrame, self.conn.execute("SELECT * FROM raw_stocks").df())

    def close(self) -> None:
        """DB 연결 종료."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
