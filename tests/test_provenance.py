"""provenance 수집·경로 정규화 회귀 테스트."""

from __future__ import annotations

from pathlib import Path

import duckdb

from src.backtest.export import (
    SCHEMA_VERSION,
    BacktestManifestContext,
    BacktestRunScope,
    build_manifest,
)
from src.backtest.metrics import BacktestMetrics
from src.backtest.strategy import BacktestStrategy
from src.utils.provenance import (
    collect_data_provenance,
    collect_provenance,
    sanitize_db_path,
)

SAMPLE_ROW_COUNT = 2
SAMPLE_MIN_DATE = "2024-01-02 00:00:00"
SAMPLE_MAX_DATE = "2024-01-03 00:00:00"


def _sample_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "stocks.db"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        create table raw_stocks as
        select
            timestamp '2024-01-02' as Date,
            'AAA' as Ticker,
            'KOSPI' as Market,
            100.0 as Open,
            101.0 as High,
            99.0 as Low,
            100.5 as Close,
            1000::bigint as Volume,
            0.0 as Dividends,
            0.0 as Split
        union all
        select
            timestamp '2024-01-03',
            'AAA',
            'KOSPI',
            100.5,
            102.0,
            100.0,
            101.0,
            1100,
            0.0,
            0.0
        """
    )
    conn.close()
    return db_path


def test_sanitize_db_path_prefers_relative(tmp_path: Path) -> None:
    db = tmp_path / "data" / "stocks.db"
    db.parent.mkdir()
    db.write_bytes(b"x")
    assert sanitize_db_path(db, cwd=tmp_path) == "data/stocks.db"


def test_sanitize_db_path_falls_back_to_name(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere" / "secret.db"
    outside.parent.mkdir()
    outside.write_bytes(b"x")
    other_cwd = tmp_path / "project"
    other_cwd.mkdir()
    assert sanitize_db_path(outside, cwd=other_cwd) == "secret.db"


def test_collect_data_provenance_reads_fingerprint(tmp_path: Path) -> None:
    db_path = _sample_db(tmp_path)
    data = collect_data_provenance(db_path, cwd=tmp_path)
    assert data["status"] == "ok"
    assert data["row_count"] == SAMPLE_ROW_COUNT
    assert data["bytes"] is not None and data["bytes"] > 0
    assert data["min_date"] == SAMPLE_MIN_DATE
    assert data["max_date"] == SAMPLE_MAX_DATE
    assert data["db_path"] == "stocks.db"


def test_collect_provenance_survives_missing_db(tmp_path: Path) -> None:
    missing = tmp_path / "nope.db"
    payload = collect_provenance(missing, cwd=tmp_path)
    assert payload["data"]["status"] == "missing"
    assert "git_sha" in payload["code"]
    assert "package_version" in payload["code"]


def test_build_manifest_includes_provenance(tmp_path: Path) -> None:
    db_path = _sample_db(tmp_path)
    metrics = BacktestMetrics(
        factor_name="reversal_5d",
        position_mode="long_short",
        rebalance_freq=21,
        total_return=0.1,
        cagr=0.05,
        max_drawdown=-0.2,
        sharpe=0.5,
        sortino=0.6,
        calmar=0.25,
        win_rate=0.55,
        benchmark_total_return=0.08,
        benchmark_cagr=0.04,
        excess_cagr=0.01,
        trading_days=10,
        rebalance_count=2,
    )
    strategy = BacktestStrategy(
        factor_name="reversal_5d",
        position_mode="long_short",
        long_quintile=5,
        short_quintile=1,
        rebalance_freq=21,
        min_observations=30,
        transaction_cost_bps=0.0,
        initial_capital=100_000.0,
    )
    manifest = build_manifest(
        BacktestManifestContext(
            run_id="reversal_5d_test",
            strategy=strategy,
            scope=BacktestRunScope(
                markets=["KOSPI"],
                start_date=None,
                end_date=None,
                ticker_count=1,
                trading_days=10,
                rebalance_count=2,
            ),
            metrics=metrics,
            artifacts={"manifest": "manifest.json"},
            export_format="parquet",
            db_path=db_path,
        )
    )
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert SCHEMA_VERSION == "1.1"
    assert manifest["provenance"]["data"]["row_count"] == SAMPLE_ROW_COUNT
    assert "code" in manifest["provenance"]
