"""DuckDB에서 주가를 로드하고 백테스트 결과를 저장."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

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
        conn.register("backtest_daily_df", daily)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_daily_returns AS
            SELECT * FROM backtest_daily_df WHERE 1 = 0
            """
        )
        conn.execute("DELETE FROM backtest_daily_returns WHERE run_id = ?", [tables.run_id])
        conn.execute(
            """
            INSERT INTO backtest_daily_returns
            SELECT * FROM backtest_daily_df
            """
        )

        positions = tables.positions.copy()
        positions["run_id"] = tables.run_id
        positions["factor_name"] = tables.strategy.factor_name
        positions["markets"] = _markets_label(tables.scope.markets)
        conn.register("backtest_positions_df", positions)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_positions AS
            SELECT * FROM backtest_positions_df WHERE 1 = 0
            """
        )
        conn.execute("DELETE FROM backtest_positions WHERE run_id = ?", [tables.run_id])
        conn.execute(
            """
            INSERT INTO backtest_positions
            SELECT * FROM backtest_positions_df
            """
        )

        summary = tables.summary.copy()
        summary["run_id"] = tables.run_id
        conn.register("backtest_summary_df", summary)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_summary AS
            SELECT * FROM backtest_summary_df WHERE 1 = 0
            """
        )
        conn.execute("DELETE FROM backtest_summary WHERE run_id = ?", [tables.run_id])
        conn.execute(
            """
            INSERT INTO backtest_summary
            SELECT * FROM backtest_summary_df
            """
        )

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


def _markets_label(markets: list[str] | None) -> str | None:
    if not markets:
        return None
    return ",".join(sorted(markets))
