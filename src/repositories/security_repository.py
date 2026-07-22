"""종목 섹터·업종 메타데이터 DuckDB 저장소."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import duckdb
import pandas as pd

from src.repositories.duckdb_conn import connect


class SecurityRepository:
    """raw_security_metadata 저장소."""

    TABLE = "raw_security_metadata"

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    def __enter__(self) -> SecurityRepository:
        _ = self.conn
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = connect(self.db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def initialize(self) -> None:
        """Contract DDL — docs/security-metadata-contract.md."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_security_metadata (
                Ticker VARCHAR NOT NULL,
                Market VARCHAR NOT NULL,
                company_name VARCHAR,
                quote_type VARCHAR,
                sector_raw VARCHAR,
                sector VARCHAR NOT NULL,
                industry_raw VARCHAR,
                industry VARCHAR,
                sector_key VARCHAR,
                industry_key VARCHAR,
                country VARCHAR,
                currency VARCHAR,
                sector_source VARCHAR NOT NULL,
                sector_status VARCHAR NOT NULL,
                sector_status_reason VARCHAR,
                as_of DATE NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                PRIMARY KEY (Ticker, Market)
            )
            """
        )

    def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        """(Ticker, Market) 기준 upsert."""
        if not rows:
            return 0
        self.initialize()
        frame = pd.DataFrame(rows)
        conn = self.conn
        conn.register("df_security_meta", frame)
        try:
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute(
                    f"""
                    DELETE FROM {self.TABLE}
                    WHERE (Ticker, Market) IN (
                        SELECT Ticker, Market FROM df_security_meta
                    )
                    """
                )
                conn.execute(f"INSERT INTO {self.TABLE} BY NAME SELECT * FROM df_security_meta")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        finally:
            try:
                conn.unregister("df_security_meta")
            except duckdb.CatalogException:
                pass
        return len(rows)

    def load_universe_from_db(self) -> pd.DataFrame:
        """raw_stocks distinct (Ticker, Market)."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_stocks (
                Date TIMESTAMP, Ticker VARCHAR, Market VARCHAR,
                Open DOUBLE, High DOUBLE, Low DOUBLE, Close DOUBLE,
                Volume BIGINT, Dividends DOUBLE, Split DOUBLE
            )
            """
        )
        return cast(
            pd.DataFrame,
            self.conn.execute(
                """
                SELECT DISTINCT Ticker, Market
                FROM raw_stocks
                ORDER BY Market, Ticker
                """
            ).df(),
        )

    @staticmethod
    def load_universe_from_csv(csv_path: Path) -> pd.DataFrame:
        """krx_list.csv 등 Ticker, Market CSV."""
        if not csv_path.exists():
            return pd.DataFrame(columns=["Ticker", "Market"])
        frame = pd.read_csv(csv_path)
        if "Ticker" not in frame.columns or "Market" not in frame.columns:
            msg = f"티커 CSV에 Ticker, Market 컬럼 필요: {csv_path}"
            raise ValueError(msg)
        return frame[["Ticker", "Market"]].drop_duplicates()

    def resolve_universe(
        self,
        *,
        ticker_list_path: Path,
        prefer_db: bool = True,
    ) -> list[tuple[str, str]]:
        """DB 또는 CSV에서 유니버스 목록."""
        if prefer_db and self.db_path.exists():
            db_uni = self.load_universe_from_db()
            if not db_uni.empty:
                pairs: list[tuple[str, str]] = [
                    (str(row.Ticker), str(row.Market)) for row in db_uni.itertuples(index=False)
                ]
                return pairs
        csv_uni = self.load_universe_from_csv(ticker_list_path)
        if csv_uni.empty:
            return []
        return [(str(row.Ticker), str(row.Market)) for row in csv_uni.itertuples(index=False)]
