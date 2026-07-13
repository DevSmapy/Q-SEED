"""백테스트 결과 파일보내기 (시각화·웹 API 친화적 구조)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from src.backtest.metrics import BacktestMetrics, metrics_to_dataframe
from src.backtest.strategy import BacktestStrategy

ExportFormat = Literal["parquet", "csv", "both"]
SCHEMA_VERSION = "1.0"
RUNS_INDEX_FILENAME = "runs_index.json"


@dataclass(frozen=True)
class BacktestRunScope:
    """백테스트 실행 범위 메타데이터 (디렉토리명이 아닌 데이터로 구분)."""

    markets: list[str] | None
    start_date: str | None
    end_date: str | None
    ticker_count: int
    trading_days: int
    rebalance_count: int


@dataclass(frozen=True)
class BacktestExportResult:
    """단일 실행보내기 결과."""

    run_id: str
    run_dir: Path
    manifest_path: Path


def resolve_backtest_output_dir(
    base_dir: Path,
    configured: Path | str | None = None,
) -> Path:
    """백테스트 결과 출력 경로 결정."""
    if configured is None:
        return base_dir / "backtest" / "case_study_kr"
    return Path(configured)


def prepare_daily_returns(
    daily_returns: pd.DataFrame,
    *,
    initial_capital: float,
) -> pd.DataFrame:
    """시각화용 일별 수익률 테이블 정리."""
    frame = daily_returns.copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.sort_values("Date").reset_index(drop=True)
    frame["cumulative_return"] = frame["equity"] / initial_capital - 1.0
    if "benchmark_return" in frame.columns:
        benchmark_equity = initial_capital * (1.0 + frame["benchmark_return"].fillna(0.0)).cumprod()
        frame["benchmark_equity"] = benchmark_equity
        frame["benchmark_cumulative_return"] = benchmark_equity / initial_capital - 1.0
    return frame


def prepare_positions(positions: pd.DataFrame) -> pd.DataFrame:
    """리밸런싱 포지션 테이블 정리."""
    if positions.empty:
        return positions.copy()
    frame = positions.copy()
    frame["rebalance_date"] = pd.to_datetime(frame["rebalance_date"])
    return frame.sort_values(["rebalance_date", "side", "Ticker"]).reset_index(drop=True)


@dataclass(frozen=True)
class BacktestExportPayload:
    """단일 실행 파일보내기 입력."""

    run_id: str
    strategy: BacktestStrategy
    scope: BacktestRunScope
    daily_returns: pd.DataFrame
    positions: pd.DataFrame
    metrics: BacktestMetrics
    export_format: ExportFormat = "parquet"


@dataclass(frozen=True)
class BacktestManifestContext:
    """manifest.json 생성 컨텍스트."""

    run_id: str
    strategy: BacktestStrategy
    scope: BacktestRunScope
    metrics: BacktestMetrics
    artifacts: dict[str, str]
    export_format: ExportFormat


def build_manifest(context: BacktestManifestContext) -> dict[str, Any]:
    """실행 단위 manifest (시장·설정은 메타데이터로만 기록)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": context.run_id,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "export_format": context.export_format,
        "scope": {
            "markets": context.scope.markets,
            "start_date": context.scope.start_date,
            "end_date": context.scope.end_date,
            "ticker_count": context.scope.ticker_count,
            "trading_days": context.scope.trading_days,
            "rebalance_count": context.scope.rebalance_count,
        },
        "strategy": context.strategy.to_dict(),
        "metrics": context.metrics.to_dict(),
        "artifacts": context.artifacts,
        "artifact_columns": {
            "daily_returns": [
                "Date",
                "strategy_return",
                "benchmark_return",
                "equity",
                "drawdown",
                "cumulative_return",
                "benchmark_equity",
                "benchmark_cumulative_return",
            ],
            "positions": ["rebalance_date", "Ticker", "side", "weight"],
            "summary": list(context.metrics.to_dict().keys()),
        },
    }


def save_backtest_run(
    output_dir: Path,
    payload: BacktestExportPayload,
) -> BacktestExportResult:
    """단일 실행 결과를 output_dir/{run_id}/ 아래에 저장."""
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / payload.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    daily = prepare_daily_returns(
        payload.daily_returns,
        initial_capital=payload.strategy.initial_capital,
    )
    positions_prepared = prepare_positions(payload.positions)
    summary = metrics_to_dataframe(payload.metrics)

    artifacts: dict[str, str] = {"manifest": "manifest.json"}
    artifacts.update(
        _write_table(run_dir, "daily_returns", daily, payload.export_format),
    )
    artifacts.update(
        _write_table(run_dir, "positions", positions_prepared, payload.export_format),
    )
    artifacts.update(
        _write_table(run_dir, "summary", summary, payload.export_format),
    )

    manifest = build_manifest(
        BacktestManifestContext(
            run_id=payload.run_id,
            strategy=payload.strategy,
            scope=payload.scope,
            metrics=payload.metrics,
            artifacts=artifacts,
            export_format=payload.export_format,
        )
    )
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    _update_runs_index(
        output_dir,
        {
            "run_id": payload.run_id,
            "factor_name": payload.strategy.factor_name,
            "position_mode": payload.strategy.position_mode,
            "weight_method": payload.strategy.weight_method,
            "opt_lookback": payload.strategy.opt_lookback,
            "markets": payload.scope.markets,
            "export_format": payload.export_format,
            "created_at": manifest["created_at"],
            "path": payload.run_id,
            "metrics": {
                "cagr": payload.metrics.cagr,
                "max_drawdown": payload.metrics.max_drawdown,
                "sharpe": payload.metrics.sharpe,
            },
        },
    )

    return BacktestExportResult(
        run_id=payload.run_id,
        run_dir=run_dir,
        manifest_path=manifest_path,
    )


def _write_table(
    run_dir: Path,
    name: str,
    frame: pd.DataFrame,
    export_format: ExportFormat,
) -> dict[str, str]:
    """테이블을 지정 형식으로 저장하고 artifact 경로 맵을 반환."""
    artifacts: dict[str, str] = {}
    if export_format in ("parquet", "both"):
        parquet_name = f"{name}.parquet"
        frame.to_parquet(run_dir / parquet_name, index=False)
        artifacts[name] = parquet_name
    if export_format in ("csv", "both"):
        csv_name = f"{name}.csv"
        frame.to_csv(run_dir / csv_name, index=False)
        csv_key = name if export_format == "csv" else f"{name}_csv"
        artifacts[csv_key] = csv_name
    return artifacts


def _update_runs_index(output_dir: Path, entry: dict[str, Any]) -> None:
    """출력 루트에 실행 목록 인덱스 갱신 (웹·시각화 탐색용)."""
    index_path = output_dir / RUNS_INDEX_FILENAME
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {"schema_version": SCHEMA_VERSION, "runs": []}

    runs: list[dict[str, Any]] = index.get("runs", [])
    runs = [run for run in runs if run.get("run_id") != entry["run_id"]]
    runs.insert(0, entry)
    index["runs"] = runs
    index["updated_at"] = datetime.now(tz=UTC).isoformat()
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
