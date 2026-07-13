# Q-SEED

> **Quant Strategy Evaluation & Engine Development**

한국·미국 주식 시장 데이터를 자동으로 수집하고, DuckDB에 적재한 뒤 dbt로 품질 검증까지 수행하는 퀀트 연구용 데이터 파이프라인입니다.
장기 목표는 팩터 연구, 백테스팅, 포트폴리오 최적화로 이어지는 **자동 투자 연구 환경**을 구축하는 것입니다.

현재는 **Phase 1 — 데이터 인프라**, **Phase 2 — 팩터 라이브러리**, **Phase 3 — 백테스팅 엔진**,
**Phase 4 — 포트폴리오 최적화**까지 구현된 상태입니다.

Q-SEED는 데이터 수집·팩터 평가·백테스트·가중치 최적화를 담당하는 **연구용 백엔드 엔진**입니다.
AI/ML 기반 시그널·자동매매는 이 엔진 위에 얹는 **후속 프로젝트**로 분리합니다.

---

## 현재 구현 범위

### 데이터 수집 파이프라인

`qseed` CLI가 `StockDataPipeline`을 실행하여 아래 흐름을 처리합니다.

```text
StockProvider  →  YFinanceFetcher  →  DuckDBRepository  →  ParquetRepository
(FinanceDataReader)   (yfinance)         (stocks.db)         (Parquet 백업)
                                              ↓
                                        GCSUploader (선택)
```

**지원 시장 (7개)**

| 시장                        | 티커 접미사 |
| --------------------------- | ----------- |
| KOSPI, KONEX                | `.KS`       |
| KOSDAQ                      | `.KQ`       |
| S&P 500, NASDAQ, NYSE, AMEX | 없음        |

**수집 데이터**

- 일별 OHLCV (수정 주가 기준)
- 배당금(`Dividends`), 액면분할(`Split`)
- 시장 구분(`Market`)

**동작 방식**

1. `FinanceDataReader`로 시장별 종목 목록을 조회하고, 중복 티커를 제거합니다.
2. 종목을 청크 단위로 나눠 `yfinance`에서 일괄 다운로드합니다.
3. DuckDB `raw_stocks` 테이블에 적재하고, `(Ticker, Date)` 기준 중복을 제거합니다.
4. 청크별 Parquet 파일을 `data/` 아래에 저장합니다.
5. 수집 결과(성공/실패 티커, 마지막 거래일)를 `data/data_log/`에 기록합니다.

**적재 모드**

- `full`: 테이블을 초기화한 뒤 전체 재적재
- `incremental`: 티커별 `last_date` 기준 증분 수집 (`--update-db`). 청크 내 최소 `last_date`를 시작일로 사용해 중단 후 재실행 시 공백을 방지합니다. 완료 후 시장별 공백 티커를 자동 복구합니다.

### 저장 구조

**DuckDB — `data/stocks.db`**

```sql
raw_stocks (
    Date, Ticker, Market,
    Open, High, Low, Close, Volume,
    Dividends, Split
)
```

**런타임 산출물 — `data/data_log/`**

| 파일                      | 설명                     |
| ------------------------- | ------------------------ |
| `krx_list.csv`            | 수집 대상 티커·시장 목록 |
| `completed_data_list.txt` | 수집 성공 티커           |
| `no_data_list.txt`        | 데이터 없음/실패 티커    |
| `last_date.txt`           | DB 내 최신 거래일        |
| `qseed_run.log`           | 실행 로그                |

### dbt 변환 레이어

프로젝트 루트의 `dbt_project.yml` 설정으로 DuckDB(`stocks.db`)의 `raw_stocks`를 **stocks 도메인** 모델로 변환합니다.
환율·거시 등 다른 도메인과는 분리되어 있으며, `dbt/models/stocks/` 아래만 참조합니다.

