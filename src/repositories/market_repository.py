"""시장 지표용 DuckDB 저장소."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import duckdb
import pandas as pd


class MarketRepository:
    """raw_market_series / raw_market_breadth 저장소."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def __enter__(self) -> MarketRepository:
        _ = self.conn
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect(str(self.db_path))
        return self._conn

    def initialize(self) -> None:
        """시장 지표 테이블 생성."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_market_series (
                Date TIMESTAMP,
                series_id TEXT,
                value DOUBLE,
                source TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_market_breadth (
                Date TIMESTAMP,
                Market TEXT,
                advances BIGINT,
                declines BIGINT,
                unchanged BIGINT,
                adr_20d DOUBLE,
                ad_line DOUBLE,
                pct_above_ma20 DOUBLE,
                pct_above_ma200 DOUBLE
            )
            """
        )

    def insert_series(self, dataframe: pd.DataFrame) -> None:
        """시계열 DataFrame을 raw_market_series에 적재."""
        if dataframe.empty:
            return
        required = {"Date", "series_id", "value", "source"}
        missing = required - set(dataframe.columns)
        if missing:
            raise ValueError(f"raw_market_series 필수 컬럼 누락: {sorted(missing)}")

        self.initialize()
        conn = self.conn
        conn.register("df_market_series", dataframe[list(required)])
        try:
            conn.execute("INSERT INTO raw_market_series BY NAME SELECT * FROM df_market_series")
        finally:
            try:
                conn.unregister("df_market_series")
            except duckdb.CatalogException:
                pass

    def insert_breadth(self, dataframe: pd.DataFrame) -> None:
        """breadth DataFrame을 raw_market_breadth에 적재."""
        if dataframe.empty:
            return
        required = {
            "Date",
            "Market",
            "advances",
            "declines",
            "unchanged",
            "adr_20d",
            "ad_line",
            "pct_above_ma20",
            "pct_above_ma200",
        }
        missing = required - set(dataframe.columns)
        if missing:
            raise ValueError(f"raw_market_breadth 필수 컬럼 누락: {sorted(missing)}")

        self.initialize()
        conn = self.conn
        cols = list(required)
        conn.register("df_market_breadth", dataframe[cols])
        try:
            conn.execute("INSERT INTO raw_market_breadth BY NAME SELECT * FROM df_market_breadth")
        finally:
            try:
                conn.unregister("df_market_breadth")
            except duckdb.CatalogException:
                pass

    def deduplicate_series(self) -> None:
        """(series_id, Date) 기준 중복 제거 — 마지막 적재 행 우선."""
        self.initialize()
        self.conn.execute("CHECKPOINT")
        self.conn.execute(
            """
            CREATE TABLE raw_market_series_tmp AS
            SELECT Date, series_id, value, source
            FROM (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY series_id, Date
                           ORDER BY source
                       ) AS row_num
                FROM raw_market_series
            )
            WHERE row_num = 1
            """
        )
        self.conn.execute("DROP TABLE raw_market_series")
        self.conn.execute("ALTER TABLE raw_market_series_tmp RENAME TO raw_market_series")
        self.conn.execute("CHECKPOINT")

    def replace_breadth_for_markets(self, markets: list[str], dataframe: pd.DataFrame) -> None:
        """지정 Market의 breadth를 교체 적재."""
        self.initialize()
        if markets:
            placeholders = ", ".join("?" for _ in markets)
            self.conn.execute(
                f"DELETE FROM raw_market_breadth WHERE Market IN ({placeholders})",
                markets,
            )
        self.insert_breadth(dataframe)
        self.conn.execute("CHECKPOINT")

    def load_stock_closes(self, markets: list[str] | None = None) -> pd.DataFrame:
        """breadth 계산용 Close 시계열 로드."""
        tables = self.conn.execute("SHOW TABLES").fetchall()
        table_names = {str(row[0]) for row in tables}
        if "raw_stocks" not in table_names:
            return pd.DataFrame(columns=["Date", "Ticker", "Market", "Close"])

        if markets:
            placeholders = ", ".join("?" for _ in markets)
            query = f"""
                SELECT Date, Ticker, Market, Close
                FROM raw_stocks
                WHERE Market IN ({placeholders})
                ORDER BY Market, Ticker, Date
            """
            return cast(pd.DataFrame, self.conn.execute(query, markets).df())

        return cast(
            pd.DataFrame,
            self.conn.execute(
                """
                SELECT Date, Ticker, Market, Close
                FROM raw_stocks
                ORDER BY Market, Ticker, Date
                """
            ).df(),
        )

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
