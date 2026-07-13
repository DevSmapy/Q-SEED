# Q-SEED

> **Quant Strategy Evaluation & Engine Development**

한국·미국 주식 시장 데이터를 자동으로 수집하고, DuckDB에 적재한 뒤 dbt로 품질 검증까지 수행하는 퀀트 연구용 데이터 파이프라인입니다.
장기 목표는 팩터 연구, 백테스팅, 포트폴리오 최적화로 이어지는 **자동 투자 연구 환경**을 구축하는 것입니다.

현재는 **Phase 1 — 데이터 인프라**가 구현된 상태입니다.

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
- `incremental`: DB의 마지막 거래일 이후 데이터만 추가 수집 (`--update-db` 또는 `--mode incremental`)

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

프로젝트 루트의 `dbt_project.yml` 설정으로 DuckDB(`data/stocks.db`)의 `raw_stocks`를 소스로 변환 모델을 생성합니다.

| 모델                 | 설명                                                         |
| -------------------- | ------------------------------------------------------------ |
| `stg_raw_stocks`     | `raw_stocks` 스테이징                                        |
| `count_by_markets`   | 시장별 종목 수 집계                                          |
| `data_quality`       | 티커별 누락률, 영업일 대비 수집일, 거래량 0일·종가 결측 검사 |
| `rpt_ticker_details` | 시장·종목별 수집 기간·행 수 요약                             |

소스 테스트(`sources.yml`)로 `Date`, `Ticker`의 not-null 검증을 포함합니다.

### 로컬 웹 조회 API

`src/qseed/web/`에 DuckDB 검색용 HTTP 서버가 있습니다. 정적 HTML과 REST API를 함께 제공합니다.

주요 엔드포인트: `/api/health`, `/api/summary`, `/api/search`, `/api/ticker`, `/api/market`

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
| 시각화 (준비)   | Streamlit, Plotly                      |
| 클라우드 (선택) | Google Cloud Storage                   |
| 품질            | Ruff, mypy, pre-commit                 |

분석·백테스팅용 라이브러리(Pandas, SciPy, quantstats, pyportfolioopt 등)와 PySpark, dbt-bigquery는 의존성에 포함되어 있으나, **현재 파이프라인에서는 사용하지 않습니다.**

---

## 디렉토리 구조

```text
Q-SEED/
├── src/
│   ├── qseed/              # CLI, 설정, 웹 서버
│   ├── providers/          # 종목 목록 (FinanceDataReader)
│   ├── fetchers/           # 주가 수집 (yfinance)
│   ├── repositories/       # DuckDB, Parquet, 조회/미리보기, 대시보드
│   ├── pipelines/          # stock_pipeline
│   ├── uploaders/          # GCS
│   └── utils/
├── dbt/
│   ├── models/             # dbt SQL 모델
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

# 증분 업데이트 (마지막 거래일 이후)
uv run qseed --update-db

# 데이터 저장 경로 지정
uv run qseed --build-db --data-dir ./data
```

**CLI 옵션**

| 옵션                   | 설명                                    | 기본값   |
| ---------------------- | --------------------------------------- | -------- |
| `--build-db`           | 전 종목·max 기간 전체 적재              | —        |
| `--update-db`          | 증분 업데이트 (모든 시장)               | —        |
| `--run-stock-pipeline` | 파이프라인 실행                         | —        |
| `--mode`               | `full` / `incremental`                  | `full`   |
| `--data-dir`           | 데이터 저장 디렉토리                    | `./data` |
| `--max-stocks`         | 시장별 최대 종목 수                     | `1000`   |
| `--download-period`    | yfinance 기간 (`1y`, `5y`, `max` 등)    | `max`    |
| `--chunk-size`         | 청크당 종목 수                          | `100`    |
| `--sleep-interval`     | 청크 간 대기(초)                        | `5.0`    |
| `--start-date`         | 수집 시작일 (`YYYY-MM-DD`, incremental) | —        |
| `--end-date`           | 수집 종료일 (`YYYY-MM-DD`, incremental) | —        |

### 2. dbt 실행

파이프라인으로 `data/stocks.db`를 만든 뒤, 프로젝트 루트에서 실행합니다. `profiles.yml`에 DuckDB 경로를 설정해야 합니다.

```bash
uv run dbt run
uv run dbt test
```

### 3. 환경 변수

`.env` 파일 또는 환경 변수로 설정합니다. 접두사는 `QSEED_STOCK_`, `QSEED_GCS_`입니다.

```bash
# 예시
QSEED_STOCK_BASE_DIR=./data
QSEED_STOCK_MAX_STOCKS=500
QSEED_STOCK_CHUNK_SIZE=50
QSEED_GCS_BUCKET_NAME=my-bucket   # 설정 시 Parquet GCS 업로드 활성화
```

### 4. 웹 조회 서버 (선택)

DuckDB가 준비된 상태에서 실행합니다.

```bash
PYTHONPATH=src uv run python -m qseed.web.server --db data/stocks.db
```

---

## 로드맵

| Phase                  | 목표                             | 상태        |
| ---------------------- | -------------------------------- | ----------- |
| 1. Data Infrastructure | 전 종목 주가 자동 적재·품질 검증 | **진행 중** |
| 2. Factor Library      | 팩터 구현 및 IC·분위수 분석      | 예정        |
| 3. Backtesting Engine  | CAGR, MDD, Sharpe 등 성과 지표   | 예정        |
| 4. AI & Optimization   | ML 기반 포트폴리오 최적화        | 예정        |

---

## 참고

- `data/`, `target/`, `logs/`, `profiles.yml`, `research/` 등 런타임·로컬 산출물은 `.gitignore`에 포함되어 있습니다.
- GCS 업로드는 `QSEED_GCS_BUCKET_NAME`이 설정된 경우에만 full 적재 시 Parquet 파일에 대해 동작합니다.
- Streamlit 대시보드(`src/repositories/dashboard.py`)는 dbt 모델 기반 시각화를 위한 준비 단계입니다.
