"""CLI 인자 파서."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성."""
    parser = argparse.ArgumentParser(
        prog="qseed",
        description=(
            "Q-SEED 레거시 플래그. 초보자는 qseed doctor / qseed demo / qseed quickstart 를 쓰세요."
        ),
        epilog=(
            "작업 명령: qseed doctor | demo | quickstart | collect | analyze | backtest\n"
            "플래그 전체: qseed --help-flags"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--run-stock-pipeline",
        action="store_true",
        help="주식 데이터 수집 파이프라인 실행 (시장·종목 수·기간을 지정하는 첫 실행에 적합)",
    )
    parser.add_argument(
        "--run-market-pipeline",
        action="store_true",
        help="시장 지표 시계열 수집 및 breadth 파생 적재",
    )
    parser.add_argument(
        "--breadth-only",
        action="store_true",
        help="--run-market-pipeline 시 외부 시계열 수집 없이 breadth만 재계산",
    )
    parser.add_argument(
        "--build-db",
        action="store_true",
        help=(
            "전체 데이터베이스 구축 (기본: 모든 시장, 기간 max). "
            "--market / --max-stocks / --download-period 로 범위를 줄일 수 있음"
        ),
    )
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="데이터베이스 증분 업데이트 (마지막 날짜 이후 데이터 수집, 종료 후 공백 자동 복구)",
    )
    parser.add_argument(
        "--check-gaps",
        action="store_true",
        help="시장별 기준일 대비 뒤처진 티커 공백 탐지 (수집 없음)",
    )
    parser.add_argument(
        "--repair-gaps",
        action="store_true",
        help="공백이 감지된 티커만 재수집",
    )
    parser.add_argument(
        "--no-gap-repair",
        action="store_true",
        help="--update-db 실행 시 종료 후 자동 공백 복구 비활성화",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="full",
        choices=["full", "incremental"],
        help="실행 모드 (full 또는 incremental)",
    )
    parser.add_argument(
        "--max-stocks",
        type=int,
        default=None,
        help="시장별 최대 수집 종목 수 (입력값이 시스템 최대치를 초과하면 시스템 최대치로 제한됨)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="한 번에 처리할 종목 수",
    )
    parser.add_argument(
        "--download-period",
        type=str,
        default=None,
        help='yfinance 다운로드 기간 (예: "1y", "5y", "max")',
    )
    parser.add_argument(
        "--sleep-interval",
        type=float,
        default=None,
        help="청크 간 대기 시간(초)",
    )
    parser.add_argument(
        "--yfinance-threads",
        action="store_true",
        help="yfinance 멀티스레드 다운로드 활성화 (대량 청크 시 FD 부족 위험)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="수집 시작 날짜 (YYYY-MM-DD, incremental 모드 전용)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="수집 종료 날짜 (YYYY-MM-DD, incremental 모드 전용)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help='데이터 디렉토리 경로 (기본값: "./data")',
    )
    parser.add_argument(
        "--update-security-metadata",
        action="store_true",
        help="yfinance info 기반 종목 섹터·업종 메타데이터 적재",
    )
    parser.add_argument(
        "--max-tickers",
        type=int,
        default=None,
        help="--update-security-metadata 시 수집 최대 종목 수 (로컬 dev)",
    )
    parser.add_argument(
        "--security-sleep",
        type=float,
        default=None,
        help="--update-security-metadata 시 티커 간 대기(초)",
    )
    parser.add_argument(
        "--security-equity-only",
        action="store_true",
        help="--update-security-metadata 시 EQUITY만 raw_security_metadata에 저장",
    )
    parser.add_argument(
        "--import-security-overrides",
        type=str,
        default=None,
        metavar="CSV",
        help="수동 섹터 override CSV를 raw_security_metadata에 upsert",
    )
    parser.add_argument(
        "--export-enrichment-queue",
        type=str,
        default=None,
        metavar="CSV",
        help="섹터 enrichment 대상 목록 CSV export (dbt mart 또는 raw fallback)",
    )
    parser.add_argument(
        "--run-factor-analysis",
        action="store_true",
        help="팩터 IC·분위수 분석 실행",
    )
    parser.add_argument(
        "--factor",
        type=str,
        default=None,
        help="분석할 팩터 이름 (예: momentum_12_1, reversal_5d)",
    )
    parser.add_argument(
        "--list-factors",
        action="store_true",
        help="등록된 팩터 목록 출력",
    )
    parser.add_argument(
        "--market",
        type=str,
        action="append",
        default=None,
        help="분석 대상 시장 (반복 지정 가능, 예: --market KOSPI --market KOSDAQ)",
    )
    parser.add_argument(
        "--forward-horizon",
        type=int,
        default=None,
        help="선행 수익률 기간(거래일, 기본값: 21)",
    )
    parser.add_argument(
        "--run-backtest",
        action="store_true",
        help="팩터 롱숏/롱온리 백테스트 실행",
    )
    parser.add_argument(
        "--rebalance-freq",
        type=int,
        default=None,
        help="리밸런싱 주기(거래일, 기본값: 21)",
    )
    parser.add_argument(
        "--position-mode",
        type=str,
        default=None,
        choices=["long_short", "long_only"],
        help="포지션 모드 (long_short 또는 long_only)",
    )
    parser.add_argument(
        "--long-only",
        action="store_true",
        help="롱온리 모드 (--position-mode long_only 와 동일)",
    )
    parser.add_argument(
        "--transaction-cost-bps",
        type=float,
        default=None,
        help="거래비용 (bps, 기본값: 0)",
    )
    parser.add_argument(
        "--backtest-output-dir",
        type=str,
        default=None,
        help='백테스트 결과 출력 경로 (기본값: "{data_dir}/backtest/case_study_kr")',
    )
    parser.add_argument(
        "--export-format",
        type=str,
        default=None,
        choices=["parquet", "csv", "both"],
        help="백테스트 결과 파일 형식 (기본값: parquet)",
    )
    parser.add_argument(
        "--run-optimize",
        action="store_true",
        help="팩터 선정 + 포트폴리오 가중치 최적화 백테스트 실행",
    )
    parser.add_argument(
        "--weight-method",
        type=str,
        default=None,
        choices=["equal_weight", "min_volatility", "max_sharpe", "hrp"],
        help="가중치 방법 (기본: backtest=equal_weight, optimize=min_volatility)",
    )
    parser.add_argument(
        "--opt-lookback",
        type=int,
        default=None,
        help="최적화 lookback 거래일 (기본값: 252)",
    )
    parser.add_argument(
        "--opt-max-assets",
        type=int,
        default=None,
        help="슬리브당 최적화 최대 종목 수 (기본값: 50)",
    )
    return parser


