"""Security metadata unit tests (no network)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.metadata.sector_map import (
    UNCLASSIFIED_SECTOR,
    normalize_sector,
    parse_yfinance_info,
)
from src.repositories.security_repository import SecurityRepository


def test_normalize_sector_yahoo_to_gics() -> None:
    assert normalize_sector("Technology") == "Information Technology"
    assert normalize_sector("Financial Services") == "Financials"
    assert normalize_sector(None) == UNCLASSIFIED_SECTOR


def test_parse_yfinance_info_equity_mapped() -> None:
    row = parse_yfinance_info(
        "AAPL",
        "NASDAQ",
        {"quoteType": "EQUITY", "sector": "Technology", "industry": "Consumer Electronics"},
        as_of="2026-07-21",
        updated_at="2026-07-21T00:00:00",
    )
    assert row["sector"] == "Information Technology"
    assert row["sector_status"] == "mapped"
    assert row["sector_status_reason"] is None


def test_parse_yfinance_info_etf_non_equity() -> None:
    row = parse_yfinance_info(
        "SPY",
        "NYSE",
        {"quoteType": "ETF"},
        as_of="2026-07-21",
        updated_at="2026-07-21T00:00:00",
    )
    assert row["sector"] == UNCLASSIFIED_SECTOR
    assert row["sector_status"] == "unclassified"
    assert row["sector_status_reason"] == "non_equity"


def test_security_repository_upsert_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "stocks.db"
    rows = [
        parse_yfinance_info(
            "AAPL",
            "NASDAQ",
            {"quoteType": "EQUITY", "sector": "Technology"},
            as_of="2026-07-21",
            updated_at="2026-07-21T00:00:00",
        )
    ]
    with SecurityRepository(db_path) as repo:
        assert repo.upsert_rows(rows) == 1
        assert repo.upsert_rows(rows) == 1
        count = repo.conn.execute("SELECT COUNT(*) FROM raw_security_metadata").fetchone()
        assert count is not None
        assert int(count[0]) == 1


def test_load_universe_from_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "krx_list.csv"
    pd.DataFrame({"Ticker": ["005930.KS"], "Market": ["KOSPI"]}).to_csv(csv_path, index=False)
    uni = SecurityRepository.load_universe_from_csv(csv_path)
    assert len(uni) == 1
    assert uni.iloc[0]["Ticker"] == "005930.KS"
