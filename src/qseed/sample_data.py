"""로컬 샘플 DuckDB warehouse. git에 DB를 넣지 않고 명령으로 생성한다."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.repositories.duckdb_builder import DuckDBRepository

DEFAULT_TICKERS = 40
DEFAULT_DAYS = 80
DEFAULT_MARKET = "KOSPI"
DEFAULT_START = "2024-01-02"
DEFAULT_SEED = 42


@dataclass(frozen=True)
class SampleWarehouse:
    """생성한 샘플 warehouse 요약."""

    db_path: Path
    n_tickers: int
    n_days: int
    n_rows: int
    market: str


def build_sample_prices(
    *,
    n_tickers: int = DEFAULT_TICKERS,
    n_days: int = DEFAULT_DAYS,
    market: str = DEFAULT_MARKET,
    start: str = DEFAULT_START,
    seed: int = DEFAULT_SEED,
) -> pd.DataFrame:
    """단면 분산이 있는 합성 일봉. IC·단기 반전 데모용."""
    dates = pd.bdate_range(start, periods=n_days)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for ticker_i in range(n_tickers):
        ticker = f"SMPL{ticker_i:03d}"
        price = 40.0 + ticker_i
        drift = 0.0004 * ((ticker_i % 7) - 3)
        for day in dates:
            shock = float(rng.normal(drift, 0.012))
            price = max(1.0, price * (1.0 + shock))
            rows.append(
                {
                    "Date": pd.Timestamp(day),
                    "Ticker": ticker,
                    "Market": market,
                    "Open": price * 0.998,
                    "High": price * 1.004,
                    "Low": price * 0.996,
                    "Close": price,
                    "Volume": int(1_000_000 + ticker_i * 1000),
                    "Dividends": 0.0,
                    "Split": 0.0,
                }
            )
    return pd.DataFrame(rows)


def write_sample_warehouse(
    db_path: Path,
    *,
    n_tickers: int = DEFAULT_TICKERS,
    n_days: int = DEFAULT_DAYS,
    market: str = DEFAULT_MARKET,
    force: bool = False,
) -> SampleWarehouse:
    """`raw_stocks`만 채운 샘플 DuckDB를 만든다."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        if not force:
            msg = f"이미 warehouse가 있습니다: {db_path}. 덮어쓰려면 qseed demo --force"
            raise FileExistsError(msg)
        db_path.unlink()

    prices = build_sample_prices(n_tickers=n_tickers, n_days=n_days, market=market)
    with DuckDBRepository(db_path) as repo:
        repo.reset_raw_stocks_table()
        repo.insert_dataframe(prices)
        repo.checkpoint()
    return SampleWarehouse(
        db_path=db_path,
        n_tickers=n_tickers,
        n_days=n_days,
        n_rows=len(prices),
        market=market,
    )
