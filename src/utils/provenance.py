"""결과 산출물용 코드·데이터 provenance 수집."""

from __future__ import annotations

import logging
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from src.repositories.duckdb_conn import connect, table_exists

logger = logging.getLogger("qseed")

PACKAGE_NAME = "q-seed"
RAW_STOCKS_TABLE = "raw_stocks"


def collect_code_provenance(*, cwd: Path | None = None) -> dict[str, Any]:
    """git SHA·dirty·패키지 버전. 실패 시 null/상태로 남기고 예외를 올리지 않는다."""
    root = cwd or Path.cwd()
    git_sha: str | None = None
    dirty: bool | None = None
    git_status = "ok"
    try:
        git_exe = shutil.which("git")
        if git_exe is None:
            git_status = "unavailable"
        else:
            # Fixed argv after shutil.which; not shell, not user-controlled args.
            sha_proc = subprocess.run(  # noqa: S603
                [git_exe, "rev-parse", "HEAD"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if sha_proc.returncode == 0:
                git_sha = sha_proc.stdout.strip() or None
            else:
                git_status = "unavailable"

            dirty_proc = subprocess.run(  # noqa: S603
                [git_exe, "status", "--porcelain"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if dirty_proc.returncode == 0:
                dirty = bool(dirty_proc.stdout.strip())
            elif git_status == "ok":
                git_status = "dirty_unknown"
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("git provenance 수집 실패: %s", exc)
        git_status = "unavailable"

    package_version: str | None
    try:
        package_version = version(PACKAGE_NAME)
    except PackageNotFoundError:
        package_version = None

    return {
        "git_sha": git_sha,
        "dirty": dirty,
        "git_status": git_status,
        "package_version": package_version,
        "package_name": PACKAGE_NAME,
    }


def sanitize_db_path(db_path: Path | str, *, cwd: Path | None = None) -> str:
    """홈 경로를 노출하지 않도록 상대경로 또는 파일명만 반환."""
    path = Path(db_path).resolve()
    base = (cwd or Path.cwd()).resolve()
    try:
        return str(path.relative_to(base))
    except ValueError:
        return path.name


def collect_data_provenance(
    db_path: Path | str | None,
    *,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """DuckDB fingerprint. 파일/테이블이 없어도 연구 실행을 깨지 않는다."""
    if db_path is None:
        return {
            "db_path": None,
            "bytes": None,
            "row_count": None,
            "min_date": None,
            "max_date": None,
            "status": "no_path",
        }

    path = Path(db_path)
    result: dict[str, Any] = {
        "db_path": sanitize_db_path(path, cwd=cwd),
        "bytes": None,
        "row_count": None,
        "min_date": None,
        "max_date": None,
        "status": "ok",
    }
    if not path.exists():
        result["status"] = "missing"
        return result

    try:
        result["bytes"] = path.stat().st_size
    except OSError as exc:
        logger.debug("DB size 조회 실패: %s", exc)
        result["status"] = "stat_failed"
        return result

    conn = None
    try:
        conn = connect(path, read_only=True)
        if not table_exists(conn, RAW_STOCKS_TABLE):
            result["status"] = "no_raw_stocks"
            return result
        row = conn.execute(
            f"""
            select
                count(*)::bigint,
                min(Date)::varchar,
                max(Date)::varchar
            from {RAW_STOCKS_TABLE}
            """
        ).fetchone()
        if row is not None:
            result["row_count"] = int(row[0])
            result["min_date"] = row[1]
            result["max_date"] = row[2]
    except Exception as exc:  # noqa: BLE001 — provenance must not fail callers
        logger.debug("DB fingerprint 실패: %s", exc)
        result["status"] = "query_failed"
    finally:
        if conn is not None:
            conn.close()

    return result


def collect_provenance(
    db_path: Path | str | None = None,
    *,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """코드·데이터 provenance 묶음."""
    return {
        "code": collect_code_provenance(cwd=cwd),
        "data": collect_data_provenance(db_path, cwd=cwd),
    }
