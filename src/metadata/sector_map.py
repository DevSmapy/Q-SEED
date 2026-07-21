"""Yahoo Finance sector → GICS-aligned 11-sector normalization."""

from __future__ import annotations

from typing import Any

UNCLASSIFIED_SECTOR = "Unclassified"

EQUITY_QUOTE_TYPE = "EQUITY"

YAHOO_TO_GICS: dict[str, str] = {
    "Technology": "Information Technology",
    "Financial Services": "Financials",
    "Healthcare": "Health Care",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Basic Materials": "Materials",
    "Energy": "Energy",
    "Industrials": "Industrials",
    "Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "Communication Services": "Communication Services",
}


def normalize_sector(sector_raw: str | None) -> str:
    """Map Yahoo sector label to GICS-aligned name."""
    if not sector_raw or not str(sector_raw).strip():
        return UNCLASSIFIED_SECTOR
    key = str(sector_raw).strip()
    if key in YAHOO_TO_GICS:
        return YAHOO_TO_GICS[key]
    if key in YAHOO_TO_GICS.values():
        return key
    return UNCLASSIFIED_SECTOR


def parse_yfinance_info(
    ticker: str,
    market: str,
    info: dict[str, Any] | None,
    *,
    as_of: str,
    updated_at: str,
) -> dict[str, Any]:
    """Convert yfinance info dict to raw_security_metadata row."""
    data = info or {}
    quote_type = data.get("quoteType")
    quote_type_str = str(quote_type) if quote_type is not None else None

    sector_raw = data.get("sector")
    industry_raw = data.get("industry")

    if quote_type_str and quote_type_str.upper() != EQUITY_QUOTE_TYPE:
        sector = UNCLASSIFIED_SECTOR
        sector_status = "unclassified"
        sector_status_reason = "non_equity"
    elif sector_raw:
        sector = normalize_sector(str(sector_raw))
        if sector == UNCLASSIFIED_SECTOR:
            sector_status = "unclassified"
            sector_status_reason = "missing_yahoo"
        else:
            sector_status = "mapped"
            sector_status_reason = None
    else:
        sector_raw = None
        sector = UNCLASSIFIED_SECTOR
        sector_status = "unclassified"
        sector_status_reason = "missing_yahoo"

    return {
        "Ticker": ticker,
        "Market": market,
        "company_name": data.get("shortName") or data.get("longName"),
        "quote_type": quote_type_str,
        "sector_raw": sector_raw,
        "sector": sector,
        "industry_raw": industry_raw,
        "industry": industry_raw,
        "sector_key": data.get("sectorKey"),
        "industry_key": data.get("industryKey"),
        "country": data.get("country"),
        "currency": data.get("currency"),
        "sector_source": "yfinance",
        "sector_status": sector_status,
        "sector_status_reason": sector_status_reason,
        "as_of": as_of,
        "updated_at": updated_at,
    }


def error_row(
    ticker: str,
    market: str,
    *,
    as_of: str,
    updated_at: str,
) -> dict[str, Any]:
    """Row for failed yfinance fetch."""
    return {
        "Ticker": ticker,
        "Market": market,
        "company_name": None,
        "quote_type": None,
        "sector_raw": None,
        "sector": UNCLASSIFIED_SECTOR,
        "industry_raw": None,
        "industry": None,
        "sector_key": None,
        "industry_key": None,
        "country": None,
        "currency": None,
        "sector_source": "yfinance",
        "sector_status": "error",
        "sector_status_reason": "fetch_error",
        "as_of": as_of,
        "updated_at": updated_at,
    }
