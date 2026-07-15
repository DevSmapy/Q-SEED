"""팩터 저장소·미리보기·IC 최소 회귀 테스트."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.analysis.ic import compute_forward_returns, compute_ic
from src.optimize.optimizer import equal_weight_map
from src.repositories.factor_repository import FactorAnalysisTables, FactorRepository
from src.repositories.preview import DuckDBPreviewRepository


def _sample_prices() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    for offset, day in enumerate(pd.date_range("2024-01-01", periods=40, freq="B")):
        for i, ticker in enumerate(tickers):
            close = 100.0 + i * 3.0 + offset * (0.5 + i * 0.1)
            rows.append(
                {
                    "Date": day,
                    "Ticker": ticker,
                    "Market": "TEST",
                    "Open": close,
                    "High": close,
                    "Low": close,
                    "Close": close,
                    "Volume": 1_000_000,
                    "Dividends": 0.0,
                    "Split": 0.0,
                }
            )
    return pd.DataFrame(rows)


def test_factor_save_keeps_other_factors(tmp_path: Path) -> None:
    db_path = tmp_path / "stocks.db"
    prices = _sample_prices()

    with FactorRepository(db_path) as repo:
        repo.conn.register("prices_df", prices)
        repo.conn.execute("CREATE TABLE raw_stocks AS SELECT * FROM prices_df")
        repo.conn.unregister("prices_df")

        for name, values in (
            ("factor_a", 1.0),
            ("factor_b", 2.0),
        ):
            dates = sorted(prices["Date"].unique())[20:]
            factor_values = pd.DataFrame(
                [
                    {
                        "Date": d,
                        "Ticker": t,
                        "factor_value": values + i * 0.1,
                    }
                    for d in dates
                    for i, t in enumerate(prices["Ticker"].unique())
                ]
            )
            ic_daily = pd.DataFrame({"Date": dates[:5], "ic": [0.1, 0.2, 0.0, -0.1, 0.05]})
            ic_summary = pd.DataFrame(
                [
                    {
                        "factor_name": name,
                        "forward_horizon": 21,
                        "ic_mean": 0.05,
                        "ic_std": 0.1,
                        "ic_ir": 0.5,
                        "hit_rate": 0.6,
                        "observation_days": 5,
                    }
                ]
            )
            quintile_returns = pd.DataFrame(
                {
                    "Date": dates[:2],
                    "quintile": [1, 5],
                    "mean_forward_return": [0.01, 0.02],
                }
            )
            quintile_summary = pd.DataFrame(
                [
                    {
                        "factor_name": name,
                        "forward_horizon": 21,
                        "long_short_spread": 0.01,
                        "q1_avg_return": 0.01,
                        "q2_avg_return": 0.01,
                        "q3_avg_return": 0.01,
                        "q4_avg_return": 0.01,
                        "q5_avg_return": 0.02,
                    }
                ]
            )
            repo.save_analysis_tables(
                FactorAnalysisTables(
                    factor_name=name,
                    factor_values=factor_values,
                    ic_daily=ic_daily,
                    ic_summary=ic_summary,
                    quintile_returns=quintile_returns,
                    quintile_summary=quintile_summary,
                )
            )

        names = (
            repo.conn.execute("SELECT DISTINCT factor_name FROM factor_ic_summary ORDER BY 1")
            .df()["factor_name"]
            .tolist()
        )
        assert names == ["factor_a", "factor_b"]


def test_preview_by_ticker_uses_parameters(tmp_path: Path) -> None:
    db_path = tmp_path / "stocks.db"
    prices = _sample_prices()
    conn = __import__("duckdb").connect(str(db_path))
    conn.register("prices_df", prices)
    conn.execute("CREATE TABLE raw_stocks AS SELECT * FROM prices_df")
    conn.close()

    repo = DuckDBPreviewRepository(db_path)
    # Injection-like ticker must be treated as a literal, not SQL
    malicious = "AAA'; DROP TABLE raw_stocks; --"
    frame = repo.preview_by_ticker(malicious, limit=5)
    assert frame.empty
    still_there = repo.get_tickers()
    assert "AAA" in still_there
    repo.close()


def test_compute_ic_returns_summary() -> None:
    prices = _sample_prices()
    forward = compute_forward_returns(prices, horizon=5)
    factor_values = prices[["Date", "Ticker"]].copy()
    factor_values["factor_value"] = prices.groupby("Ticker").cumcount().astype(float)
    result = compute_ic(
        factor_values,
        forward,
        factor_name="demo",
        forward_horizon=5,
        min_observations=5,
    )
    assert result.factor_name == "demo"
    assert not result.summary.empty
    assert "ic_mean" in result.summary.columns


def test_equal_weight_map_scales_to_budget() -> None:
    tickers = ["A", "B", "C", "D"]
    sleeve_budget = 0.5
    weight_tolerance = 1e-12
    weights = equal_weight_map(tickers, sleeve_budget=sleeve_budget)
    assert len(weights) == len(tickers)
    assert abs(sum(weights.values()) - sleeve_budget) < weight_tolerance
