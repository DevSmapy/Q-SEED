"""작업 중심 CLI: doctor, demo, quickstart, collect/analyze/backtest."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from src.qseed import hints
from src.qseed.cli.commands import (
    run_backtest_cli,
    run_factor_analysis,
    run_optimize_cli,
    run_stock_main_cli,
)
from src.qseed.cli.parser import build_parser
from src.qseed.config import AppConfig, get_config
from src.qseed.sample_data import write_sample_warehouse

REQUIRED_PYTHON = (3, 11)
MAX_PYTHON = (3, 13)


@dataclass(frozen=True)
class DoctorCheck:
    """doctor 한 줄."""

    name: str
    status: str
    detail: str
    hint: str | None = None


def _config(data_dir: str | None) -> AppConfig:
    config = get_config()
    if data_dir is not None:
        config.stock.base_dir = Path(data_dir)
    return config


def _flag_ns(flag_argv: list[str]) -> argparse.Namespace:
    return build_parser().parse_args(flag_argv)


def _append_data_dir(flag_argv: list[str], data_dir: str | None) -> list[str]:
    if data_dir:
        flag_argv.extend(["--data-dir", data_dir])
    return flag_argv


def collect_doctor_checks(*, data_dir: str | None, cwd: Path | None = None) -> list[DoctorCheck]:
    """환경 점검을 리스트로 반환 (테스트용)."""
    cwd = cwd or Path.cwd()
    checks: list[DoctorCheck] = []

    version = sys.version_info
    py_ok = REQUIRED_PYTHON <= (version.major, version.minor) < MAX_PYTHON
    checks.append(
        DoctorCheck(
            name="python",
            status="ok" if py_ok else "fail",
            detail=f"{version.major}.{version.minor}.{version.micro}",
            hint=None if py_ok else "Python 3.11 또는 3.12가 필요합니다.",
        )
    )

    try:
        pkg = metadata.version("q-seed")
        checks.append(DoctorCheck(name="qseed", status="ok", detail=pkg))
    except metadata.PackageNotFoundError:
        checks.append(
            DoctorCheck(
                name="qseed",
                status="fail",
                detail="패키지 없음",
                hint="다음: make setup",
            )
        )

    profiles = cwd / "profiles.yml"
    if profiles.is_file():
        checks.append(DoctorCheck(name="profiles.yml", status="ok", detail=str(profiles)))
    else:
        checks.append(
            DoctorCheck(
                name="profiles.yml",
                status="warn",
                detail="없음 (dbt에 필요)",
                hint="다음: cp profiles.yml.example profiles.yml",
            )
        )

    env_file = cwd / ".env"
    if env_file.is_file():
        checks.append(DoctorCheck(name=".env", status="ok", detail=str(env_file)))
    else:
        checks.append(
            DoctorCheck(
                name=".env",
                status="warn",
                detail="없음",
                hint="다음: cp .env.example .env",
            )
        )

    config = _config(data_dir)
    db_path = config.stock.db_path
    if db_path.is_file():
        try:
            import duckdb

            conn = duckdb.connect(str(db_path), read_only=True)
            try:
                tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
                n_rows = 0
                if "raw_stocks" in tables:
                    count_row = conn.execute("SELECT COUNT(*) FROM raw_stocks").fetchone()
                    n_rows = int(count_row[0]) if count_row else 0
            finally:
                conn.close()
            checks.append(
                DoctorCheck(
                    name="stocks.db",
                    status="ok",
                    detail=f"{db_path} (raw_stocks {n_rows}행)",
                )
            )
        except Exception as exc:  # noqa: BLE001 — doctor는 원인만 보여 주면 됨
            checks.append(
                DoctorCheck(
                    name="stocks.db",
                    status="fail",
                    detail=f"열 수 없음: {exc}",
                    hint="다음: qseed demo --force",
                )
            )
    else:
        checks.append(
            DoctorCheck(
                name="stocks.db",
                status="warn",
                detail=f"없음 ({db_path})",
                hint="다음: qseed demo",
            )
        )
    return checks


def format_doctor_report(checks: list[DoctorCheck]) -> str:
    """doctor 출력 텍스트."""
    lines = ["qseed doctor"]
    for check in checks:
        marker = {"ok": "ok  ", "warn": "warn", "fail": "fail"}[check.status]
        lines.append(f"  [{marker}] {check.name}: {check.detail}")
        if check.hint:
            lines.append(f"           {check.hint}")
    fails = sum(1 for item in checks if item.status == "fail")
    warns = sum(1 for item in checks if item.status == "warn")
    if fails:
        lines.append("결과: 실패가 있습니다. 위 다음 명령을 실행하세요.")
    elif warns:
        lines.append("결과: 경고만 있습니다. 샘플부터 가려면: qseed demo")
    else:
        lines.append("결과: 준비됨. 다음: qseed analyze   또는   qseed demo")
    return "\n".join(lines)


def run_doctor(args: argparse.Namespace) -> int:
    """환경 점검."""
    checks = collect_doctor_checks(data_dir=args.data_dir)
    print(format_doctor_report(checks))
    if any(check.status == "fail" for check in checks):
        return 1
    return 0


def run_demo(args: argparse.Namespace) -> int:
    """샘플 warehouse 생성 후 (옵션) 분석·백테스트."""
    config = _config(args.data_dir)
    db_path = config.stock.db_path
    market: str | None = None
    if db_path.exists() and not args.force:
        print(f"기존 warehouse 사용: {db_path}")
        print("덮어쓰려면: qseed demo --force")
    else:
        warehouse = write_sample_warehouse(db_path, force=db_path.exists())
        market = warehouse.market
        print(
            f"샘플 warehouse: {warehouse.db_path} "
            f"({warehouse.n_tickers}종목 · {warehouse.n_days}일 · {warehouse.n_rows}행, 합성)"
        )
    if args.seed_only:
        print("다음:\n  qseed analyze\n  qseed backtest\n  qseed doctor")
        return 0

    analyze_ns = argparse.Namespace(
        data_dir=str(config.stock.base_dir),
        factor="reversal_5d",
        market=[market] if market else None,
        forward_horizon=None,
    )
    analyze_code = run_analyze_task(analyze_ns)
    if analyze_code != 0:
        return analyze_code
    backtest_code = run_backtest_task(
        argparse.Namespace(
            data_dir=str(config.stock.base_dir),
            factor="reversal_5d",
            market=[market] if market else None,
            long_only=False,
            rebalance_freq=None,
        )
    )
    if backtest_code != 0:
        return backtest_code

    factor_dir = config.stock.base_dir / "factor_analysis" / "reversal_5d"
    backtest_root = config.stock.base_dir / "backtest" / "case_study_kr"
    print(hints.after_demo(db_path, factor_dir, backtest_root))
    return 0


def run_quickstart(args: argparse.Namespace) -> int:
    """doctor 후 demo."""
    doctor_code = run_doctor(args)
    if doctor_code != 0:
        return doctor_code
    demo_args = argparse.Namespace(
        data_dir=args.data_dir,
        force=bool(getattr(args, "force", False)),
        seed_only=False,
    )
    demo_code = run_demo(demo_args)
    if demo_code != 0:
        return demo_code
    print(hints.after_quickstart())
    return 0


def collect_to_flag_argv(args: argparse.Namespace) -> list[str]:
    """collect 서브커맨드를 레거시 플래그로 바꾼다."""
    flag_argv: list[str] = []
    if args.full:
        flag_argv.append("--build-db")
        if args.market:
            for market in args.market:
                flag_argv.extend(["--market", market])
        if args.max_stocks is not None:
            flag_argv.extend(["--max-stocks", str(args.max_stocks)])
        if args.period is not None:
            flag_argv.extend(["--download-period", args.period])
        return _append_data_dir(flag_argv, args.data_dir)
    if args.update:
        flag_argv.append("--update-db")
        if args.market:
            for market in args.market:
                flag_argv.extend(["--market", market])
        return _append_data_dir(flag_argv, args.data_dir)

    flag_argv.append("--run-stock-pipeline")
    markets = args.market or ["KOSPI"]
    flag_argv.extend(["--max-stocks", str(args.max_stocks or 80)])
    flag_argv.extend(["--download-period", args.period or "1y"])
    for market in markets:
        flag_argv.extend(["--market", market])
    return _append_data_dir(flag_argv, args.data_dir)


def run_collect_task(args: argparse.Namespace) -> int:
    """실제 시세 수집."""
    if args.full and args.update:
        print("`--full`과 `--update`는 함께 쓸 수 없습니다.", file=sys.stderr)
        return 2
    return run_stock_main_cli(_flag_ns(collect_to_flag_argv(args)))


def run_analyze_task(args: argparse.Namespace) -> int:
    """팩터 분석."""
    flag_argv = ["--run-factor-analysis", "--factor", args.factor or "reversal_5d"]
    if args.market:
        for market in args.market:
            flag_argv.extend(["--market", market])
    if args.forward_horizon is not None:
        flag_argv.extend(["--forward-horizon", str(args.forward_horizon)])
    _append_data_dir(flag_argv, args.data_dir)
    return run_factor_analysis(_flag_ns(flag_argv))


def run_backtest_task(args: argparse.Namespace) -> int:
    """백테스트."""
    flag_argv = ["--run-backtest", "--factor", args.factor or "reversal_5d"]
    if args.market:
        for market in args.market:
            flag_argv.extend(["--market", market])
    if args.long_only:
        flag_argv.append("--long-only")
    if args.rebalance_freq is not None:
        flag_argv.extend(["--rebalance-freq", str(args.rebalance_freq)])
    _append_data_dir(flag_argv, args.data_dir)
    return run_backtest_cli(_flag_ns(flag_argv))


def run_optimize_task(args: argparse.Namespace) -> int:
    """최적화 백테스트."""
    flag_argv = ["--run-optimize", "--factor", args.factor or "reversal_5d"]
    if args.market:
        for market in args.market:
            flag_argv.extend(["--market", market])
    if args.weight_method:
        flag_argv.extend(["--weight-method", args.weight_method])
    _append_data_dir(flag_argv, args.data_dir)
    return run_optimize_cli(_flag_ns(flag_argv))


def run_factors_task(_args: argparse.Namespace) -> int:
    """팩터 목록."""
    return run_factor_analysis(_flag_ns(["--list-factors"]))


def dispatch_task(args: argparse.Namespace) -> int:
    """서브커맨드 실행."""
    handlers = {
        "doctor": run_doctor,
        "demo": run_demo,
        "quickstart": run_quickstart,
        "collect": run_collect_task,
        "analyze": run_analyze_task,
        "backtest": run_backtest_task,
        "optimize": run_optimize_task,
        "factors": run_factors_task,
    }
    handler = handlers.get(args.command)
    if handler is None:
        print(hints.unknown_command(str(args.command)), file=sys.stderr)
        return 2
    return handler(args)
