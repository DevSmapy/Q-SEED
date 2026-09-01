"""초보자용 다음 명령 안내."""

from __future__ import annotations

from pathlib import Path


def missing_db(path: Path) -> str:
    return (
        f"DuckDB 파일이 없습니다: {path}\n"
        "다음:\n"
        "  qseed demo       # 샘플 데이터로 팩터 IC·백테스트 (네트워크 없음)\n"
        "  qseed collect    # 실제 시세 수집 (네트워크 필요)\n"
        "  qseed doctor     # 환경 점검"
    )


def unusable_warehouse(path: Path, reason: str) -> str:
    return f"warehouse를 쓸 수 없습니다: {path} ({reason})\n" "다음:\n" "  qseed demo --force"
    return (
        "분석할 주가 데이터가 없습니다.\n"
        "다음:\n"
        "  qseed demo\n"
        "  qseed collect\n"
        "  qseed doctor"
    )


def short_history(factor_name: str, min_history_days: int, longest: int) -> str:
    return (
        f"팩터 '{factor_name}'은 종목당 최소 {min_history_days}거래일이 필요합니다. "
        f"현재 최장 히스토리는 {longest}일입니다.\n"
        "다음:\n"
        "  qseed analyze --factor reversal_5d\n"
        "  qseed collect --period 3y"
    )


def too_few_names(n_tickers: int, min_observations: int) -> str:
    return (
        f"유니버스 종목 수({n_tickers})가 IC min_observations({min_observations})보다 작습니다. "
        "IC가 비거나 NaN일 수 있습니다.\n"
        "다음:\n"
        "  qseed demo\n"
        f"  qseed collect --max-stocks {min_observations}"
    )


def after_demo(db_path: Path, factor_dir: Path, backtest_dir: Path | None) -> str:
    backtest_line = (
        f"  백테스트: {backtest_dir}" if backtest_dir is not None else "  백테스트: (실행 안 함)"
    )
    return (
        "샘플 연구 루프가 끝났습니다.\n"
        f"  warehouse: {db_path}\n"
        f"  팩터 IC: {factor_dir}\n"
        f"{backtest_line}\n"
        "다음:\n"
        "  qseed doctor\n"
        "  make dashboard\n"
        "  qseed collect    # 실제 시세로 같은 루프"
    )


def after_quickstart() -> str:
    return (
        "quickstart가 끝났습니다.\n"
        "다음:\n"
        "  qseed analyze --factor reversal_5d\n"
        "  qseed collect\n"
        "  make dashboard"
    )


def unknown_command(name: str) -> str:
    return (
        f"알 수 없는 명령: {name}\n" "다음:\n" "  qseed doctor\n" "  qseed demo\n" "  qseed --help"
    )
