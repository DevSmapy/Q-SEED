# 케이스 스터디: KOSPI·KOSDAQ 팩터 백테스트 (2026-07)

Phase 2 IC 케이스 스터디와 동일한 **KOSPI·KOSDAQ** 유니버스로 롱숏 백테스트를 실행했습니다.

관련 가이드: [백테스팅 (Phase 3)](../backtesting.md) · 선행: [팩터 IC 케이스 스터디](2026-07-kr-factor-ic.md)

## 설정

| 항목      | 값                            |
| --------- | ----------------------------- |
| 대상 시장 | KOSPI, KOSDAQ                 |
| 포지션    | 롱숏 (동일가중, 롱·숏 각 50%) |
| 리밸런싱  | 21거래일                      |
| 거래비용  | 0 bps                         |
| 벤치마크  | 동일 유니버스 동일가중        |

## 실행

```bash
for factor in reversal_5d volatility_60d; do
  uv run python -m src.qseed.cli --run-backtest \
    --factor "$factor" \
    --market KOSPI --market KOSDAQ \
    --data-dir "./data"
done

# 출력 경로 지정
uv run python -m src.qseed.cli --run-backtest \
  --factor reversal_5d \
  --market NASDAQ \
  --backtest-output-dir "./data/backtest/custom_runs"
```

## 결과 요약

산출물: `data/backtest/case_study_kr/backtest_summary.json`

| 팩터             | CAGR   | MDD    | Sharpe | Win rate | Total return | 해석                                              |
| ---------------- | ------ | ------ | ------ | -------- | ------------ | ------------------------------------------------- |
| `reversal_5d`    | +0.32% | −61.7% | +0.12  | 51%      | +8.7%        | IC 신호와 방향 일치, 절대 수익은 완만             |
| `volatility_60d` | −3.28% | −92.1% | −0.07  | 48%      | −58.2%       | 분위수 스프레드와 달리 복리 시뮬레이션에서는 열위 |

## 시사점

1. **IC·분위수 분석과 백테스트는 다른 질문**에 답합니다. 전자는 단면 예측력, 후자는 실제 리밸런싱·복리 수익입니다.
2. **`reversal_5d`** 는 양(+) Sharpe로 Phase 2 IC 결과와 방향이 일치하나, MDD가 크고 벤치마크 대비 초과수익은 없습니다.
3. **`volatility_60d`** 는 IC 기반 분위수 스프레드는 양(+)이었으나, 동일가중 롱숏 백테스트에서는 손실이 컸습니다. 향후 비용·유니버스 필터·롱온리 등 추가 검증이 필요합니다.
4. 웹 서비스 확장을 위해 각 실행은 `run_id`로 식별되며, `BacktestRepository.list_backtest_runs()`로 이력 조회가 가능합니다.

후속: [가중치 최적화 케이스 스터디](2026-07-kr-optimize.md)
