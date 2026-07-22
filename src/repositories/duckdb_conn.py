"""공유 DuckDB 연결 헬퍼."""

from __future__ import annotations

from pathlib import Path

import duckdb


def connect(path: Path | str, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """DuckDB 파일에 연결한다."""
    return duckdb.connect(str(Path(path)), read_only=read_only)


def table_exists(conn: duckdb.DuckDBPyConnection, name: str) -> bool:
    """information_schema 기준으로 테이블 존재 여부를 확인한다."""
    row = conn.execute(
        """
        select count(*)
        from information_schema.tables
        where table_name = ?
        """,
        [name],
    ).fetchone()
    return row is not None and int(row[0]) > 0
