# Q-SEED

> **Quant Strategy Evaluation & Engine Development**

한국·미국 주식 시장 데이터를 자동으로 수집하고, DuckDB에 적재한 뒤 dbt로 품질 검증까지 수행하는 퀀트 연구용 데이터 파이프라인입니다.
장기 목표는 팩터 연구, 백테스팅, 포트폴리오 최적화로 이어지는 **자동 투자 연구 환경**을 구축하는 것입니다.

현재는 **Phase 1 — 데이터 인프라**와 **Phase 2 — 팩터 라이브러리**가 완료된 상태입니다.

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

**dbt 팩터 모델**

| 모델                | 설명                         |
| ------------------- | ---------------------------- |
| `int_daily_returns` | 일간·21일 선행 수익률        |
| `fct_price_factors` | SQL 기반 팩터 값 (참조·검증) |

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
│   ├── factors/            # 팩터 계산 (Phase 2)
│   ├── analysis/           # IC·분위수 분석 (Phase 2)
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

### 로컬 환경

```bash
# 의존성 설치
uv sync

# pre-commit 훅 설치
uv run pre-commit install
```

### Docker

```bash
docker compose up -d --build
docker compose exec q-seed bash
```

컨테이너 내부에서도 `uv run`으로 동일하게 명령을 실행합니다.

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

### 5. 팩터 분석

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
DATA_DIR="/Volumes/WD_BLACK/Careers/PythonProjects/Q-SEED/data"
for factor in momentum_12_1 momentum_6m reversal_5d volatility_60d volume_ratio_20d log_dollar_volume; do
  uv run qseed --run-factor-analysis \
    --factor "$factor" \
    --market KOSPI --market KOSDAQ \
    --data-dir "$DATA_DIR"
done
```

단일 팩터 예시:

```bash
uv run qseed --run-factor-analysis \
  --factor reversal_5d \
  --market KOSPI --market KOSDAQ \
  --data-dir "/Volumes/WD_BLACK/Careers/PythonProjects/Q-SEED/data"
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

> Phase 3(백테스팅)에서는 위 팩터 중 `reversal_5d`, `volatility_60d`를 우선 전략 후보로 검증할 수 있습니다.

---

## 로드맵

| Phase                  | 목표                             | 상태     |
| ---------------------- | -------------------------------- | -------- |
| 1. Data Infrastructure | 전 종목 주가 자동 적재·품질 검증 | **완료** |
| 2. Factor Library      | 팩터 구현 및 IC·분위수 분석      | **완료** |
| 3. Backtesting Engine  | CAGR, MDD, Sharpe 등 성과 지표   | 예정     |
| 4. AI & Optimization   | ML 기반 포트폴리오 최적화        | 예정     |

---

## 참고

- `data/`, `target/`, `logs/`, `profiles.yml`, `research/` 등 런타임·로컬 산출물은 `.gitignore`에 포함되어 있습니다.
- GCS 업로드는 `QSEED_GCS_BUCKET_NAME`이 설정된 경우에만 full 적재 시 Parquet 파일에 대해 동작합니다.
- Streamlit 대시보드(`src/repositories/dashboard.py`)는 dbt 모델 기반 시각화를 위한 준비 단계입니다.
