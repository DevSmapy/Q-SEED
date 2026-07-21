# Security Metadata Contract

종목 섹터·업종 메타데이터(`raw_security_metadata` → dbt marts)의 **스키마·enum·정규화 규칙** 계약서입니다.
Python ingest, dbt, Streamlit, downstream AI 투자 엔진이 동일한 정의를 사용합니다.

## Primary keys & join keys

| 용도           | 키                                                 |
| -------------- | -------------------------------------------------- |
| Raw / dim PK   | `(Ticker, Market)`                                 |
| 가격·팩터 JOIN | `Ticker` (Yahoo-style, e.g. `005930.KS`)           |
| 시장 차원      | `Market` → [`dim_stocks__market`](architecture.md) |

## DuckDB — `raw_security_metadata`

```sql
CREATE TABLE IF NOT EXISTS raw_security_metadata (
    Ticker              VARCHAR NOT NULL,
    Market              VARCHAR NOT NULL,
    company_name        VARCHAR,
    quote_type          VARCHAR,          -- yfinance quoteType (EQUITY, ETF, ...)
    sector_raw          VARCHAR,          -- Yahoo sector 원문
    sector              VARCHAR NOT NULL, -- GICS-aligned 11-sector or 'Unclassified'
    industry_raw        VARCHAR,
    industry            VARCHAR,
    sector_key          VARCHAR,          -- Yahoo sectorKey
    industry_key        VARCHAR,
    country             VARCHAR,
    currency            VARCHAR,
    sector_source       VARCHAR NOT NULL, -- 'yfinance' | 'manual' | 'wics' | ...
    sector_status       VARCHAR NOT NULL, -- mapped | unclassified | error
    sector_status_reason VARCHAR,         -- non_equity | missing_yahoo | fetch_error | ...
    as_of               DATE NOT NULL,    -- 메타 수집 기준일
    updated_at          TIMESTAMP NOT NULL,
    PRIMARY KEY (Ticker, Market)
);
```

### Column notes

- `sector`: 항상 NOT NULL. Yahoo에 없으면 `'Unclassified'`.
- `sector_raw`: Yahoo 원문. 없으면 NULL.
- `country` / `currency`: yfinance `info` 또는 `dim_stocks__market` JOIN으로 보강 가능.
- 덮어쓰기 우선순위 (후속 enrichment): `manual > wics > search_engine > yfinance > Unclassified`.

## Enums

### `sector_status`

| 값             | 의미                                    |
| -------------- | --------------------------------------- |
| `mapped`       | Yahoo sector → GICS normalize 성공      |
| `unclassified` | EQUITY이나 sector 없음, 또는 non_equity |
| `error`        | fetch 실패 (재시도 대상)                |

### `sector_status_reason`

| 값              | 의미                                          |
| --------------- | --------------------------------------------- |
| `non_equity`    | ETF, INDEX, MUTUALFUND 등 quote_type ≠ EQUITY |
| `missing_yahoo` | EQUITY인데 sector 키 없음                     |
| `fetch_error`   | `info` 조회 예외 또는 빈 응답                 |
| NULL            | `mapped` 일 때                                |

### `quote_type` (yfinance)

대표값: `EQUITY`, `ETF`, `INDEX`, `MUTUALFUND`, `CRYPTOCURRENCY`, `CURRENCY`, `FUTURE`, `NONE`.

비-EQUITY는 섹터 분류 대상에서 제외하고 `sector = 'Unclassified'`, `sector_status_reason = 'non_equity'`.

## Yahoo → GICS 11-sector normalization

| Yahoo `sector`         | Normalized `sector` (GICS-aligned) |
| ---------------------- | ---------------------------------- |
| Technology             | Information Technology             |
| Financial Services     | Financials                         |
| Healthcare             | Health Care                        |
| Consumer Cyclical      | Consumer Discretionary             |
| Consumer Defensive     | Consumer Staples                   |
| Basic Materials        | Materials                          |
| Energy                 | Energy                             |
| Industrials            | Industrials                        |
| Utilities              | Utilities                          |
| Real Estate            | Real Estate                        |
| Communication Services | Communication Services             |
| (missing / unknown)    | Unclassified                       |

## dbt mart — `dim_stocks__security`

Latest row per `(Ticker, Market)` from `raw_security_metadata`, joined with `dim_stocks__market` for `country` / `currency` when missing.

| Column               | Type    | Notes           |
| -------------------- | ------- | --------------- |
| Ticker               | VARCHAR | PK part         |
| Market               | VARCHAR | PK part         |
| company_name         | VARCHAR |                 |
| quote_type           | VARCHAR |                 |
| sector               | VARCHAR | NOT NULL        |
| industry             | VARCHAR |                 |
| sector_status        | VARCHAR |                 |
| sector_status_reason | VARCHAR |                 |
| sector_source        | VARCHAR |                 |
| as_of                | DATE    |                 |
| country              | VARCHAR | from dim or raw |
| currency             | VARCHAR | from dim or raw |

## dbt mart — `rpt_stocks__coverage_by_sector`

| Column           | Description                       |
| ---------------- | --------------------------------- |
| sector           | GICS-aligned name or Unclassified |
| ticker_count     | distinct tickers                  |
| market           | optional breakdown dimension      |
| unclassified_pct | share of universe                 |

## dbt mart — `rpt_stocks__investable_universe` (Track C)

Price-derived; does not require sector.

| Column            | Description              |
| ----------------- | ------------------------ |
| Ticker, Market    | keys                     |
| adv_20d           | 20-day average volume    |
| dollar_volume_20d | ADV × recent close       |
| liquidity_tier    | high / mid / low         |
| min_history_days  | from history_length mart |
| gap_days          | from freshness mart      |
| investable_flag   | boolean gate             |

Default rule (env-tunable):

```text
investable_flag = adv_20d >= threshold
                AND min_history_days >= 252
                AND gap_days < 5
```

## CLI (Track A)

```bash
uv run qseed --update-security-metadata --data-dir ./data
uv run qseed --update-security-metadata --max-tickers 100 --security-sleep 0.3
```

로컬 dev (M2 Air): `--max-tickers 50~100`. Full universe run은 외장 DB·야간 batch.

## Downstream contract

- Read marts from `stocks.db` after `dbt run`.
- Use `as_of` to avoid look-ahead.
- Sector-neutral strategies: exclude `sector = 'Unclassified'` or treat as separate bucket (document policy).
- Enrichment queue (Track E): `sector_status IN ('unclassified','error') AND quote_type = 'EQUITY'`.

## Deferred (not in v1 contract)

- `marketCap`, `sharesOutstanding`, `cap_tier`
- `rpt_stocks__sector_enrichment_queue` mart
- REST API export
