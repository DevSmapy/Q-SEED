# 아키텍처

프로젝트 디렉토리 구조, 데이터 흐름, DuckDB 스키마, 산출물 경로를 정리합니다.

## 디렉토리 구조

```text
Q-SEED/
├── src/
│   ├── qseed/              # CLI, 설정, 웹 서버, stocks 리뷰 대시보드
│   │   └── dashboard/      # Streamlit multipage (stocks only)
│   ├── providers/          # 종목 목록 (FinanceDataReader)
│   ├── fetchers/           # 주가 수집 (yfinance)
│   ├── repositories/       # DuckDB, Parquet, 조회/미리보기
│   ├── pipelines/          # stock_pipeline
│   ├── factors/            # 팩터 계산 (Phase 2)
│   ├── analysis/           # IC·분위수 분석 (Phase 2)
│   ├── backtest/           # 백테스트 엔진 (Phase 3)
│   ├── optimize/           # 포트폴리오 가중치 최적화 (Phase 4)
│   ├── uploaders/          # GCS
│   └── utils/
├── dbt/
│   ├── models/
│   │   └── stocks/         # stocks 도메인 전용 모델 (fx/macro 독립)
│   └── macros/
├── dbt_project.yml         # dbt 프로젝트 설정
├── profiles.yml            # DuckDB 연결 (로컬 설정, git 미추적)
├── data/                   # 런타임 생성 (DB, Parquet, 로그)
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## 데이터 흐름 개요

```text
StockProvider  →  YFinanceFetcher  →  DuckDBRepository  →  ParquetRepository
(FinanceDataReader)   (yfinance)         (stocks.db)         (Parquet 백업)
                                              ↓
                                        GCSUploader (선택)
                                              ↓
                    Factor / Backtest / Optimize (Phase 2–4)
```

## DuckDB 스키마

### Phase 1 — 원시·수집

**DuckDB — `data/stocks.db`**

```sql
raw_stocks (
    Date, Ticker, Market,
    Open, High, Low, Close, Volume,
    Dividends, Split
)
```

### Phase 2 — 팩터 분석

| 테이블                    | 설명          |
| ------------------------- | ------------- |
| `factor_values`           | 팩터 값       |
| `factor_ic_daily`         | 일별 IC       |
| `factor_ic_summary`       | IC 요약       |
| `factor_quintile_returns` | 분위수 수익률 |
| `factor_quintile_summary` | 분위수 요약   |

팩터 테이블은 `factor_name` 기준으로 **해당 팩터 행만 교체**합니다.
다른 팩터의 이전 분석 결과는 유지됩니다. (레거시 `CREATE OR REPLACE` 스키마는
`factor_name` 컬럼이 없으면 해당 테이블을 한 번 버리고 새 스키마로 전환합니다.)

### Phase 3·4 — 백테스트 / 최적화

| 테이블                   | 설명                                           |
| ------------------------ | ---------------------------------------------- |
| `backtest_daily_returns` | 일별 전략·벤치마크 수익률, equity, drawdown    |
| `backtest_positions`     | 리밸런싱일별 보유 종목·가중치                  |
| `backtest_summary`       | CAGR, MDD, Sharpe 등 실행 요약 (`run_id` 단위) |

## 런타임 산출물

### `data/data_log/`

| 파일                      | 설명                     |
| ------------------------- | ------------------------ |
| `krx_list.csv`            | 수집 대상 티커·시장 목록 |
| `completed_data_list.txt` | 수집 성공 티커           |
| `no_data_list.txt`        | 데이터 없음/실패 티커    |
| `last_date.txt`           | DB 내 최신 거래일        |
| `qseed_run.log`           | 실행 로그                |

### `data/factor_analysis/`

```text
data/factor_analysis/{factor}/   # Parquet, analysis_report.json
```

케이스 스터디 요약: `data/factor_analysis/case_study_kr/case_study_summary.json`

### `data/backtest/`

파일 출력 구조 (시장 구분은 디렉토리가 아닌 `manifest.json`·`runs_index.json` 메타데이터로 관리):

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

## 관련 문서

- [데이터 파이프라인](data-pipeline.md)
- [팩터 분석](factor-analysis.md)
- [백테스팅](backtesting.md)
- [포트폴리오 최적화](portfolio-optimization.md)
