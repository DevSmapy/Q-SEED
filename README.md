# Q-SEED 📈

> **Quant Strategy Evaluation & Engine Development**

**Q-SEED**는 데이터 기반의 퀀트 투자 전략을 체계적으로 연구하고, 백테스팅 엔진을 직접 구현하며 자산 관리 자동화로 나아가기 위한 첫 번째 마일스톤 프로젝트입니다.

---

## 🎯 Project Overview

본 프로젝트는 《파이썬을 이용한 퀀트 투자 포트폴리오 만들기》를 기반으로 학습하며, 최종적으로 **AI 기반의 자동 포트폴리오 관리 및 매매 시스템** 구축을 목표로 합니다.

### Core Objectives

1. **Data Pipeline:** 금융 데이터 API 및 크롤링을 활용한 데이터 수집 자동화
2. **Factor Research:** 가치, 모멘텀, 퀄리티 등 다양한 투자 팩터 구현 및 검증
3. **Engine Development:** 수익률, 변동성, MDD를 분석할 수 있는 자체 백테스팅 모듈 개발
4. **Insight to Action:** 실전 투자를 위한 종목 스크리닝 및 포트폴리오 최적화

---

## 🛠 Tech Stack

- **Language:** Python 3.14
- **Distributed Processing:** [Apache Spark (PySpark)](https://spark.apache.org/docs/latest/api/python/index.html)
- **Package Manager:** [uv](https://github.com/astral-sh/uv)
- **Analysis:** Pandas, NumPy, Scipy
- **Visualization:** Matplotlib, Plotly
- **Data Source:** FinanceDataReader, BeautifulSoup4

---

## 📂 Directory Structure

```text
/Q-SEED
│── /research          # 실습 및 아이디어 스케치 (Jupyter Notebooks)
│── /data              # 분석용 금융 데이터 (CSV, DB)
│── /src               # 재사용 가능한 엔진 코어 모듈
│   ├── scraper/       # 데이터 수집기
│   ├── factors/       # 팩터 계산 로직
│   └── backtester/    # 백테스팅 엔진
└── README.md
```

## 📋 Roadmap

프로젝트는 총 4단계의 마일스톤을 통해 진행됩니다.

1. **Phase 1: Data Infrastructure** - 금융 데이터 수집 파이프라인 및 저장 구조 확립
2. **Phase 2: Factor Research** - 팩터 유효성 검증 및 라이브러리 구축
3. **Phase 3: Engine Development** - 백테스팅 엔진 코어 및 성과 지표 모듈 개발
4. **Phase 4: Strategy & Action** - 전략 최적화 및 실전 스크리닝 자동화

---

## 🚀 Getting Started

`uv`를 사용하여 환경을 구축합니다.

```bash
# 의존성 설치 및 가상환경 설정
uv sync

# pre-commit 훅 설치
uv run pre-commit install
```
