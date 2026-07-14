# Q-SEED

> **Quant Strategy Evaluation & Engine Development**

한국·미국 주식 시장 데이터를 자동으로 수집하고, DuckDB에 적재한 뒤 dbt로 품질 검증까지 수행하는 퀀트 연구용 데이터 파이프라인입니다.
장기 목표는 팩터 연구, 백테스팅, 포트폴리오 최적화로 이어지는 **자동 투자 연구 환경**을 구축하는 것입니다.

현재는 **Phase 1 — 데이터 인프라**, **Phase 2 — 팩터 라이브러리**, **Phase 3 — 백테스팅 엔진**,
**Phase 4 — 포트폴리오 최적화**까지 구현된 상태입니다.

Q-SEED는 데이터 수집·팩터 평가·백테스트·가중치 최적화를 담당하는 **연구용 백엔드 엔진**입니다.
AI/ML 기반 시그널·자동매매는 이 엔진 위에 얹는 **후속 프로젝트**로 분리합니다.

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

## 아키텍처 개요

```text
StockProvider  →  YFinanceFetcher  →  DuckDB / Parquet  →  dbt
                                              ↓
                    Factor IC  →  Backtest  →  Optimize
```

상세 디렉토리·스키마·산출물 경로는 [docs/architecture.md](docs/architecture.md)를 참고하세요.

---

## 빠른 시작

```bash
git clone <repository-url>
cd Q-SEED
make setup
uv run qseed --help
```

Docker를 쓰려면 `make docker-up` 후 `make docker-shell`로 접속합니다.

자세한 설치·설정은 [docs/getting-started.md](docs/getting-started.md)를 참고하세요.

---

## 문서

| 문서                                                | 설명                               |
| --------------------------------------------------- | ---------------------------------- |
| [docs/README.md](docs/README.md)                    | 문서 허브 (목차)                   |
| [시작하기](docs/getting-started.md)                 | uv / Docker, `profiles.yml`·`.env` |
| [아키텍처](docs/architecture.md)                    | 디렉토리·DuckDB·산출물 경로        |
| [데이터 파이프라인](docs/data-pipeline.md)          | Phase 1 수집·dbt·대시보드          |
| [팩터 분석](docs/factor-analysis.md)                | Phase 2 IC·분위수                  |
| [백테스팅](docs/backtesting.md)                     | Phase 3 시뮬레이션                 |
| [포트폴리오 최적화](docs/portfolio-optimization.md) | Phase 4 가중치                     |
| [CLI 레퍼런스](docs/cli-reference.md)               | 전체 CLI 옵션·환경 변수            |
| [케이스 스터디](docs/case-studies/)                 | KR 팩터 IC / 백테스트 / 최적화     |

---

## 기술 스택

| 영역        | 사용 기술                                    |
| ----------- | -------------------------------------------- |
| 언어·패키지 | Python 3.11–3.12, uv, pydantic-settings      |
| 수집·저장   | FinanceDataReader, yfinance, DuckDB, Parquet |
| 변환·시각화 | dbt-core/dbt-duckdb, Streamlit, Plotly       |
| 분석        | Pandas, SciPy, quantstats, pyportfolioopt    |
| 품질·배포   | Ruff, mypy, pre-commit, Docker, GCS (선택)   |

**quantstats**는 Phase 3 성과 지표에, **pyportfolioopt**는 Phase 4 가중치 최적화에 사용합니다.
PySpark, dbt-bigquery 등도 의존성에 포함되어 있습니다.
