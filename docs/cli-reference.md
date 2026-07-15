# CLI 레퍼런스

`qseed` CLI의 전체 옵션과 환경 변수를 모은 단일 진실 공급원(Single Source of Truth)입니다.
사용 예시는 각 Phase 가이드를 참고하세요.

---

## 공통

| 옵션         | 설명                       | 기본값        |
| ------------ | -------------------------- | ------------- |
| `--data-dir` | 데이터 저장 디렉토리       | `./data`      |
| `--market`   | 대상 시장 (반복 지정 가능) | 전체          |
| `--factor`   | 대상 팩터                  | 명령별 기본값 |

환경 변수 접두사: `QSEED_STOCK_`, `QSEED_GCS_`, `QSEED_FACTOR_`, `QSEED_BACKTEST_`, `QSEED_OPTIMIZE_`

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

---

## 1. 데이터 수집

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

**환경 변수 (수집·공백)**

```bash
QSEED_STOCK_BASE_DIR=./data
QSEED_STOCK_MAX_STOCKS=500
QSEED_STOCK_CHUNK_SIZE=50
QSEED_STOCK_GAP_TOLERANCE_DAYS=5
QSEED_STOCK_AUTO_REPAIR_GAPS=true
QSEED_GCS_BUCKET_NAME=my-bucket   # 설정 시 Parquet GCS 업로드 활성화
```

사용 예시는 [data-pipeline.md](data-pipeline.md#1-데이터-수집)를 참고하세요.

---

## 2. dbt

별도 `qseed` 플래그는 없습니다. 프로젝트 루트에서:

```bash
uv run dbt run --select stocks
```

`profiles.yml`에 DuckDB 경로를 설정해야 합니다. 자세한 내용은 [data-pipeline.md](data-pipeline.md#2-dbt-실행)·[getting-started.md](getting-started.md)를 참고하세요.

---

## 3. 환경 변수 (전역)

`.env` 파일 또는 환경 변수로 설정합니다. 접두사는 `QSEED_STOCK_`, `QSEED_GCS_`입니다.

| 변수                     | 설명                                 |
| ------------------------ | ------------------------------------ |
| `QSEED_STOCK_BASE_DIR`   | 데이터 루트 (`./data` 기본)          |
| `QSEED_STOCK_MAX_STOCKS` | 시장별 최대 종목 수                  |
| `QSEED_STOCK_CHUNK_SIZE` | 청크당 종목 수                       |
| `QSEED_GCS_BUCKET_NAME`  | 설정 시 full 적재 Parquet GCS 업로드 |

---

## 4. Stocks 리뷰 대시보드

```bash
PYTHONPATH=src uv run streamlit run src/qseed/dashboard/app.py
```

→ [data-pipeline.md](data-pipeline.md#3-stocks-리뷰-대시보드-streamlit)

---

## 5. 웹 조회 서버

정적 UI 기본 경로: `src/qseed/web/static/research.html` (레포 추적).

```bash
PYTHONPATH=src uv run python -m qseed.web.server --db data/stocks.db
# 또는
make web
```

→ [data-pipeline.md](data-pipeline.md#4-웹-조회-서버-선택)

---

## 6. 팩터 분석

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

사용 예시는 [factor-analysis.md](factor-analysis.md#사용법)를 참고하세요.

---

## 7. 백테스트

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

`--weight-method`는 Phase 4와 공유하며, `--run-backtest`에서도 지정할 수 있습니다. 기본 동일가중은 Phase 3 전략 구성을 따릅니다.

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

사용 예시는 [backtesting.md](backtesting.md#사용법)를 참고하세요.

---

## 8. 포트폴리오 최적화

| 옵션               | 설명                                                     | 기본값           |
| ------------------ | -------------------------------------------------------- | ---------------- |
| `--run-optimize`   | 팩터 선정 + 가중치 최적화 백테스트                       | —                |
| `--weight-method`  | `equal_weight` / `min_volatility` / `max_sharpe` / `hrp` | `min_volatility` |
| `--opt-lookback`   | 공분산·기대수익 lookback (거래일)                        | `252`            |
| `--opt-max-assets` | 슬리브당 최적화 최대 종목 수                             | `50`             |

백테스트와 공유하는 `--factor`, `--market`, `--position-mode`, `--long-only`, `--rebalance-freq`, `--transaction-cost-bps`, `--backtest-output-dir`, `--export-format`, `--data-dir`도 함께 사용할 수 있습니다.

**환경 변수 (최적화)**

```bash
QSEED_OPTIMIZE_WEIGHT_METHOD=min_volatility
QSEED_OPTIMIZE_LOOKBACK=252
QSEED_OPTIMIZE_MAX_ASSETS=50
QSEED_OPTIMIZE_DEFAULT_FACTOR=reversal_5d
QSEED_OPTIMIZE_POSITION_MODE=long_short
```

사용 예시는 [portfolio-optimization.md](portfolio-optimization.md#사용법)를 참고하세요.
