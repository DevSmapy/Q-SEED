"""시장 지표 정규화·breadth·저장소 단위 테스트."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.fetchers.market_series import _to_series_frame
from src.pipelines.breadth import compute_market_breadth
from src.providers.market_series_provider import MarketSeriesSpec
from src.repositories.market_repository import MarketRepository


def test_to_series_frame_picks_close() -> None:
    raw = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "Open": [1.0, 2.0],
            "Close": [10.0, 11.0],
        }
    )
    out = _to_series_frame(raw, series_id="vix", source="fdr", value_column="Close")
    assert list(out.columns) == ["Date", "series_id", "value", "source"]
    assert out["series_id"].tolist() == ["vix", "vix"]
    assert out["value"].tolist() == [10.0, 11.0]


def test_to_series_frame_uses_column_hint() -> None:
    raw = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01"]),
            "거래대금": [100.0],
            "고객예탁금": [200.0],
        }
    )
    out = _to_series_frame(
        raw, series_id="kr_investor_deposit", source="fdr", value_column="예탁금"
    )
    assert out["value"].tolist() == [200.0]


def test_compute_market_breadth_basic() -> None:
    # 3 tickers, 25 business days — enough for MA20 / ADR20
    rows: list[dict[str, object]] = []
    tickers = ["A", "B", "C"]
    # A always up, B always down, C flat after day 1
    for offset, day in enumerate(pd.date_range("2024-01-01", periods=25, freq="B")):
        for ticker in tickers:
            if ticker == "A":
                close = 100.0 + offset
            elif ticker == "B":
                close = 100.0 - offset
            else:
                close = 100.0
            rows.append(
                {
                    "Date": day,
                    "Ticker": ticker,
                    "Market": "TEST",
                    "Close": close,
                }
            )
    prices = pd.DataFrame(rows)
    breadth = compute_market_breadth(prices)

    assert not breadth.empty
    assert set(breadth["Market"]) == {"TEST"}
    # After first day: A up, B down, C flat → advances=1, declines=1, unchanged=1
    second = breadth.iloc[0]
    assert int(second["advances"]) == 1
    assert int(second["declines"]) == 1
    assert int(second["unchanged"]) == 1
    # AD line is cumulative net; after many days with net 0, stays near 0
    assert breadth["ad_line"].iloc[-1] == 0
    # ADR window filled on last rows
    assert breadth["adr_20d"].notna().any()
    assert breadth["pct_above_ma20"].notna().any()


def test_market_repository_series_dedupe(tmp_path: Path) -> None:
    db_path = tmp_path / "stocks.db"
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "series_id": ["vix", "vix"],
            "value": [12.0, 13.0],
            "source": ["fdr", "fdr"],
        }
    )
    with MarketRepository(db_path) as repo:
        repo.insert_series(frame)
        repo.deduplicate_series()
        rows = repo.conn.execute(
            "SELECT series_id, value FROM raw_market_series ORDER BY value"
        ).fetchall()
        assert len(rows) == 1


def test_market_repository_replace_breadth(tmp_path: Path) -> None:
    db_path = tmp_path / "stocks.db"
    breadth = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "Market": ["TEST", "TEST"],
            "advances": [1, 2],
            "declines": [1, 0],
            "unchanged": [0, 0],
            "adr_20d": [100.0, 200.0],
            "ad_line": [0.0, 2.0],
            "pct_above_ma20": [50.0, 60.0],
            "pct_above_ma200": [40.0, 45.0],
        }
    )
    with MarketRepository(db_path) as repo:
        repo.replace_breadth_for_markets(["TEST"], breadth)
        repo.replace_breadth_for_markets(["TEST"], breadth)
        count = repo.conn.execute(
            "SELECT COUNT(*) FROM raw_market_breadth WHERE Market = 'TEST'"
        ).fetchone()
        assert count is not None
        assert int(count[0]) == 2


def test_series_specs_cover_phase1() -> None:
    from src.providers.market_series_provider import get_series_specs

    ids = {s.series_id for s in get_series_specs()}
    assert ids == {"vix", "dxy", "us_t10y2y", "kr_investor_deposit"}
    assert all(isinstance(s, MarketSeriesSpec) for s in get_series_specs())