| 모델                              | 설명                        |
| --------------------------------- | --------------------------- |
| `stg_stocks__raw_stocks`          | `raw_stocks` 스테이징       |
| `dim_stocks__market`              | Market → country / currency |
| `rpt_stocks__overview`            | 전체 KPI                    |
| `rpt_stocks__coverage_by_market`  | 시장별 종목·행 수           |
| `rpt_stocks__coverage_by_country` | 국가별 종목·행 수           |
| `rpt_stocks__freshness`           | 시장별 최신일·지연          |
| `rpt_stocks__history_length`      | 티커별 히스토리 길이        |
| `rpt_stocks__data_quality`        | 누락률·거래량 0·OHLC 이상   |
| `rpt_stocks__return_stats`        | 시장층화 수익률·기술통계    |

무거운 참조 모델(`int_stocks__daily_returns`, `fct_stocks__price_factors`)은 기본 비활성입니다.

### 로컬 웹 조회 API

`src/qseed/web/`에 DuckDB 검색용 HTTP 서버가 있습니다. 정적 HTML과 REST API를 함께 제공합니다.

주요 엔드포인트: `/api/health`, `/api/summary`, `/api/search`, `/api/ticker`, `/api/market`

### 팩터 라이브러리 (Phase 2)

OHLCV 데이터로 팩터를 계산하고, **IC(Information Coefficient)** 와 **분위수(Quintile)** 분석을 수행합니다.

**내장 팩터 (6개)**

| 팩터                | 설명                             |
| ------------------- | -------------------------------- |
| `momentum_12_1`     | 12-1개월 모멘텀                  |
| `momentum_6m`       | 6개월 모멘텀                     |
| `reversal_5d`       | 5일 단기 반전                    |
| `volatility_60d`    | 60일 수익률 변동성               |
| `volume_ratio_20d`  | 20일 평균 대비 거래량 비율       |
| `log_dollar_volume` | 로그 달러 거래대금 (규모·유동성) |

**분석 흐름**

```text
DuckDB (raw_stocks)  →  Factor.compute()  →  IC / Quintile 분석
                              ↓
                    factor_values, factor_ic_*, factor_quintile_* 테이블
                              ↓
                    data/factor_analysis/{factor}/ (Parquet·JSON)
```

**dbt 팩터 모델** (기본 비활성 — 필요 시 `dbt run --select int_stocks__daily_returns fct_stocks__price_factors`)

| 모델                        | 설명                         |
| --------------------------- | ---------------------------- |
| `int_stocks__daily_returns` | 일간·21일 선행 수익률        |
| `fct_stocks__price_factors` | SQL 기반 팩터 값 (참조·검증) |

### 백테스팅 엔진 (Phase 3)

팩터 분위수 기반 **롱숏 / 롱온리** 전략을 시뮬레이션하고 CAGR, MDD, Sharpe 등 성과 지표를 산출합니다.
웹 서비스 연동을 고려해 `BacktestRunConfig`·`run_id` 단위로 실행·저장·조회가 가능합니다.

**전략 구성**

| 항목        | 기본값        | 설명                                  |
| ----------- | ------------- | ------------------------------------- |
| 포지션 모드 | `long_short`  | 롱숏(Q5−Q1) 또는 `long_only`          |
| 리밸런싱    | 21거래일      | CLI·환경 변수로 변경 가능             |
| 가중치      | 동일가중      | 롱·숏 각 50% (롱숏), 롱 100% (롱온리) |
| 거래비용    | 0 bps         | 리밸런싱 시 턴오버 기반 차감          |
| 벤치마크    | 동일가중 시장 | 대상 유니버스 전 종목 동일가중        |

**시뮬레이션 흐름**

```text
DuckDB (raw_stocks)  →  Factor.compute()  →  분위수 포지션 구성
                              ↓
                    일별 수익률 누적 (리밸런싱 주기마다 재구성)
                              ↓
                    quantstats 성과 지표 (CAGR, MDD, Sharpe, …)
                              ↓
                    backtest_* 테이블 + data/backtest/case_study_kr/{run_id}/
```

**파일 출력 구조** (시장 구분은 디렉토리가 아닌 `manifest.json`·`runs_index.json` 메타데이터로 관리)

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

**DuckDB 테이블**

