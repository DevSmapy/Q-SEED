#!/usr/bin/env python3
"""Create a tiny synthetic DuckDB warehouse for CI dbt build/test.

No network. Path defaults to data/ci_stocks.db (gitignored; keeps real stocks.db safe).
"""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb

WEEKDAYS = 5  # Monday=0 .. Friday=4


def _business_days(start: date, count: int) -> list[date]:
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < WEEKDAYS:
            days.append(current)
        current += timedelta(days=1)
    return days


def seed(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    dates = _business_days(date(2024, 1, 2), 40)
    tickers = [
        ("AAA", "KOSPI"),
        ("BBB", "KOSPI"),
        ("CCC", "KOSDAQ"),
        ("DDD", "NASDAQ"),
    ]

    stock_rows: list[tuple[object, ...]] = []
    for offset, day in enumerate(dates):
        for i, (ticker, market) in enumerate(tickers):
            close = 100.0 + i * 5.0 + offset * 0.25
            stock_rows.append(
                (
                    datetime(day.year, day.month, day.day),
                    ticker,
                    market,
                    close - 0.5,
                    close + 0.5,
                    close - 1.0,
                    close,
                    1_000_000 + i * 10_000,
                    0.0,
                    0.0,
                )
            )

    as_of = dates[-1]
    now = datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC).replace(tzinfo=None)
    meta_rows = [
        (
            "AAA",
            "KOSPI",
            "Alpha Co",
            "EQUITY",
            "Technology",
            "Information Technology",
            "Software",
            "Software",
            "technology",
            "software",
            "South Korea",
            "KRW",
            "yfinance",
            "mapped",
            None,
            as_of,
            now,
        ),
        (
            "BBB",
            "KOSPI",
            "Beta Co",
            "EQUITY",
            None,
            "Unclassified",
            None,
            None,
            None,
            None,
            "South Korea",
            "KRW",
            "yfinance",
            "unclassified",
            "missing_yahoo",
            as_of,
            now,
        ),
        (
            "CCC",
            "KOSDAQ",
            "Gamma Co",
            "EQUITY",
            "Healthcare",
            "Health Care",
            "Biotech",
            "Biotech",
            "healthcare",
            "biotech",
            "South Korea",
            "KRW",
            "yfinance",
            "mapped",
            None,
            as_of,
            now,
        ),
        (
            "DDD",
            "NASDAQ",
            "Delta ETF",
            "ETF",
            None,
            "Unclassified",
            None,
            None,
            None,
            None,
            "United States",
            "USD",
            "yfinance",
            "unclassified",
            "non_equity",
            as_of,
            now,
        ),
    ]

    series_rows = [
        (datetime(d.year, d.month, d.day), "vix", 15.0 + i * 0.1, "synthetic")
        for i, d in enumerate(dates)
    ]
    breadth_rows = [
        (
            datetime(d.year, d.month, d.day),
            "KOSPI",
            2,
            1,
            0,
            100.0,
            float(i),
            50.0,
            40.0,
        )
        for i, d in enumerate(dates)
    ]

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE raw_stocks (
                Date TIMESTAMP,
                Ticker TEXT,
                Market TEXT,
                Open DOUBLE,
                High DOUBLE,
                Low DOUBLE,
                Close DOUBLE,
                Volume BIGINT,
                Dividends DOUBLE,
                Split DOUBLE
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO raw_stocks
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            stock_rows,
        )

        conn.execute(
            """
            CREATE TABLE raw_security_metadata (
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
        conn.executemany(
            """
            INSERT INTO raw_security_metadata VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            meta_rows,
        )

        conn.execute(
            """
            CREATE TABLE raw_market_series (
                Date TIMESTAMP,
                series_id TEXT,
                value DOUBLE,
                source TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO raw_market_series VALUES (?, ?, ?, ?)",
            series_rows,
        )

        conn.execute(
            """
            CREATE TABLE raw_market_breadth (
                Date TIMESTAMP,
                Market TEXT,
                advances BIGINT,
                declines BIGINT,
                unchanged BIGINT,
                adr_20d DOUBLE,
                ad_line DOUBLE,
                pct_above_ma20 DOUBLE,
                pct_above_ma200 DOUBLE
            )
            """
        )
        conn.executemany(
            "INSERT INTO raw_market_breadth VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            breadth_rows,
        )
    finally:
        conn.close()

    print(f"Seeded synthetic DuckDB at {db_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default="data/ci_stocks.db",
        help="Output DuckDB path (default: data/ci_stocks.db)",
    )
    args = parser.parse_args()
    seed(Path(args.db))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
