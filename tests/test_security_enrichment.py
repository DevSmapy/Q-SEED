"""Sector enrichment import/export tests (no network)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src.metadata.enrichment import (
    OverrideInput,
    export_enrichment_queue,
    import_security_overrides,
    load_override_rows,
    parse_override_row,
    run_search_hook_batch,
)
from src.metadata.sector_map import parse_yfinance_info
from src.repositories.security_repository import SecurityRepository


def test_parse_override_row_maps_sector() -> None:
    row = parse_override_row(
        OverrideInput(
            ticker="005930.KS",
            market="KOSPI",
            sector="Technology",
            industry="Semiconductors",
        )
    )
    assert row["sector"] == "Information Technology"
    assert row["sector_source"] == "manual"
    assert row["sector_status"] == "mapped"


def test_import_and_export_enrichment_queue(tmp_path: Path) -> None:
    db_path = tmp_path / "stocks.db"
    rows = [
        parse_yfinance_info(
            "MISSING.KS",
            "KOSPI",
            {"quoteType": "EQUITY"},
            as_of="2026-07-21",
            updated_at="2026-07-21T00:00:00",
        ),
        parse_yfinance_info(
            "AAPL",
            "NASDAQ",
            {"quoteType": "EQUITY", "sector": "Technology"},
            as_of="2026-07-21",
            updated_at="2026-07-21T00:00:00",
        ),
    ]
    with SecurityRepository(db_path) as repo:
        repo.upsert_rows(rows)

    out_csv = tmp_path / "queue.csv"
    result = export_enrichment_queue(db_path, out_csv)
    assert result.row_count == 1
    assert result.source == "raw_security_metadata"
    exported = pd.read_csv(out_csv)
    assert exported.iloc[0]["Ticker"] == "MISSING.KS"


def test_import_security_overrides_csv(tmp_path: Path) -> None:
    db_path = tmp_path / "stocks.db"
    csv_path = tmp_path / "overrides.csv"
    pd.DataFrame(
        {
            "Ticker": ["005930.KS"],
            "Market": ["KOSPI"],
            "sector": ["Technology"],
            "industry": ["Semiconductors"],
        }
    ).to_csv(csv_path, index=False)

    result = import_security_overrides(db_path, csv_path)
    assert result.imported == 1
    assert result.skipped == 0

    conn = duckdb.connect(str(db_path))
    try:
        sector = conn.execute(
            "select sector, sector_source from raw_security_metadata where Ticker = '005930.KS'"
        ).fetchone()
    finally:
        conn.close()
    assert sector is not None
    assert sector[0] == "Information Technology"
    assert sector[1] == "manual"


class _StubHook:
    def lookup(self, ticker: str, market: str) -> dict[str, str] | None:
        if ticker == "MISSING.KS":
            return {"sector": "Technology", "industry": "Chips"}
        return None


def test_run_search_hook_batch(tmp_path: Path) -> None:
    db_path = tmp_path / "stocks.db"
    with SecurityRepository(db_path) as repo:
        repo.upsert_rows(
            [
                parse_yfinance_info(
                    "MISSING.KS",
                    "KOSPI",
                    {"quoteType": "EQUITY"},
                    as_of="2026-07-21",
                    updated_at="2026-07-21T00:00:00",
                )
            ]
        )

    upserted = run_search_hook_batch(db_path, _StubHook())
    assert upserted == 1

    conn = duckdb.connect(str(db_path))
    try:
        row = conn.execute(
            """
            select sector, sector_source
            from raw_security_metadata
            where Ticker = 'MISSING.KS'
            order by updated_at desc
            limit 1
            """
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == "Information Technology"
    assert row[1] == "manual"


def test_load_override_rows_empty_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")
    rows, skipped = load_override_rows(csv_path)
    assert rows == []
    assert skipped == 0


def test_load_override_rows_preserves_leading_zeros(tmp_path: Path) -> None:
    csv_path = tmp_path / "overrides.csv"
    csv_path.write_text(
        "Ticker,Market,sector,industry\n005930.KS,KOSPI,Technology,Semiconductors\n",
        encoding="utf-8",
    )
    rows, skipped = load_override_rows(csv_path)
    assert skipped == 0
    assert len(rows) == 1
    assert rows[0]["Ticker"] == "005930.KS"


def test_run_search_hook_batch_cleans_tmp_on_read_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "stocks.db"
    export_path = tmp_path / ".enrichment_queue_tmp.csv"
    with SecurityRepository(db_path) as repo:
        repo.upsert_rows(
            [
                parse_yfinance_info(
                    "MISSING.KS",
                    "KOSPI",
                    {"quoteType": "EQUITY"},
                    as_of="2026-07-21",
                    updated_at="2026-07-21T00:00:00",
                )
            ]
        )

    def _read_csv_fail(*args: object, **kwargs: object) -> pd.DataFrame:
        raise ValueError("read failed")

    monkeypatch.setattr("src.metadata.enrichment.pd.read_csv", _read_csv_fail)

    with pytest.raises(ValueError, match="read failed"):
        run_search_hook_batch(db_path, _StubHook())

    assert not export_path.exists()
