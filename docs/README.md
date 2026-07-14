# Q-SEED 문서

Quant Strategy Evaluation & Engine Development — 연구용 백엔드 엔진 문서 허브입니다.

환경 구성부터 시작해 Phase별 가이드 → CLI 레퍼런스 → 케이스 스터디 순으로 보시면 됩니다.

## 시작

| 문서                           | 설명                                            |
| ------------------------------ | ----------------------------------------------- |
| [시작하기](getting-started.md) | 사전 요구사항, uv/Docker, `profiles.yml`·`.env` |
| [아키텍처](architecture.md)    | 디렉토리 구조, DuckDB 스키마, 산출물 경로       |

## Phase 가이드

| Phase | 문서                                           | 설명                                  |
| ----- | ---------------------------------------------- | ------------------------------------- |
| 1     | [데이터 파이프라인](data-pipeline.md)          | 수집, dbt, 웹 API, Streamlit 대시보드 |
| 2     | [팩터 분석](factor-analysis.md)                | 내장 팩터, IC·분위수 분석             |
| 3     | [백테스팅](backtesting.md)                     | 롱숏/롱온리 시뮬레이션, 성과 지표     |
| 4     | [포트폴리오 최적화](portfolio-optimization.md) | min_volatility, max_sharpe, HRP       |

## 레퍼런스

| 문서                             | 설명                                       |
| -------------------------------- | ------------------------------------------ |
| [CLI 레퍼런스](cli-reference.md) | 전체 CLI 옵션·환경 변수 (단일 진실 공급원) |

## 케이스 스터디

| 문서                                                         | 설명                                |
| ------------------------------------------------------------ | ----------------------------------- |
| [KR 팩터 IC (2026-07)](case-studies/2026-07-kr-factor-ic.md) | KOSPI·KOSDAQ 6개 팩터 IC·분위수     |
| [KR 백테스트 (2026-07)](case-studies/2026-07-kr-backtest.md) | `reversal_5d`·`volatility_60d` 롱숏 |
| [KR 최적화 (2026-07)](case-studies/2026-07-kr-optimize.md)   | 동일가중 vs min_volatility vs HRP   |

프로젝트 요약·로드맵은 [루트 README](../README.md)를 참고하세요.
