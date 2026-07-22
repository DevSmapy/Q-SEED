"""Sector enrichment queue export and manual override import."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from src.metadata.sector_map import UNCLASSIFIED_SECTOR, normalize_sector
from src.repositories.duckdb_conn import connect, table_exists
from src.repositories.security_repository import SecurityRepository

ENRICHMENT_QUEUE_MART = "rpt_stocks__sector_enrichment_queue"

ENRICHMENT_QUEUE_FALLBACK_SQL = """
select
    Ticker,
    Market,
    company_name,
    sector,
    industry,
    sector_status,
    sector_status_reason,
    sector_source,
    as_of
from raw_security_metadata
where upper(coalesce(quote_type, '')) = 'EQUITY'
  and sector_status in ('unclassified', 'error')
qualify row_number() over (
    partition by Ticker, Market
    order by updated_at desc
) = 1
order by Market, Ticker
"""

OVERRIDE_CSV_COLUMNS = ("Ticker", "Market", "sector", "industry")


class EnrichmentSearchHook(Protocol):
    """Optional hook for downstream AI / search-engine enrichment."""

    def lookup(self, ticker: str, market: str) -> dict[str, Any] | None:
        """Return sector/industry fields or None if not found."""


@dataclass(frozen=True)
class OverrideInput:
    """Manual override fields from CSV or search hook."""

    ticker: str
    market: str
    sector: str
    industry: str | None = None
    company_name: str | None = None
    as_of: date | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class OverrideImportResult:
    """Manual override CSV import summary."""

    imported: int
    skipped: int


@dataclass(frozen=True)
class EnrichmentExportResult:
    """Enrichment queue CSV export summary."""

    row_count: int
    output_path: Path
    source: str


def parse_override_row(override: OverrideInput) -> dict[str, Any]:
    """Build a manual override row for raw_security_metadata."""
    today = override.as_of or date.today()
    ts = override.updated_at or datetime.now(tz=UTC)
    normalized = normalize_sector(override.sector)
    sector_status = "mapped" if normalized != UNCLASSIFIED_SECTOR else "unclassified"
    return {
        "Ticker": override.ticker,
        "Market": override.market,
        "company_name": override.company_name,
        "quote_type": "EQUITY",
        "sector_raw": override.sector,
        "sector": normalized,
        "industry_raw": override.industry,
        "industry": override.industry,
        "sector_key": None,
        "industry_key": None,
        "country": None,
        "currency": None,
        "sector_source": "manual",
        "sector_status": sector_status,
        "sector_status_reason": None if sector_status == "mapped" else "missing_yahoo",
        "as_of": today.isoformat(),
        "updated_at": ts.isoformat(),
    }


def load_override_rows(csv_path: Path) -> tuple[list[dict[str, Any]], int]:
    """Parse override CSV; returns rows and skipped invalid line count."""
    try:
        frame = pd.read_csv(csv_path, dtype=str)
    except pd.errors.EmptyDataError:
        return [], 0

    missing = [col for col in OVERRIDE_CSV_COLUMNS if col not in frame.columns]
    if missing:
        msg = f"Override CSV requires columns {OVERRIDE_CSV_COLUMNS}; missing {missing}"
        raise ValueError(msg)

    rows: list[dict[str, Any]] = []
    skipped = 0
    for record in frame.to_dict(orient="records"):
        ticker = str(record.get("Ticker", "")).strip()
        market = str(record.get("Market", "")).strip()
        sector = str(record.get("sector", "")).strip()
        if not ticker or not market or not sector:
            skipped += 1
            continue
        industry_val = record.get("industry")
        industry = str(industry_val).strip() if pd.notna(industry_val) else None
        company_val = record.get("company_name")
        company_name = str(company_val).strip() if pd.notna(company_val) else None
        rows.append(
            parse_override_row(
                OverrideInput(
                    ticker=ticker,
                    market=market,
                    sector=sector,
                    industry=industry,
                    company_name=company_name,
                )
            )
        )
    return rows, skipped


def import_security_overrides(db_path: Path | str, csv_path: Path | str) -> OverrideImportResult:
    """Import manual sector overrides into raw_security_metadata."""
    path = Path(csv_path)
    rows, skipped = load_override_rows(path)
    with SecurityRepository(db_path) as repo:
        imported = repo.upsert_rows(rows)
    return OverrideImportResult(imported=imported, skipped=skipped)


def export_enrichment_queue(
    db_path: Path | str,
    output_path: Path | str,
) -> EnrichmentExportResult:
    """Export enrichment queue to CSV (dbt mart preferred, raw fallback)."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(db_path, read_only=True)
    try:
        if table_exists(conn, ENRICHMENT_QUEUE_MART):
            frame = conn.execute(f"select * from {ENRICHMENT_QUEUE_MART}").df()
            source = ENRICHMENT_QUEUE_MART
        else:
            frame = conn.execute(ENRICHMENT_QUEUE_FALLBACK_SQL).df()
            source = "raw_security_metadata"
    finally:
        conn.close()

    frame.to_csv(out, index=False)
    return EnrichmentExportResult(row_count=len(frame), output_path=out, source=source)


def run_search_hook_batch(
    db_path: Path | str,
    hook: EnrichmentSearchHook,
    *,
    max_rows: int | None = None,
) -> int:
    """Apply an external search hook to queue rows (stub integration point)."""
    export_path = Path(db_path).parent / ".enrichment_queue_tmp.csv"
    try:
        result = export_enrichment_queue(db_path, export_path)
        if result.row_count == 0:
            return 0

        queue = pd.read_csv(export_path, dtype=str)
        if max_rows is not None:
            queue = queue.head(max_rows)

        rows: list[dict[str, Any]] = []
        for record in queue.to_dict(orient="records"):
            ticker = str(record["Ticker"])
            market = str(record["Market"])
            found = hook.lookup(ticker, market)
            if not found:
                continue
            sector = found.get("sector")
            if not sector:
                continue
            rows.append(
                parse_override_row(
                    OverrideInput(
                        ticker=ticker,
                        market=market,
                        sector=str(sector),
                        industry=found.get("industry"),
                        company_name=found.get("company_name"),
                    )
                )
            )

        if not rows:
            return 0
        with SecurityRepository(db_path) as repo:
            return repo.upsert_rows(rows)
    finally:
        export_path.unlink(missing_ok=True)
