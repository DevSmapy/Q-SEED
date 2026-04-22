"""DuckDB 저장소 모듈."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import duckdb
import pandas as pd


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

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """활성 DuckDB 연결 객체."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self.db_path))
        return self._conn

    def initialize(self) -> None:
        """기본 테이블 생성."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_stocks (
                Date TIMESTAMP,
                Ticker TEXT,
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

    def insert_dataframe(self, dataframe: pd.DataFrame) -> None:
        """DataFrame을 raw_stocks 테이블에 적재.

        Args:
            dataframe: 적재할 주가 데이터 DataFrame
        """
        if dataframe.empty:
            return

        self.conn.register("df_to_insert", dataframe)
        try:
            self.conn.execute("INSERT INTO raw_stocks SELECT * FROM df_to_insert")
        finally:
            self.conn.unregister("df_to_insert")

    def fetch_all(self) -> pd.DataFrame:
        """저장된 전체 데이터 조회."""
        return cast(pd.DataFrame, self.conn.execute("SELECT * FROM raw_stocks").df())

    def close(self) -> None:
        """DB 연결 종료."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