TASK_COMMANDS = frozenset(
    {
        "doctor",
        "demo",
        "quickstart",
        "collect",
        "analyze",
        "backtest",
        "optimize",
        "factors",
    }
)

ROOT_HELP = """\
usage: qseed <command> [options]

Q-SEED 로컬 퀀트 연구 엔진

첫 실행:
  qseed doctor        환경·설정·DB 점검
  qseed demo          샘플 데이터로 IC·백테스트 한 바퀴 (네트워크 없음)
  qseed quickstart    doctor 후 demo까지 한 번에

연구:
  qseed collect       실제 시세 수집 (기본: KOSPI 80종목 1y)
  qseed analyze       팩터 IC·분위수 (기본: reversal_5d)
  qseed backtest      팩터 백테스트 (기본: reversal_5d)
  qseed optimize      가중치 최적화
  qseed factors       등록 팩터 목록

도움:
  qseed <command> -h
  qseed --help-flags   기존 --build-db 등 플래그
"""


def print_root_help() -> None:
    """초보자용 루트 도움말."""
    print(ROOT_HELP, end="")


def build_task_parser() -> argparse.ArgumentParser:
    """작업 중심 서브커맨드 파서."""
    parser = argparse.ArgumentParser(
        prog="qseed",
        description="Q-SEED 로컬 퀀트 연구 엔진",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help='데이터 디렉토리 (기본값: "./data")',
    )

    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", parents=[common], help="환경·설정·DB 점검")
    doctor.set_defaults(command="doctor")

    demo = sub.add_parser(
        "demo",
        parents=[common],
        help="샘플 warehouse로 팩터 IC·백테스트 (네트워크 없음)",
    )
    demo.add_argument(
        "--force",
        action="store_true",
        help="기존 stocks.db를 샘플 데이터로 덮어쓰기",
    )
    demo.add_argument(
        "--seed-only",
        action="store_true",
        help="샘플 DB만 만들고 분석은 생략",
    )
    demo.set_defaults(command="demo")

    quickstart = sub.add_parser(
        "quickstart",
        parents=[common],
        help="doctor 다음 demo까지 한 번에",
    )
    quickstart.add_argument(
        "--force",
        action="store_true",
        help="기존 stocks.db를 샘플 데이터로 덮어쓰기",
    )
    quickstart.set_defaults(command="quickstart")

    collect = sub.add_parser(
        "collect",
        parents=[common],
        help="실제 시세 수집 (기본: KOSPI 80종목 1y)",
    )
    collect.add_argument("--market", action="append", default=None, help="대상 시장 (반복 가능)")
    collect.add_argument(
        "--max-stocks",
        type=int,
        default=None,
        help="시장별 최대 종목 수 (기본 수집: 80)",
    )
    collect.add_argument(
        "--period",
        type=str,
        default=None,
        help="yfinance 기간 (기본 수집: 1y)",
    )
    collect.add_argument("--full", action="store_true", help="전 시장·기간 max (--build-db)")
    collect.add_argument("--update", action="store_true", help="증분 업데이트 (--update-db)")
    collect.set_defaults(command="collect")

    analyze = sub.add_parser(
        "analyze",
        parents=[common],
        help="팩터 IC·분위수 (기본 팩터: reversal_5d)",
    )
    analyze.add_argument("--factor", type=str, default="reversal_5d")
    analyze.add_argument("--market", action="append", default=None)
    analyze.add_argument("--forward-horizon", type=int, default=None)
    analyze.set_defaults(command="analyze")

    backtest = sub.add_parser(
        "backtest",
        parents=[common],
        help="팩터 백테스트 (기본 팩터: reversal_5d)",
    )
    backtest.add_argument("--factor", type=str, default="reversal_5d")
    backtest.add_argument("--market", action="append", default=None)
    backtest.add_argument("--long-only", action="store_true")
    backtest.add_argument("--rebalance-freq", type=int, default=None)
    backtest.set_defaults(command="backtest")

    optimize = sub.add_parser(
        "optimize",
        parents=[common],
        help="팩터 선정 + 가중치 최적화 백테스트",
    )
    optimize.add_argument("--factor", type=str, default="reversal_5d")
    optimize.add_argument("--market", action="append", default=None)
    optimize.add_argument(
        "--weight-method",
        type=str,
        default=None,
        choices=["equal_weight", "min_volatility", "max_sharpe", "hrp"],
    )
    optimize.set_defaults(command="optimize")

    factors = sub.add_parser("factors", help="등록된 팩터 목록")
    factors.set_defaults(command="factors")
    return parser
