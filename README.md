# Q-SEED 📈

> **Quant Strategy Evaluation & Engine Development**

**Q-SEED**는 데이터 기반의 퀀트 투자 전략을 체계적으로 연구하고, 백테스팅 엔진을 직접 구현하며 자산 관리 자동화로 나아가기 위한 첫 번째 마일스톤 프로젝트입니다.

---

## 🎯 Project Overview

본 프로젝트는 《파이썬을 이용한 퀀트 투자 포트폴리오 만들기》를 기반으로 학습하며, 최종적으로 **AI 기반의 자동 포트폴리오 관리 및 매매 시스템** 구축을 목표로 합니다.

### Core Objectives (Quantitative & Technical)

1. **Data Pipeline (Reliability & Scalability):**
   - **Coverage:** KOSPI, KOSDAQ 전 종목 (2,500+) 및 미국 주요 종목 (S&P 500) 데이터 수집.
   - **History:** 최근 10년 이상의 일별 수정 주가 및 재무 제표 데이터 확보.
   - **Automation:** PySpark를 활용한 대용량 데이터 ETL (Extract-Transform-Load) 및 Parquet/Delta Lake 저장 구조화.
2. **Factor Research (Statistical Rigor):**
   - **Implementation:** 가치(P/E, P/B), 모멘텀(Relative Strength), 퀄리티(ROE, GPA) 등 10개 이상의 팩터 라이브러리화.
   - **Validation:** 팩터별 IC(Information Coefficient), 10분위수 수익률(Decile Analysis)을 통한 통계적 유효성 검증.
3. **Engine Development (Precision):**
   - **Metrics:** 연평균 수익률(CAGR), 최대 낙폭(MDD), 샤프 지수(Sharpe Ratio), 소르티노 지수(Sortino Ratio) 자동 계산.
   - **Realistic Simulation:** 거래세, 슬리피지(Slippage), 리밸런싱 주기 설정을 포함한 정밀 백테스팅 구현.
4. **Insight to Action (Optimization):**
   - **Strategy:** 월간 리밸런싱 기반의 멀티 팩터 모델 구축 및 포트폴리오 최적화(Mean-Variance, Risk Parity).
   - **Execution:** 선정된 종목 리스트의 자동 생성 및 대시보드 시각화.

---

## 🛠 Tech Stack

- **Language:** Python 3.13
- **Distributed Processing:** [Apache Spark (PySpark)](https://spark.apache.org/docs/latest/api/python/index.html) - 대용량 금융 시계열 데이터 처리 최적화
- **Data Transformation:** dbt (dbt-core, dbt-bigquery) - 데이터 모델링 및 파이프라인 관리
- **Storage:** Delta Lake / DuckDB / BigQuery - 효율적인 데이터 조회 및 스키마 관리
- **Package Manager:** [uv](https://github.com/astral-sh/uv)
- **Analysis:** Pandas, NumPy, Scipy, Statsmodels
- **Visualization:** Plotly (Interactive Charts), Matplotlib
- **Data Source:** FinanceDataReader, yfinance, Tiingo, BeautifulSoup4

---

## 📂 Directory Structure

```text
/Q-SEED
├── /kor_ticker        # 한국 주식 티커 및 데이터 수집/처리 모듈
├── /research          # 실습, 데이터 탐색 및 아이디어 스케치 (Jupyter Notebooks)
│   ├── exploration.ipynb # 데이터 탐색 노트북
│   └── spark-warehouse/  # 로컬 Spark 데이터 임시 저장소
├── docker-compose.yml # Docker 환경 설정
├── Dockerfile         # Docker 이미지 빌드 파일
├── pyproject.toml     # 프로젝트 의존성 및 환경 설정 (uv)
│   ├── factors/       # 팩터 계산 및 유효성 검증 모듈
│   ├── backtester/    # 성과 분석 및 리포팅 엔진
│   └── utils/         # 공통 유틸리티 (로깅, 설정)
└── README.md
```

## 📋 Roadmap & KPIs

프로젝트의 성공 여부를 측정할 수 있는 정량적 지표(KPI)와 함께 진행합니다.

1. **Phase 1: Data Infrastructure (Month 1)**
   - **Goal:** 전 종목 일별 주가 및 재무 데이터의 자동 적재 프로세스 완료.
   - **KPI:** 데이터 누락율 0.1% 미만, 수집 속도 개선 (Spark 병렬 처리 활용).
2. **Phase 2: Factor Library (Month 2)**
   - **Goal:** 주요 퀀트 팩터 10개 이상 구현 및 유효성 분석 리포트 생성.
   - **KPI:** 특정 팩터의 상위 10% 포트폴리오가 벤치마크(KOSPI) 대비 아웃퍼폼 확인.
3. **Phase 3: Backtesting Engine (Month 3)**
   - **Goal:** 실전 매매 제약 조건을 반영한 엔진 개발.
   - **KPI:** 실제 과거 수익률과의 오차 최소화, 성과 리포트 PDF/HTML 자동 생성.
4. **Phase 4: AI & Optimization (Future)**
   - **Goal:** 머신러닝 기반 팩터 가중치 최적화 및 실전 스크리닝 연동.
   - **KPI:** 샤프 지수 1.5 이상의 전략 개발 및 실전 투자 포트폴리오 도출.

---

## 🚀 Getting Started

로컬 환경 혹은 Docker를 사용하여 개발 환경을 구축할 수 있습니다.

### Local (uv)

`uv`를 사용하여 환경을 구축합니다.

```bash
# 의존성 설치 및 가상환경 설정
uv sync

# pre-commit 훅 설치
uv run pre-commit install
```

### Docker

Docker를 사용하면 Python, dbt, Google Cloud SDK가 포함된 일관된 환경을 바로 사용할 수 있습니다.

1. **이미지 빌드 및 컨테이너 실행**

   ```bash
   docker compose up -d --build
   ```

2. **컨테이너 접속**

   ```bash
   docker compose exec q-seed bash
   ```

3. **GCP 인증 (BigQuery 사용 시, 처음 한 번)**

   ```bash
   gcloud auth login
   ```

4. **dbt 실행 확인**
   ```bash
   uv run dbt --version
   ```