| 테이블                   | 설명                                           |
| ------------------------ | ---------------------------------------------- |
| `backtest_daily_returns` | 일별 전략·벤치마크 수익률, equity, drawdown    |
| `backtest_positions`     | 리밸런싱일별 보유 종목·가중치                  |
| `backtest_summary`       | CAGR, MDD, Sharpe 등 실행 요약 (`run_id` 단위) |

### 포트폴리오 최적화 (Phase 4)

팩터 분위수로 **종목을 선정**한 뒤, 동일가중 대신 **수리 최적화**로 가중치를 산출합니다.
선정(selection)과 배분(allocation)을 분리하며, 시뮬레이션은 Phase 3 `BacktestEngine`을 재사용합니다.

**가중치 방법**

| 방법             | 설명                               |
| ---------------- | ---------------------------------- |
| `equal_weight`   | 동일가중 (Phase 3 기본, 비교 기준) |
| `min_volatility` | 최소분산 (기본 최적화 방법)        |
| `max_sharpe`     | 최대 Sharpe (평균-분산)            |
| `hrp`            | Hierarchical Risk Parity           |

**최적화 흐름**

```text
DuckDB (raw_stocks)  →  Factor.compute()  →  분위수 유니버스
                              ↓
                    WeightOptimizer (슬리브별 long-only)
                              ↓
                    BacktestEngine (일별 수익률·성과 지표)
                              ↓
                    backtest_* 테이블 + data/backtest/.../{run_id}/
```

- lookback 기본 252거래일, 슬리브당 `max_assets` 기본 50 (관측치 많은 종목 우선)
- 공분산·기대수익 추정 실패 또는 솔버 오류 시 **동일가중으로 폴백**
- 롱숏이면 롱·숏 슬리브를 각각 최적화한 뒤 각 50%로 정규화

### 개발 환경

- **uv** 기반 의존성 관리
- **Ruff** (lint/format), **mypy** (정적 타입 검사)
- **pre-commit** 훅 및 GitHub Actions CI (`main` 브랜치 push/PR 시 실행)
- **Docker Compose**로 컨테이너 개발 환경 제공

---

## 기술 스택

| 영역            | 사용 기술                              |
| --------------- | -------------------------------------- |
| 언어            | Python 3.11 – 3.12                     |
| 패키지 관리     | uv                                     |
| 설정            | pydantic-settings (`.env` / 환경 변수) |
| 데이터 수집     | FinanceDataReader, yfinance            |
| 저장            | DuckDB, Parquet                        |
| 변환            | dbt-core, dbt-duckdb                   |
| 시각화          | Streamlit, Plotly                      |
| 클라우드 (선택) | Google Cloud Storage                   |
| 품질            | Ruff, mypy, pre-commit                 |

분석·백테스팅용 라이브러리(Pandas, SciPy, **quantstats**, **pyportfolioopt** 등)와 PySpark, dbt-bigquery는 의존성에 포함되어 있습니다.
**quantstats**는 Phase 3 성과 지표에, **pyportfolioopt**는 Phase 4 가중치 최적화에 사용합니다.

---

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

---

## 시작하기

저장소를 클론한 뒤 **uv**(로컬) 또는 **Docker**(컨테이너) 중 하나로 환경을 구성할 수 있습니다.

### 사전 요구사항

