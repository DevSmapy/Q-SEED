"""DuckDB 저장소 모듈."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

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
            self._conn = duckdb.connect(str(self.db_path))
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
            # 즉시 커밋 효과를 위해 체크포인트 실행
            conn.execute("CHECKPOINT")
        finally:
            conn.unregister("df_to_insert")

    def fetch_all(self) -> pd.DataFrame:
        """저장된 전체 데이터 조회."""
        self.ensure_database_file()
        return cast(pd.DataFrame, self.conn.execute("SELECT * FROM raw_stocks").df())

    def close(self) -> None:
        """DB 연결 종료."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
