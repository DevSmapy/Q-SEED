# 백테스팅 엔진 (Phase 3)

팩터 분위수 기반 **롱숏 / 롱온리** 전략을 시뮬레이션하고 CAGR, MDD, Sharpe 등 성과 지표를 산출합니다.
웹 서비스 연동을 고려해 `BacktestRunConfig`·`run_id` 단위로 실행·저장·조회가 가능합니다.

전체 CLI 옵션·환경 변수는 [cli-reference.md](cli-reference.md#7-백테스트)를 참고하세요.

## 전략 구성

| 항목        | 기본값        | 설명                                  |
| ----------- | ------------- | ------------------------------------- |
| 포지션 모드 | `long_short`  | 롱숏(Q5−Q1) 또는 `long_only`          |
| 리밸런싱    | 21거래일      | CLI·환경 변수로 변경 가능             |
| 가중치      | 동일가중      | 롱·숏 각 50% (롱숏), 롱 100% (롱온리) |
| 거래비용    | 0 bps         | 리밸런싱 시 턴오버 기반 차감          |
| 벤치마크    | 동일가중 시장 | 대상 유니버스 전 종목 동일가중        |

## 시뮬레이션 흐름

```text
DuckDB (raw_stocks)  →  Factor.compute()  →  분위수 포지션 구성
                              ↓
                    일별 수익률 누적 (리밸런싱 주기마다 재구성)
                              ↓
                    quantstats 성과 지표 (CAGR, MDD, Sharpe, …)
                              ↓
                    backtest_* 테이블 + data/backtest/case_study_kr/{run_id}/
```

## 파일 출력 구조

시장 구분은 디렉토리가 아닌 `manifest.json`·`runs_index.json` 메타데이터로 관리합니다.

```text
data/backtest/case_study_kr/          # 기본 출력 경로 (--backtest-output-dir로 변경 가능)
├── runs_index.json                   # 실행 목록 인덱스 (웹·시각화 탐색용)
└── {run_id}/                         # 예: reversal_5d_20260707_102526
    ├── manifest.json                 # scope(시장·기간), 전략, 지표, 파일 목록
    ├── daily_returns.parquet         # equity, drawdown, cumulative_return 포함
    ├── positions.parquet             # 리밸런싱별 보유 종목
    └── summary.parquet               # CAGR, MDD, Sharpe 등 요약
```

NASDAQ 등 미국 시장 실행 시에도 **동일한 디렉토리 구조**를 사용하며, `manifest.json`의 `scope.markets`에 `["NASDAQ"]` 등으로 기록됩니다.

## DuckDB 테이블

| 테이블                   | 설명                                           |
| ------------------------ | ---------------------------------------------- |
| `backtest_daily_returns` | 일별 전략·벤치마크 수익률, equity, drawdown    |
| `backtest_positions`     | 리밸런싱일별 보유 종목·가중치                  |
| `backtest_summary`       | CAGR, MDD, Sharpe 등 실행 요약 (`run_id` 단위) |

스키마·경로 상세는 [architecture.md](architecture.md)를 참고하세요.

## 사용법

팩터 IC 분석 이후, 동일한 DuckDB 데이터로 롱숏/롱온리 전략 백테스트를 실행합니다.

```bash
# 기본 팩터(reversal_5d) 롱숏 백테스트
uv run python -m src.qseed.cli --run-backtest

# 특정 팩터·시장 지정
uv run python -m src.qseed.cli --run-backtest \
  --factor reversal_5d \
  --market KOSPI --market KOSDAQ

# 롱온리, 리밸런싱 주기 변경
uv run python -m src.qseed.cli --run-backtest \
  --factor volatility_60d \
  --long-only \
  --rebalance-freq 42

# CSV로보내기 (Plotly·Excel 연동용)
uv run python -m src.qseed.cli --run-backtest \
  --factor reversal_5d \
  --export-format csv

# Parquet + CSV 동시 저장
uv run python -m src.qseed.cli --run-backtest \
  --factor reversal_5d \
  --export-format both
```

**백테스트 산출물**

- DuckDB 테이블: `backtest_daily_returns`, `backtest_positions`, `backtest_summary`
- 파일: `data/backtest/case_study_kr/{run_id}/` (`manifest.json`, Parquet)
- 실행 목록: `data/backtest/case_study_kr/runs_index.json`

전체 CLI 옵션·환경 변수는 [cli-reference.md](cli-reference.md#7-백테스트)를 참고하세요.

## 케이스 스터디

- [KOSPI·KOSDAQ 팩터 백테스트 (2026-07)](case-studies/2026-07-kr-backtest.md)
- Phase 2 IC 선행 연구: [팩터 IC 케이스 스터디](case-studies/2026-07-kr-factor-ic.md)
