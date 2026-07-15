# Q-SEED

> **Quant Strategy Evaluation & Engine Development**

로컬 DuckDB warehouse를 구축·관리하고, 그 위에서 팩터·백테스트·포트폴리오 최적화를 검증하는 **퀀트 투자 연구 엔진**입니다.

## What it is / is not

|            |                                                                                                 |
| ---------- | ----------------------------------------------------------------------------------------------- |
| **Is**     | 시세 DB 수집·갱신·품질 확인, 팩터 IC/분위수, 백테스트, 가중치 최적화 (CLI · 로컬 dashboard/web) |
| **Is not** | 자동매매, 브로커 연동, AI/ML 시그널, 공개 Hosted API 서비스                                     |

소비 경로의 기본은 **로컬 CLI + Streamlit/웹 조회**입니다. 공개 API·Hosted 데모는 아래 Future에만 둡니다.

## 데이터 원칙

- **Source of truth**: DuckDB `raw_stocks` (+ Parquet 백업)
- **yfinance / FinanceDataReader**: 배치 수집(`--build-db` / `--update-db`)에만 사용
- **분석·대시보드·로컬 API**: 요청마다 외부 시세를 치지 않고 **warehouse를 읽음**

교차종목 팩터·백테스트는 온디맨드 API보다 물리 적재가 재현성·지연·레이트 리밋 면에서 맞습니다.

## Core loop

```text
Build / update DB  →  Health (dbt · gaps · dashboard)
        →  Factor IC / quintiles  →  Backtest  →  Optimize
```

```text
StockProvider  →  YFinanceFetcher  →  DuckDB / Parquet  →  dbt
                                              ↓
                    Factor IC  →  Backtest  →  Optimize
```

상세 경로는 [docs/architecture.md](docs/architecture.md)를 참고하세요.

## 로드맵

| 구분       | 내용                                                                   | 상태        |
| ---------- | ---------------------------------------------------------------------- | ----------- |
| Phase 1    | Data Infrastructure — 주가 적재·dbt·리뷰 UI                            | **Done**    |
| Phase 2    | Factor Library — IC·분위수                                             | **Done**    |
| Phase 3    | Backtesting — CAGR, MDD, Sharpe 등                                     | **Done**    |
| Phase 4    | Portfolio Optimization — min_vol · max_sharpe · HRP                    | **Done**    |
| **Next**   | 로컬 정합성·UX (팩터 DB 다중 보관, 테스트, CLI/패키징, 의존성 정리 등) | In progress |
| **Future** | Research job API → Self-host 배포 → (선택) 제한 유니버스 Hosted 데모   | Later       |

Future API는 clone 장벽을 낮추기 위함이며, **당분간 구현·운영하지 않습니다.**

## 빠른 시작

```bash
git clone <repository-url>
cd Q-SEED
make setup
uv run qseed --help
```

Docker: `make docker-up` 후 `make docker-shell`.

설치·설정: [docs/getting-started.md](docs/getting-started.md).

## 문서

| 문서                                                | 설명                               |
| --------------------------------------------------- | ---------------------------------- |
| [docs/README.md](docs/README.md)                    | 문서 허브                          |
| [시작하기](docs/getting-started.md)                 | uv / Docker, `profiles.yml`·`.env` |
| [아키텍처](docs/architecture.md)                    | 디렉토리·DuckDB·산출물             |
| [데이터 파이프라인](docs/data-pipeline.md)          | Phase 1 수집·dbt·대시보드          |
| [팩터 분석](docs/factor-analysis.md)                | Phase 2                            |
| [백테스팅](docs/backtesting.md)                     | Phase 3                            |
| [포트폴리오 최적화](docs/portfolio-optimization.md) | Phase 4                            |
| [CLI 레퍼런스](docs/cli-reference.md)               | CLI·환경 변수                      |
| [케이스 스터디](docs/case-studies/)                 | KR IC / 백테스트 / 최적화          |

## 기술 스택

| 영역        | 사용 기술                                    |
| ----------- | -------------------------------------------- |
| 언어·패키지 | Python 3.11–3.12, uv, pydantic-settings      |
| 수집·저장   | FinanceDataReader, yfinance, DuckDB, Parquet |
| 변환·시각화 | dbt-core/dbt-duckdb, Streamlit, Plotly       |
| 분석        | Pandas, SciPy, quantstats, pyportfolioopt    |
| 품질·배포   | Ruff, mypy, pre-commit, Docker, GCS (선택)   |

**quantstats**는 Phase 3 성과 지표에, **pyportfolioopt**는 Phase 4 가중치 최적화에 사용합니다.
PySpark, dbt-bigquery 등은 의존성에 포함될 수 있으나 핵심 로컬 경로에서는 필수가 아닙니다.
