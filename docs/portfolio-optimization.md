# 포트폴리오 최적화 (Phase 4)

팩터 분위수로 **종목을 선정**한 뒤, 동일가중 대신 **수리 최적화**(**pyportfolioopt**)로 가중치를 산출합니다.
선정(selection)과 배분(allocation)을 분리하며, 시뮬레이션은 Phase 3 `BacktestEngine`을 재사용합니다.

전체 CLI 옵션·환경 변수는 [cli-reference.md](cli-reference.md#8-포트폴리오-최적화)를 참고하세요.

## 가중치 방법

| 방법             | 설명                               |
| ---------------- | ---------------------------------- |
| `equal_weight`   | 동일가중 (Phase 3 기본, 비교 기준) |
| `min_volatility` | 최소분산 (기본 최적화 방법)        |
| `max_sharpe`     | 최대 Sharpe (평균-분산)            |
| `hrp`            | Hierarchical Risk Parity           |

## 최적화 흐름

```text
DuckDB (raw_stocks)  →  Factor.compute()  →  분위수 유니버스
                              ↓
                    WeightOptimizer (슬리브별 long-only)
                              ↓
                    BacktestEngine (일별 수익률·성과 지표)
                              ↓
                    backtest_* 테이블 + data/backtest/.../{run_id}/
```

- lookback 기본 252거래일, 슬리브당 `max_assets` 기본 50 (관측치 많은 종목 우선)
- 공분산·기대수익 추정 실패 또는 솔버 오류 시 **동일가중으로 폴백**
- 롱숏이면 롱·숏 슬리브를 각각 최적화한 뒤 각 50%로 정규화

산출물 경로·테이블은 [architecture.md](architecture.md)와 [backtesting.md](backtesting.md)를 참고하세요.

## 사용법

팩터 분위수 유니버스에 최소분산·HRP 등 가중치를 적용해 백테스트합니다.

```bash
# 기본: min_volatility
uv run python -m src.qseed.cli --run-optimize \
  --factor reversal_5d \
  --market KOSPI --market KOSDAQ

# 동일가중 / HRP 비교
uv run python -m src.qseed.cli --run-optimize \
  --factor reversal_5d \
  --market KOSPI --market KOSDAQ \
  --weight-method equal_weight

uv run python -m src.qseed.cli --run-optimize \
  --factor reversal_5d \
  --market KOSPI --market KOSDAQ \
  --weight-method hrp \
  --opt-lookback 252 \
  --opt-max-assets 50

# Phase 3 CLI에서도 가중치 방법 지정 가능
uv run python -m src.qseed.cli --run-backtest \
  --factor reversal_5d \
  --weight-method min_volatility
```

전체 CLI 옵션·환경 변수는 [cli-reference.md](cli-reference.md#8-포트폴리오-최적화)를 참고하세요.

## 케이스 스터디

- [KOSPI·KOSDAQ 가중치 최적화 (2026-07)](case-studies/2026-07-kr-optimize.md)
- Phase 3 선행 연구: [팩터 백테스트 케이스 스터디](case-studies/2026-07-kr-backtest.md)
