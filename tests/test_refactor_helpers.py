"""리팩토링 헬퍼·CLI·gap 회귀 테스트."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.pipelines.stock_gap import GapRunContext, run_gap_check, run_gap_repair_with_repo
from src.pipelines.stock_types import FetchStoreOptions, StockPipelineResult
from src.qseed.cli.parser import build_parser
from src.repositories.duckdb_builder import DuckDBRepository
from src.repositories.duckdb_conn import connect, table_exists
from src.utils.labels import markets_label


def test_markets_label() -> None:
    assert markets_label(None) is None
    assert markets_label([]) is None
    assert markets_label(["KOSDAQ", "KOSPI"]) == "KOSDAQ,KOSPI"
    assert markets_label(["KOSPI"]) == "KOSPI"


def test_duckdb_conn_connect_and_table_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "helper.db"
    conn = connect(db_path)
    try:
        assert not table_exists(conn, "raw_stocks")
        conn.execute("CREATE TABLE raw_stocks AS SELECT 1 AS x")
        assert table_exists(conn, "raw_stocks")
    finally:
        conn.close()

    read_conn = connect(db_path, read_only=True)
    try:
        assert table_exists(read_conn, "raw_stocks")
    finally:
        read_conn.close()


def test_cli_build_parser_has_core_flags() -> None:
    parser = build_parser()
    dests = {action.dest for action in parser._actions}
    for flag in (
        "build_db",
        "update_db",
        "check_gaps",
        "run_backtest",
        "run_optimize",
        "run_factor_analysis",
        "run_market_pipeline",
    ):
        assert flag in dests


def test_cli_package_exports_main() -> None:
    from src.qseed.cli import main

    assert callable(main)


def test_cli_module_help_smoke() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.qseed.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0
    assert "--build-db" in result.stdout
    assert "--run-backtest" in result.stdout


def _seed_gap_db(db_path: Path) -> None:
    prices = pd.DataFrame(
        [
            {
                "Date": pd.Timestamp("2024-01-10"),
                "Ticker": "AAA",
                "Market": "TEST",
                "Open": 1.0,
                "High": 1.0,
                "Low": 1.0,
                "Close": 1.0,
                "Volume": 100,
                "Dividends": 0.0,
                "Split": 0.0,
            },
            {
                "Date": pd.Timestamp("2024-01-20"),
                "Ticker": "BBB",
                "Market": "TEST",
                "Open": 1.0,
                "High": 1.0,
                "Low": 1.0,
                "Close": 1.0,
                "Volume": 100,
                "Dividends": 0.0,
                "Split": 0.0,
            },
        ]
    )
    with DuckDBRepository(db_path) as repo:
        repo.initialize()
        repo.conn.register("prices_df", prices)
        repo.conn.execute("INSERT INTO raw_stocks SELECT * FROM prices_df")
        repo.conn.unregister("prices_df")


def test_run_gap_check_reports_lagging(tmp_path: Path) -> None:
    db_path = tmp_path / "gaps.db"
    _seed_gap_db(db_path)
    ctx = GapRunContext(
        gap_tolerance_days=5,
        ticker_list_path=tmp_path / "tickers.txt",
        no_data_path=tmp_path / "no_data.txt",
    )
    with DuckDBRepository(db_path) as repo:
        result = run_gap_check(repo, ctx)

    assert result.failed_tickers == ["AAA"]
    assert result.total_attempted == 0


def test_run_gap_repair_empty_and_callback(tmp_path: Path) -> None:
    ctx = GapRunContext(
        gap_tolerance_days=5,
        ticker_list_path=tmp_path / "tickers.txt",
        no_data_path=tmp_path / "no_data.txt",
    )
    calls: list[FetchStoreOptions] = []

    def fake_fetch(
        options: FetchStoreOptions,
        repo: DuckDBRepository,
    ) -> StockPipelineResult:
        calls.append(options)
        return StockPipelineResult(
            total_attempted=len(options.tickers),
            success_tickers=list(options.tickers),
            failed_tickers=[],
            parquet_files=[],
            ticker_list_path=ctx.ticker_list_path,
            no_data_path=ctx.no_data_path,
        )

    empty_db = tmp_path / "repair_empty.db"
    prices = pd.DataFrame(
        [
            {
                "Date": pd.Timestamp("2024-01-20"),
                "Ticker": "AAA",
                "Market": "TEST",
                "Open": 1.0,
                "High": 1.0,
                "Low": 1.0,
                "Close": 1.0,
                "Volume": 100,
                "Dividends": 0.0,
                "Split": 0.0,
            },
            {
                "Date": pd.Timestamp("2024-01-20"),
                "Ticker": "BBB",
                "Market": "TEST",
                "Open": 1.0,
                "High": 1.0,
                "Low": 1.0,
                "Close": 1.0,
                "Volume": 100,
                "Dividends": 0.0,
                "Split": 0.0,
            },
        ]
    )
    with DuckDBRepository(empty_db) as repo:
        repo.initialize()
        repo.conn.register("prices_df", prices)
        repo.conn.execute("INSERT INTO raw_stocks SELECT * FROM prices_df")
        repo.conn.unregister("prices_df")
        empty = run_gap_repair_with_repo(
            repo,
            ctx,
            end_date=None,
            fetch_and_store=fake_fetch,
        )
    assert empty.total_attempted == 0
    assert calls == []

    lagging_db = tmp_path / "repair_lagging.db"
    _seed_gap_db(lagging_db)
    with DuckDBRepository(lagging_db) as repo:
        repaired = run_gap_repair_with_repo(
            repo,
            ctx,
            end_date="2024-01-21",
            fetch_and_store=fake_fetch,
        )
    assert repaired.success_tickers == ["AAA"]
    assert len(calls) == 1
    assert calls[0].parquet_prefix == "stocks_gap"
    assert calls[0].tickers == ["AAA"]
