"""yfinance 기반 종목 섹터·업종 메타데이터 수집."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import yfinance as yf

from src.metadata.sector_map import error_row, parse_yfinance_info

logger = logging.getLogger("qseed")

MIN_INFO_KEYS_FOR_VALID_RESPONSE = 3

METADATA_COLUMNS = [
    "Ticker",
    "Market",
    "company_name",
    "quote_type",
    "sector_raw",
    "sector",
    "industry_raw",
    "industry",
    "sector_key",
    "industry_key",
    "country",
    "currency",
    "sector_source",
    "sector_status",
    "sector_status_reason",
    "as_of",
    "updated_at",
]


@dataclass
class SecurityMetadataFetchResult:
    """메타데이터 수집 결과."""

    rows: list[dict[str, Any]] = field(default_factory=list)
    requested: int = 0
    mapped: int = 0
    unclassified: int = 0
    errors: int = 0


def _now_utc_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")


def fetch_info_for_ticker(ticker: str, market: str) -> dict[str, Any]:
    """단일 티커 yfinance info → metadata row."""
    as_of = date.today().isoformat()
    updated_at = _now_utc_iso()
    try:
        info = yf.Ticker(ticker).info
        if not info or (
            len(info) <= MIN_INFO_KEYS_FOR_VALID_RESPONSE and info.get("regularMarketPrice") is None
        ):
            return error_row(ticker, market, as_of=as_of, updated_at=updated_at)
        return parse_yfinance_info(
            ticker,
            market,
            info,
            as_of=as_of,
            updated_at=updated_at,
        )
    except Exception as exc:
        logger.warning("metadata fetch failed for %s: %s", ticker, exc)
        return error_row(ticker, market, as_of=as_of, updated_at=updated_at)


def fetch_metadata_batch(
    universe: list[tuple[str, str]],
    *,
    sleep_seconds: float = 0.3,
    equity_only: bool = True,
) -> SecurityMetadataFetchResult:
    """티커·시장 목록에 대해 순차적으로 metadata 수집."""
    result = SecurityMetadataFetchResult(requested=len(universe))
    for idx, (ticker, market) in enumerate(universe):
        row = fetch_info_for_ticker(ticker, market)
        if equity_only and row.get("quote_type") and row["quote_type"] != "EQUITY":
            continue
        result.rows.append(row)
        status = row.get("sector_status")
        if status == "mapped":
            result.mapped += 1
        elif status == "error":
            result.errors += 1
        else:
            result.unclassified += 1
        if sleep_seconds > 0 and idx + 1 < len(universe):
            time.sleep(sleep_seconds)
    return result
