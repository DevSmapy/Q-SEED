# 팩터 분석 (Phase 2)

OHLCV 데이터로 팩터를 계산하고, **IC(Information Coefficient)** 와 **분위수(Quintile)** 분석을 수행합니다.

전체 CLI 옵션·환경 변수는 [cli-reference.md](cli-reference.md#6-팩터-분석)를 참고하세요.

## 팩터 라이브러리

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

## 사용법

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

**분석 산출물**

- DuckDB 테이블: `factor_values`, `factor_ic_daily`, `factor_ic_summary`, `factor_quintile_returns`, `factor_quintile_summary`
- 파일: `data/factor_analysis/{factor}/` (Parquet, `analysis_report.json`)

스키마·경로 상세는 [architecture.md](architecture.md)를 참고하세요.

전체 CLI 옵션·환경 변수는 [cli-reference.md](cli-reference.md#6-팩터-분석)를 참고하세요.

## 케이스 스터디

- [KOSPI·KOSDAQ 팩터 IC (2026-07)](case-studies/2026-07-kr-factor-ic.md)