| 방식 | 필요 도구 |
| ---- | --------- |
| 로컬 (uv) | [uv](https://docs.astral.sh/uv/getting-started/installation/) |
| Docker | [Docker](https://docs.docker.com/get-docker/) + Docker Compose v2 |

Python 버전은 **3.12**를 권장합니다 (`.python-version` 참고).

### 빠른 시작 (uv)

```bash
git clone <repository-url>
cd Q-SEED

# 한 번에 초기화: 의존성 설치, profiles.yml/.env 생성, pre-commit 훅 설치
make setup

# 또는 수동으로
uv sync
cp profiles.yml.example profiles.yml
cp .env.example .env
uv run pre-commit install
```

설치 후 CLI 확인:

```bash
uv run qseed --help
```

### 빠른 시작 (Docker)

```bash
git clone <repository-url>
cd Q-SEED

# 로컬 설정 파일 준비 (dbt·환경 변수용)
cp profiles.yml.example profiles.yml
cp .env.example .env

# 컨테이너 빌드 및 시작
make docker-up

# 컨테이너 셸 접속
make docker-shell
```

컨테이너 내부에서도 동일하게 `uv run`으로 명령을 실행합니다.

```bash
uv run qseed --help
uv run dbt run
```

컨테이너를 중지하려면 `make docker-down`을 실행합니다.

### 설정 파일

| 파일 | 설명 |
| ---- | ---- |
| `profiles.yml.example` | dbt DuckDB 연결 템플릿 → `profiles.yml`로 복사 |
| `.env.example` | 환경 변수 템플릿 → `.env`로 복사 |

`profiles.yml`과 `.env`는 git에 포함되지 않습니다. 클론 후 예시 파일을 복사해 사용하세요.

---

## 사용법

### 1. 데이터 수집

```bash
# 전체 DB 구축 (모든 시장, max 기간)
uv run qseed --build-db

# 설정값을 조정해 실행 (시장당 기본 1,000종목, max 기간)
uv run qseed --run-stock-pipeline

# 수집 범위 직접 지정
uv run qseed --run-stock-pipeline --download-period 10y --max-stocks 500

# 증분 업데이트 (티커별 last_date 기준, 종료 후 공백 자동 복구)
uv run python -m src.qseed.cli --update-db --data-dir ./data

# 공백만 탐지 (수집 없음)
uv run python -m src.qseed.cli --check-gaps --data-dir ./data

# 공백 티커만 재수집
uv run python -m src.qseed.cli --repair-gaps --data-dir ./data

# 증분 업데이트 + 자동 복구 끄기
uv run python -m src.qseed.cli --update-db --no-gap-repair --data-dir ./data

# 데이터 저장 경로 지정
uv run python -m src.qseed.cli --build-db --data-dir ./data
```

**CLI 옵션**

| 옵션                   | 설명                                             | 기본값   |
| ---------------------- | ------------------------------------------------ | -------- |
| `--build-db`           | 전 종목·max 기간 전체 적재                       | —        |
| `--update-db`          | 증분 업데이트 (티커별 last_date, 공백 자동 복구) | —        |
| `--check-gaps`         | 시장별 공백 티커 탐지 (수집 없음)                | —        |
| `--repair-gaps`        | 공백 티커만 재수집                               | —        |
| `--no-gap-repair`      | `--update-db` 후 자동 공백 복구 비활성화         | —        |
| `--run-stock-pipeline` | 파이프라인 실행                                  | —        |
| `--mode`               | `full` / `incremental`                           | `full`   |
| `--data-dir`           | 데이터 저장 디렉토리                             | `./data` |
| `--max-stocks`         | 시장별 최대 종목 수                              | `1000`   |
| `--download-period`    | yfinance 기간 (`1y`, `5y`, `max` 등)             | `max`    |
| `--chunk-size`         | 청크당 종목 수                                   | `100`    |
| `--sleep-interval`     | 청크 간 대기(초)                                 | `5.0`    |
| `--start-date`         | 수집 시작일 (`YYYY-MM-DD`, incremental)          | —        |
| `--end-date`           | 수집 종료일 (`YYYY-MM-DD`, incremental)          | —        |

**공백 감지·복구**

증분 업데이트는 전역 `MAX(Date)` 대신 **청크 내 티커별 `last_date` 최솟값**을 시작일로 사용합니다. 중단 후 재실행해도 일부만 갱신된 티커가 뒤처지지 않습니다.

`--check-gaps` / `--repair-gaps`는 **시장별 최신일** 대비 `gap_tolerance_days`(기본 5일) 이상 뒤처진 티커만 대상으로 합니다. 미국 7/2 vs 한국 7/6 같은 휴장 차이는 공백으로 잡지 않습니다.

```bash
QSEED_STOCK_GAP_TOLERANCE_DAYS=5
QSEED_STOCK_AUTO_REPAIR_GAPS=true
```

### 2. dbt 실행

파이프라인으로 `data/stocks.db`를 만든 뒤, 프로젝트 루트에서 실행합니다. `profiles.yml`에 DuckDB 경로를 설정해야 합니다.

```bash
uv run dbt run --select stocks
```

### 3. 환경 변수

`.env` 파일 또는 환경 변수로 설정합니다. 접두사는 `QSEED_STOCK_`, `QSEED_GCS_`입니다.

```bash
cp .env.example .env   # 로컬 전용; .env는 gitignore됨
# .env 예시:
QSEED_STOCK_BASE_DIR=./data
# 외장 디스크 등 절대경로가 필요하면:
# QSEED_STOCK_BASE_DIR=/path/to/your/Q-SEED/data
QSEED_STOCK_MAX_STOCKS=500
QSEED_STOCK_CHUNK_SIZE=50
QSEED_GCS_BUCKET_NAME=my-bucket   # 설정 시 Parquet GCS 업로드 활성화
```

코드 기본값은 `./data`입니다. 머신별 절대경로는 소스에 넣지 말고 `.env`에만 둡니다.

### 4. Stocks 리뷰 대시보드 (Streamlit)

```bash
PYTHONPATH=src uv run streamlit run src/qseed/dashboard/app.py
```

dbt `rpt_stocks_*` 테이블과 `data_log/` 수집 로그를 읽어 Overview / Coverage / Freshness / Descriptive / Ticker 페이지를 제공합니다.

### 5. 웹 조회 서버 (선택)

DuckDB가 준비된 상태에서 실행합니다.

```bash
PYTHONPATH=src uv run python -m qseed.web.server --db data/stocks.db
```

### 6. 팩터 분석

DuckDB에 주가 데이터가 적재된 뒤 실행합니다.

```bash
# 등록된 팩터 목록
uv run qseed --list-factors

# 기본 팩터(momentum_12_1) IC·분위수 분석
uv run qseed --run-factor-analysis

# 특정 팩터·시장 지정
uv run qseed --run-factor-analysis --factor reversal_5d --market KOSPI --market KOSDAQ

# 선행 수익률 기간(거래일) 변경
uv run qseed --run-factor-analysis --factor momentum_6m --forward-horizon 63
```

**CLI 옵션 (팩터)**

| 옵션                    | 설명                       | 기본값          |
| ----------------------- | -------------------------- | --------------- |
| `--run-factor-analysis` | 팩터 IC·분위수 분석 실행   | —               |
| `--list-factors`        | 등록된 팩터 목록 출력      | —               |
| `--factor`              | 분석 팩터 이름             | `momentum_12_1` |
| `--market`              | 대상 시장 (반복 지정 가능) | 전체            |
| `--forward-horizon`     | 선행 수익률 기간(거래일)   | `21`            |

**환경 변수 (팩터)**

```bash
QSEED_FACTOR_FORWARD_HORIZON=21
QSEED_FACTOR_MIN_OBSERVATIONS=30
QSEED_FACTOR_DEFAULT_FACTOR=momentum_12_1
```

**분석 산출물**

- DuckDB 테이블: `factor_values`, `factor_ic_daily`, `factor_ic_summary`, `factor_quintile_returns`, `factor_quintile_summary`
- 파일: `data/factor_analysis/{factor}/` (Parquet, `analysis_report.json`)

### 7. 백테스트

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

**CLI 옵션 (백테스트)**

| 옵션                     | 설명                                        | 기본값                              |
| ------------------------ | ------------------------------------------- | ----------------------------------- |
| `--run-backtest`         | 팩터 백테스트 실행                          | —                                   |
| `--factor`               | 대상 팩터                                   | `reversal_5d`                       |
| `--market`               | 대상 시장 (반복 지정 가능)                  | 전체                                |
| `--position-mode`        | `long_short` / `long_only`                  | `long_short`                        |
| `--long-only`            | 롱온리 모드 (위 옵션 단축)                  | —                                   |
| `--rebalance-freq`       | 리밸런싱 주기(거래일)                       | `21`                                |
| `--transaction-cost-bps` | 거래비용 (bps)                              | `0`                                 |
| `--backtest-output-dir`  | 결과 출력 경로                              | `{data_dir}/backtest/case_study_kr` |
| `--export-format`        | 결과 파일 형식 (`parquet` / `csv` / `both`) | `parquet`                           |

**환경 변수 (백테스트)**

```bash
QSEED_BACKTEST_REBALANCE_FREQ=21
QSEED_BACKTEST_TRANSACTION_COST_BPS=0
QSEED_BACKTEST_INITIAL_CAPITAL=100000000
QSEED_BACKTEST_DEFAULT_FACTOR=reversal_5d
QSEED_BACKTEST_POSITION_MODE=long_short
QSEED_BACKTEST_OUTPUT_DIR=./data/backtest/case_study_kr
QSEED_BACKTEST_EXPORT_FORMAT=parquet
```

**백테스트 산출물**

- DuckDB 테이블: `backtest_daily_returns`, `backtest_positions`, `backtest_summary`
- 파일: `data/backtest/case_study_kr/{run_id}/` (`manifest.json`, Parquet)
- 실행 목록: `data/backtest/case_study_kr/runs_index.json`

### 8. 포트폴리오 최적화

팩터 분위수 유니버스에 최소분산·HRP 등 가중치를 적용해 백테스트합니다.

```bash
# 기본: min_volatility
uv run python -m src.qseed.cli --run-optimize \
  --factor reversal_5d \
  --market KOSPI --market KOSDAQ

# 동일가중 / HRP 비교
uv run python -m src.qseed.cli --run-optimize \
  --factor reversal_5d \
  --market KOSPI --market KOSDAQ \
  --weight-method equal_weight

uv run python -m src.qseed.cli --run-optimize \
  --factor reversal_5d \
  --market KOSPI --market KOSDAQ \
  --weight-method hrp \
  --opt-lookback 252 \
  --opt-max-assets 50

# Phase 3 CLI에서도 가중치 방법 지정 가능
uv run python -m src.qseed.cli --run-backtest \
  --factor reversal_5d \
  --weight-method min_volatility
```

**CLI 옵션 (최적화)**

| 옵션               | 설명                                                     | 기본값           |
| ------------------ | -------------------------------------------------------- | ---------------- |
| `--run-optimize`   | 팩터 선정 + 가중치 최적화 백테스트                       | —                |
| `--weight-method`  | `equal_weight` / `min_volatility` / `max_sharpe` / `hrp` | `min_volatility` |
| `--opt-lookback`   | 공분산·기대수익 lookback (거래일)                        | `252`            |
| `--opt-max-assets` | 슬리브당 최적화 최대 종목 수                             | `50`             |

**환경 변수 (최적화)**

```bash
QSEED_OPTIMIZE_WEIGHT_METHOD=min_volatility
QSEED_OPTIMIZE_LOOKBACK=252
QSEED_OPTIMIZE_MAX_ASSETS=50
QSEED_OPTIMIZE_DEFAULT_FACTOR=reversal_5d
QSEED_OPTIMIZE_POSITION_MODE=long_short
```

### 케이스 스터디: KOSPI·KOSDAQ 팩터 IC (2026-07)

실제 `stocks.db`(9,431종목, 2026-07-06 기준)에서 **KOSPI·KOSDAQ 2,778종목**을 대상으로 6개 팩터를 분석했습니다.

**설정**

| 항목              | 값                         |
| ----------------- | -------------------------- |
| 대상 시장         | KOSPI, KOSDAQ              |
| 선행 수익률       | 21거래일                   |
| IC                | 일별 단면 Spearman         |
| 분위수            | 5분위, Q5−Q1 롱숏 스프레드 |
| 최소 단면 종목 수 | 30                         |

**실행** (6개 팩터 일괄)

```bash
# .env의 QSEED_STOCK_BASE_DIR 또는 --data-dir 사용
for factor in momentum_12_1 momentum_6m reversal_5d volatility_60d volume_ratio_20d log_dollar_volume; do
  uv run qseed --run-factor-analysis \
    --factor "$factor" \
    --market KOSPI --market KOSDAQ
done
```

단일 팩터 예시:

```bash
uv run qseed --run-factor-analysis \
  --factor reversal_5d \
  --market KOSPI --market KOSDAQ
```

**결과 요약** (산출물: `data/factor_analysis/case_study_kr/case_study_summary.json`)

| 팩터                | IC mean    | IC IR     | Hit rate | Q5−Q1 spread | 해석                                                              |
| ------------------- | ---------- | --------- | -------- | ------------ | ----------------------------------------------------------------- |
| `reversal_5d`       | **+0.036** | **+0.36** | 64%      | **+0.81%**   | 단기 반전 유효 (최근 5일 하락 종목이 이후 21일 수익 우세)         |
| `momentum_12_1`     | +0.016     | +0.14     | 57%      | −0.17%       | 모멘텀 신호 약함, 분위수 스프레드 미미                            |
| `momentum_6m`       | −0.026     | −0.21     | 43%      | −0.80%       | 6개월 모멘텀은 역방향 (한국 시장 반전 성격)                       |
| `volatility_60d`    | −0.106     | −0.73     | 22%      | +1.35%\*     | 저변동성 종목이 이후 수익 우세 (\*낮을수록 유리 → Q1−Q5 스프레드) |
| `volume_ratio_20d`  | +0.002     | +0.03     | 53%      | +0.48%       | 거래량 급증 신호는 IC·스프레드 모두 미약                          |
| `log_dollar_volume` | −0.088     | −0.67     | 23%      | −3.39%       | 고유동성·대형주가 이후 21일 수익 열위                             |

**시사점**

1. **단기 반전(`reversal_5d`)** 이 한국 시장 샘플에서 가장 일관된 IC·분위수 스프레드를 보였습니다.
2. **중기 모멘텀(`momentum_6m`)** 은 오히려 역신호에 가깝습니다. 12-1 모멘텀은 유의미하지 않습니다.
3. **저변동성(`volatility_60d`)** 은 IC가 음수이지만, 팩터 방향(낮을수록 유리) 기준 롱숏 스프레드는 양수입니다.
4. **거래량 비율(`volume_ratio_20d`)** 은 예측력이 거의 없고, **로그 달러 거래대금(`log_dollar_volume`)** 은 소형·저유동성 종목이 이후 수익에서 우세합니다.

> Phase 3 백테스팅에서는 위 팩터 중 `reversal_5d`, `volatility_60d`를 우선 전략 후보로 검증했습니다.

### 케이스 스터디: KOSPI·KOSDAQ 팩터 백테스트 (2026-07)

Phase 2 IC 케이스 스터디와 동일한 **KOSPI·KOSDAQ** 유니버스로 롱숏 백테스트를 실행했습니다.

**설정**

| 항목      | 값                            |
| --------- | ----------------------------- |
| 대상 시장 | KOSPI, KOSDAQ                 |
| 포지션    | 롱숏 (동일가중, 롱·숏 각 50%) |
| 리밸런싱  | 21거래일                      |
| 거래비용  | 0 bps                         |
| 벤치마크  | 동일 유니버스 동일가중        |

**실행**

```bash
for factor in reversal_5d volatility_60d; do
  uv run python -m src.qseed.cli --run-backtest \
    --factor "$factor" \
    --market KOSPI --market KOSDAQ \
    --data-dir "./data"
done

# 출력 경로 지정
uv run python -m src.qseed.cli --run-backtest \
  --factor reversal_5d \
  --market NASDAQ \
  --backtest-output-dir "./data/backtest/custom_runs"
```

**결과 요약** (산출물: `data/backtest/case_study_kr/backtest_summary.json`)

| 팩터             | CAGR   | MDD    | Sharpe | Win rate | Total return | 해석                                              |
| ---------------- | ------ | ------ | ------ | -------- | ------------ | ------------------------------------------------- |
| `reversal_5d`    | +0.32% | −61.7% | +0.12  | 51%      | +8.7%        | IC 신호와 방향 일치, 절대 수익은 완만             |
| `volatility_60d` | −3.28% | −92.1% | −0.07  | 48%      | −58.2%       | 분위수 스프레드와 달리 복리 시뮬레이션에서는 열위 |

**시사점**

1. **IC·분위수 분석과 백테스트는 다른 질문**에 답합니다. 전자는 단면 예측력, 후자는 실제 리밸런싱·복리 수익입니다.
2. **`reversal_5d`** 는 양(+) Sharpe로 Phase 2 IC 결과와 방향이 일치하나, MDD가 크고 벤치마크 대비 초과수익은 없습니다.
3. **`volatility_60d`** 는 IC 기반 분위수 스프레드는 양(+)이었으나, 동일가중 롱숏 백테스트에서는 손실이 컸습니다. 향후 비용·유니버스 필터·롱온리 등 추가 검증이 필요합니다.
4. 웹 서비스 확장을 위해 각 실행은 `run_id`로 식별되며, `BacktestRepository.list_backtest_runs()`로 이력 조회가 가능합니다.

### 케이스 스터디: KOSPI·KOSDAQ 가중치 최적화 (2026-07)

Phase 3와 동일한 **KOSPI·KOSDAQ / `reversal_5d` / 롱숏 / 21일 리밸런싱** 조건에서
동일가중·최소분산·HRP 가중치를 비교했습니다. 최적화 시 슬리브당 최대 50종목(`opt_max_assets`)을 사용합니다.

**실행**

```bash
DATA_DIR="/path/to/data"   # stocks.db 위치
OUT_DIR="./data/backtest/case_study_kr"
for method in equal_weight min_volatility hrp; do
  uv run python -m src.qseed.cli --run-optimize \
    --factor reversal_5d \
    --market KOSPI --market KOSDAQ \
    --weight-method "$method" \
    --data-dir "$DATA_DIR" \
    --backtest-output-dir "$OUT_DIR" \
    --opt-lookback 252 \
    --opt-max-assets 50
done
```

**결과 요약** (산출물: `data/backtest/case_study_kr/optimize_summary.json`)

| weight_method    | CAGR   | MDD    | Sharpe | Win rate | 해석                                            |
| ---------------- | ------ | ------ | ------ | -------- | ----------------------------------------------- |
| `equal_weight`   | +7.63% | −39.6% | +0.47  | 51%      | 기준선 (동일가중 롱숏)                          |
| `min_volatility` | +7.26% | −26.7% | +0.50  | 50%      | CAGR 유사, MDD·Sharpe 개선                      |
| `hrp`            | +7.59% | −21.7% | +0.40  | 50%      | MDD가 가장 낮음, Sharpe는 기준선 대비 소폭 하락 |

**시사점**

1. **선정은 팩터, 배분은 최적화**로 나누면 MDD를 줄일 수 있습니다. `min_volatility`·`hrp` 모두 동일가중 대비 낙폭이 작습니다.
2. **`min_volatility`** 는 CAGR을 크게 희생하지 않으면서 Sharpe를 소폭 올렸습니다.
3. **`hrp`** 는 MDD 완화에 가장 효과적이었으나 Sharpe는 기준선보다 낮았습니다.
4. 대규모 분위수 유니버스에서는 `opt_max_assets`로 후보를 제한합니다. 솔버 실패 시 해당 리밸런싱은 동일가중으로 폴백합니다.

---

## 로드맵

| Phase                     | 목표                                 | 상태     |
| ------------------------- | ------------------------------------ | -------- |
| 1. Data Infrastructure    | 전 종목 주가 자동 적재·품질 검증     | **완료** |
| 2. Factor Library         | 팩터 구현 및 IC·분위수 분석          | **완료** |
| 3. Backtesting Engine     | CAGR, MDD, Sharpe 등 성과 지표       | **완료** |
| 4. Portfolio Optimization | 평균-분산·최소분산·HRP 가중치 최적화 | **완료** |

AI/ML 기반 시그널·자동매매는 Q-SEED 범위 밖이며, 본 엔진(데이터·평가·최적화) 위에 얹는 **후속 프로젝트**로 진행합니다.

---

## 참고

- `data/`, `target/`, `logs/`, `profiles.yml`, `research/` 등 런타임·로컬 산출물은 `.gitignore`에 포함되어 있습니다.
- GCS 업로드는 `QSEED_GCS_BUCKET_NAME`이 설정된 경우에만 full 적재 시 Parquet 파일에 대해 동작합니다.
- Streamlit stocks 리뷰 대시보드: `PYTHONPATH=src uv run streamlit run src/qseed/dashboard/app.py`
