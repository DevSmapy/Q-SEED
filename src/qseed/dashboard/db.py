"""DuckDB and data_log access for the stocks review dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import duckdb
import pandas as pd
import streamlit as st

from qseed.config import get_config
from src.repositories.duckdb_conn import connect


@dataclass(frozen=True)
class DataPaths:
    base_dir: Path
    db_path: Path
    log_dir: Path
    ticker_list_path: Path
    no_data_path: Path
    completed_data_path: Path


def get_data_paths() -> DataPaths:
    stock = get_config().stock
    return DataPaths(
        base_dir=stock.base_dir,
        db_path=stock.db_path,
        log_dir=stock.log_dir,
        ticker_list_path=stock.ticker_list_path,
        no_data_path=stock.no_data_path,
        completed_data_path=stock.completed_data_path,
    )


@st.cache_resource  # type: ignore[misc]
def get_connection() -> duckdb.DuckDBPyConnection:
    paths = get_data_paths()
    if not paths.db_path.exists():
        raise FileNotFoundError(f"DuckDB not found: {paths.db_path}")
    # read_only avoids locking writers; dbt runs need exclusive access separately
    return connect(paths.db_path, read_only=True)


@st.cache_data(ttl=300)  # type: ignore[misc]
def query_df(sql: str, params: tuple[Any, ...] | None = None) -> pd.DataFrame:
    con = get_connection()
    if params:
        return cast(pd.DataFrame, con.execute(sql, list(params)).df())
    return cast(pd.DataFrame, con.execute(sql).df())


@st.cache_data(ttl=300)  # type: ignore[misc]
def table_df(table: str) -> pd.DataFrame:
    # Identifier-only: reject anything that is not a simple table name
    if not table.replace("_", "").isalnum():
        raise ValueError(f"Invalid table name: {table}")
    return cast(pd.DataFrame, query_df(f"select * from {table}"))


@lru_cache(maxsize=1)
def _read_lines(path_str: str) -> tuple[str, ...]:
    path = Path(path_str)
    if not path.exists():
        return ()
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if item:
            lines.append(item)
    return tuple(lines)


@st.cache_data(ttl=300)  # type: ignore[misc]
def load_ticker_list() -> pd.DataFrame:
    paths = get_data_paths()
    if not paths.ticker_list_path.exists():
        return pd.DataFrame(columns=["Ticker", "Market"])
    return pd.read_csv(paths.ticker_list_path)


@st.cache_data(ttl=300)  # type: ignore[misc]
def load_completed_tickers() -> list[str]:
    return list(_read_lines(str(get_data_paths().completed_data_path)))


@st.cache_data(ttl=300)  # type: ignore[misc]
def load_no_data_tickers() -> list[str]:
    return list(_read_lines(str(get_data_paths().no_data_path)))


def classify_failure(ticker: str) -> str:
    if " " in ticker:
        return "preferred_or_spaced"
    if ticker.endswith(".U") or ".U" in ticker:
        return "unit_or_spac"
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "kr_failed"
    return "us_other"


@st.cache_data(ttl=300)  # type: ignore[misc]
def failure_frame() -> pd.DataFrame:
    rows = [{"Ticker": t, "failure_type": classify_failure(t)} for t in load_no_data_tickers()]
    return pd.DataFrame(rows)
