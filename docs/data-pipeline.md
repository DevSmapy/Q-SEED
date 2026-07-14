# 데이터 파이프라인 (Phase 1)

한국·미국 주식 시장 데이터를 수집하고 DuckDB에 적재한 뒤, dbt로 품질 검증·리포트를 수행하는 Phase 1 가이드입니다.

전체 CLI 옵션·환경 변수는 [cli-reference.md](cli-reference.md)를 참고하세요.

## 데이터 수집 파이프라인

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

## 저장 구조

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

스키마·경로 전체는 [architecture.md](architecture.md)를 참고하세요.

## dbt 변환 레이어

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

## 로컬 웹 조회 API

`src/qseed/web/`에 DuckDB 검색용 HTTP 서버가 있습니다. 정적 HTML과 REST API를 함께 제공합니다.

주요 엔드포인트: `/api/health`, `/api/summary`, `/api/search`, `/api/ticker`, `/api/market`

## 개발 환경

- **uv** 기반 의존성 관리
- **Ruff** (lint/format), **mypy** (정적 타입 검사)
- **pre-commit** 훅 및 GitHub Actions CI (`main` 브랜치 push/PR 시 실행)
- **Docker Compose**로 컨테이너 개발 환경 제공

초기 환경 구성은 [getting-started.md](getting-started.md)를 참고하세요.

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

**공백 감지·복구**

증분 업데이트는 전역 `MAX(Date)` 대신 **청크 내 티커별 `last_date` 최솟값**을 시작일로 사용합니다. 중단 후 재실행해도 일부만 갱신된 티커가 뒤처지지 않습니다.

`--check-gaps` / `--repair-gaps`는 **시장별 최신일** 대비 `gap_tolerance_days`(기본 5일) 이상 뒤처진 티커만 대상으로 합니다. 미국 7/2 vs 한국 7/6 같은 휴장 차이는 공백으로 잡지 않습니다.

전체 CLI 옵션·환경 변수는 [cli-reference.md](cli-reference.md#1-데이터-수집)를 참고하세요.

### 2. dbt 실행

파이프라인으로 `data/stocks.db`를 만든 뒤, 프로젝트 루트에서 실행합니다. `profiles.yml`에 DuckDB 경로를 설정해야 합니다.

```bash
uv run dbt run --select stocks
```

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

---

## 참고

- `data/`, `target/`, `logs/`, `profiles.yml`, `research/` 등 런타임·로컬 산출물은 `.gitignore`에 포함되어 있습니다.
- GCS 업로드는 `QSEED_GCS_BUCKET_NAME`이 설정된 경우에만 full 적재 시 Parquet 파일에 대해 동작합니다.
- Streamlit stocks 리뷰 대시보드: `PYTHONPATH=src uv run streamlit run src/qseed/dashboard/app.py`
