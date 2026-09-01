"""Quickstart CLI 범위 해상도와 팩터 lookback 안내."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from src.analysis.runner import _ensure_enough_price_history
from src.factors.registry import get_factor
from src.qseed.cli.commands import (
    StockPipelineCliDefaults,
    _log_stock_pipeline_plan,
    resolve_stock_pipeline_cli,
)
from src.qseed.cli.parser import build_parser

_DEFAULTS = StockPipelineCliDefaults(
    max_stocks=1000,
    period="max",
    chunk_size=100,
    sleep_interval=5.0,
    yfinance_threads=False,
)
_DEMO_MAX_STOCKS = 80
_BUILD_DB_UNLIMITED = 1_000_000


def _prices(tickers: list[str], days: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for offset, day in enumerate(pd.date_range("2024-01-02", periods=days, freq="B")):
        for i, ticker in enumerate(tickers):
            close = 100.0 + i + offset * 0.1
            rows.append(
                {
                    "Date": day,
                    "Ticker": ticker,
                    "Market": "KOSPI",
                    "Open": close,
                    "High": close,
                    "Low": close,
                    "Close": close,
                    "Volume": 1_000_000,
                }
            )
    return pd.DataFrame(rows)


def test_build_db_scope_flags_override_full_universe_preset() -> None:
    args = build_parser().parse_args(
        [
            "--build-db",
            "--market",
            "KOSPI",
            "--max-stocks",
            str(_DEMO_MAX_STOCKS),
            "--download-period",
            "1y",
        ]
    )
    resolved = resolve_stock_pipeline_cli(args, _DEFAULTS)
    assert resolved.mode == "full"
    assert resolved.max_stocks == _DEMO_MAX_STOCKS
    assert resolved.period == "1y"
    assert resolved.markets == ["KOSPI"]


def test_run_stock_pipeline_keeps_explicit_demo_scope() -> None:
    args = build_parser().parse_args(
        [
            "--run-stock-pipeline",
            "--market",
            "KOSPI",
            "--max-stocks",
            str(_DEMO_MAX_STOCKS),
            "--download-period",
            "1y",
        ]
    )
    resolved = resolve_stock_pipeline_cli(args, _DEFAULTS)
    assert resolved.mode == "full"
    assert resolved.max_stocks == _DEMO_MAX_STOCKS
    assert resolved.period == "1y"
    assert resolved.markets == ["KOSPI"]


def test_build_db_without_scope_keeps_full_preset() -> None:
    args = build_parser().parse_args(["--build-db"])
    resolved = resolve_stock_pipeline_cli(args, _DEFAULTS)
    assert resolved.max_stocks == _BUILD_DB_UNLIMITED
    assert resolved.period == "max"
    assert resolved.markets is None


def test_build_db_with_scope_logs_resolved_not_full_universe(
    caplog: pytest.LogCaptureFixture,
) -> None:
    args = build_parser().parse_args(
        [
            "--build-db",
            "--market",
            "KOSPI",
            "--max-stocks",
            str(_DEMO_MAX_STOCKS),
            "--download-period",
            "1y",
        ]
    )
    resolved = resolve_stock_pipeline_cli(args, _DEFAULTS)
    logger = logging.getLogger("qseed.quickstart.test")
    with caplog.at_level(logging.INFO, logger=logger.name):
        _log_stock_pipeline_plan(args, resolved, logger, auto_repair_gaps=True)
    text = "\n".join(caplog.messages)
    assert f"시장별 최대 종목 수: {_DEMO_MAX_STOCKS}" in text
    assert "데이터 수집 기간: 1y" in text
    assert "대상 시장: KOSPI" in text
    assert "모든 지원 시장의 모든 티커" not in text


def test_short_history_rejects_momentum_and_allows_reversal() -> None:
    prices = _prices(["AAA", "BBB"], days=40)
    with pytest.raises(ValueError, match="qseed analyze"):
        _ensure_enough_price_history(prices, get_factor("momentum_12_1"))
    _ensure_enough_price_history(prices, get_factor("reversal_5d"))


def test_root_help_lists_task_commands(capsys: pytest.CaptureFixture[str]) -> None:
    from src.qseed.cli.main import main

    assert main([]) == 0
    out = capsys.readouterr().out
    assert "qseed doctor" in out
    assert "qseed demo" in out
    assert "qseed quickstart" in out
    assert "qseed collect" in out


def test_empty_prices_hint_names_next_commands() -> None:
    from src.qseed import hints

    text = hints.empty_prices()
    assert "qseed demo" in text
    assert "qseed collect" in text
    assert "qseed doctor" in text


def test_unusable_warehouse_hint_names_force_reseed() -> None:
    from src.qseed import hints

    text = hints.unusable_warehouse(Path("data/stocks.db"), "raw_stocks 비어 있음")
    assert "qseed demo --force" in text
    assert "raw_stocks 비어 있음" in text


def test_unknown_command_suggests_demo(capsys: pytest.CaptureFixture[str]) -> None:
    from src.qseed.cli.main import main

    unknown_exit = 2
    assert main(["nope"]) == unknown_exit
    err = capsys.readouterr().err
    assert "qseed demo" in err
    assert "qseed doctor" in err


def test_collect_defaults_to_scoped_kospi() -> None:
    from src.qseed.cli.parser import build_task_parser
    from src.qseed.cli.tasks import collect_to_flag_argv

    args = build_task_parser().parse_args(["collect"])
    argv = collect_to_flag_argv(args)
    assert argv[:3] == ["--run-stock-pipeline", "--max-stocks", "80"]
    assert "--download-period" in argv
    assert "1y" in argv
    assert "KOSPI" in argv


def test_collect_full_uses_build_db() -> None:
    from src.qseed.cli.parser import build_task_parser
    from src.qseed.cli.tasks import collect_to_flag_argv

    args = build_task_parser().parse_args(["collect", "--full"])
    assert collect_to_flag_argv(args) == ["--build-db"]


def test_doctor_warns_when_db_missing(tmp_path: Path) -> None:
    from src.qseed.cli.tasks import collect_doctor_checks, format_doctor_report

    checks = collect_doctor_checks(data_dir=str(tmp_path), cwd=tmp_path)
    by_name = {item.name: item for item in checks}
    assert by_name["stocks.db"].status == "warn"
    assert "qseed demo" in (by_name["stocks.db"].hint or "")
    report = format_doctor_report(checks)
    assert "qseed demo" in report


def test_demo_seed_only_and_analyze_loop(tmp_path: Path) -> None:
    from src.qseed.cli.main import main

    assert main(["demo", "--seed-only", "--data-dir", str(tmp_path)]) == 0
    assert (tmp_path / "stocks.db").is_file()
    assert main(["demo", "--force", "--data-dir", str(tmp_path)]) == 0
    report = tmp_path / "factor_analysis" / "reversal_5d" / "analysis_report.json"
    assert report.is_file()
    assert main(["analyze", "--factor", "momentum_12_1", "--data-dir", str(tmp_path)]) == 1


def _empty_duckdb(path: Path, *, with_empty_raw_stocks: bool) -> None:
    import duckdb

    conn = duckdb.connect(str(path))
    try:
        if with_empty_raw_stocks:
            conn.execute(
                """
                CREATE TABLE raw_stocks (
                    Date TIMESTAMP, Ticker TEXT, Market TEXT,
                    Open DOUBLE, High DOUBLE, Low DOUBLE, Close DOUBLE,
                    Volume BIGINT, Dividends DOUBLE, Split DOUBLE
                )
                """
            )
    finally:
        conn.close()


def test_doctor_marks_schemaless_db_unusable(tmp_path: Path) -> None:
    from src.qseed.cli.tasks import collect_doctor_checks

    _empty_duckdb(tmp_path / "stocks.db", with_empty_raw_stocks=False)
    checks = collect_doctor_checks(data_dir=str(tmp_path), cwd=tmp_path)
    stock = next(item for item in checks if item.name == "stocks.db")
    assert stock.status == "fail"
    assert "qseed demo --force" in (stock.hint or "")


def test_doctor_marks_empty_raw_stocks_unusable(tmp_path: Path) -> None:
    from src.qseed.cli.tasks import collect_doctor_checks

    _empty_duckdb(tmp_path / "stocks.db", with_empty_raw_stocks=True)
    checks = collect_doctor_checks(data_dir=str(tmp_path), cwd=tmp_path)
    stock = next(item for item in checks if item.name == "stocks.db")
    assert stock.status == "fail"
    assert "qseed demo --force" in (stock.hint or "")


def test_demo_refuses_empty_warehouse_without_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from src.qseed.cli.main import main

    _empty_duckdb(tmp_path / "stocks.db", with_empty_raw_stocks=True)
    assert main(["demo", "--data-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "qseed demo --force" in err
    assert not (tmp_path / "factor_analysis").exists()


def test_demo_force_reseeds_empty_warehouse(tmp_path: Path) -> None:
    from src.qseed.cli.main import main

    _empty_duckdb(tmp_path / "stocks.db", with_empty_raw_stocks=True)
    assert main(["demo", "--force", "--seed-only", "--data-dir", str(tmp_path)]) == 0
    from src.qseed.cli.tasks import inspect_warehouse

    inspection = inspect_warehouse(tmp_path / "stocks.db")
    assert inspection.usable
    assert inspection.n_rows > 0
