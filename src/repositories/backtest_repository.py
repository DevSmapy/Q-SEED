"""DuckDB에서 주가를 로드하고 백테스트 결과를 저장."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import duckdb
import pandas as pd

from src.backtest.export import BacktestRunScope
from src.backtest.strategy import BacktestStrategy
from src.repositories.factor_repository import FactorRepository


@dataclass(frozen=True)
class BacktestTables:
    """DuckDB에 저장할 백테스트 테이블 묶음."""

    run_id: str
    strategy: BacktestStrategy
    scope: BacktestRunScope
    daily_returns: pd.DataFrame
    positions: pd.DataFrame
    summary: pd.DataFrame


class BacktestRepository(FactorRepository):
    """백테스트용 DuckDB 접근 계층 (FactorRepository 확장)."""

    def __init__(self, db_path: Path | str) -> None:
        super().__init__(db_path)

    def __enter__(self) -> BacktestRepository:
        super().__enter__()
        return self

    def save_backtest_tables(self, tables: BacktestTables) -> None:
        """백테스트 결과를 DuckDB 테이블로 저장."""
        conn = self.conn
        daily = tables.daily_returns.copy()
        daily["run_id"] = tables.run_id
        daily["factor_name"] = tables.strategy.factor_name
        daily["position_mode"] = tables.strategy.position_mode
        daily["rebalance_freq"] = tables.strategy.rebalance_freq
        daily["markets"] = _markets_label(tables.scope.markets)

        positions = tables.positions.copy()
        positions["run_id"] = tables.run_id
        positions["factor_name"] = tables.strategy.factor_name
        positions["markets"] = _markets_label(tables.scope.markets)

        summary = tables.summary.copy()
        summary["run_id"] = tables.run_id

        conn.execute("BEGIN TRANSACTION")
        try:
            _replace_run_rows(
                conn,
                table_name="backtest_daily_returns",
                register_name="backtest_daily_df",
                frame=daily,
                run_id=tables.run_id,
            )
            _replace_run_rows(
                conn,
                table_name="backtest_positions",
                register_name="backtest_positions_df",
                frame=positions,
                run_id=tables.run_id,
            )
            _replace_run_rows(
                conn,
                table_name="backtest_summary",
                register_name="backtest_summary_df",
                frame=summary,
                run_id=tables.run_id,
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def list_backtest_runs(self, factor_name: str | None = None) -> pd.DataFrame:
        """저장된 백테스트 실행 목록 조회 (웹 API용)."""
        if factor_name is None:
            query = "SELECT * FROM backtest_summary ORDER BY run_id DESC"
            return cast(pd.DataFrame, self.conn.execute(query).df())
        query = """
            SELECT * FROM backtest_summary
            WHERE factor_name = ?
            ORDER BY run_id DESC
        """
        return cast(pd.DataFrame, self.conn.execute(query, [factor_name]).df())


def _replace_run_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    table_name: str,
    register_name: str,
    frame: pd.DataFrame,
    run_id: str,
) -> None:
    """단일 run_id 행을 트랜잭션 내에서 교체 (INSERT BY NAME)."""
    conn.register(register_name, frame)
    try:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} AS
            SELECT * FROM {register_name} WHERE 1 = 0
            """
        )
        conn.execute(f"DELETE FROM {table_name} WHERE run_id = ?", [run_id])
        if not frame.empty:
            conn.execute(
                f"""
                INSERT INTO {table_name} BY NAME
                SELECT * FROM {register_name}
                """
            )
    finally:
        conn.unregister(register_name)


def _markets_label(markets: list[str] | None) -> str | None:
    if not markets:
        return None
    return ",".join(sorted(markets))
