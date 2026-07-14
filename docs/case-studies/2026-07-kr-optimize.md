# 케이스 스터디: KOSPI·KOSDAQ 가중치 최적화 (2026-07)

Phase 3와 동일한 **KOSPI·KOSDAQ / `reversal_5d` / 롱숏 / 21일 리밸런싱** 조건에서
동일가중·최소분산·HRP 가중치를 비교했습니다. 최적화 시 슬리브당 최대 50종목(`opt_max_assets`)을 사용합니다.

관련 가이드: [포트폴리오 최적화 (Phase 4)](../portfolio-optimization.md) · 선행: [백테스트 케이스 스터디](2026-07-kr-backtest.md)

## 실행

```bash
DATA_DIR="/path/to/data"   # stocks.db 위치
OUT_DIR="./data/backtest/case_study_kr"
for method in equal_weight min_volatility hrp; do
  uv run python -m src.qseed.cli --run-optimize \
    --factor reversal_5d \
    --market KOSPI --market KOSDAQ \
    --weight-method "$method" \
    --data-dir "$DATA_DIR" \
    --backtest-output-dir "$OUT_DIR" \
    --opt-lookback 252 \
    --opt-max-assets 50
done
```

## 결과 요약

산출물: `data/backtest/case_study_kr/optimize_summary.json`

| weight_method    | CAGR   | MDD    | Sharpe | Win rate | 해석                                            |
| ---------------- | ------ | ------ | ------ | -------- | ----------------------------------------------- |
| `equal_weight`   | +7.63% | −39.6% | +0.47  | 51%      | 기준선 (동일가중 롱숏)                          |
| `min_volatility` | +7.26% | −26.7% | +0.50  | 50%      | CAGR 유사, MDD·Sharpe 개선                      |
| `hrp`            | +7.59% | −21.7% | +0.40  | 50%      | MDD가 가장 낮음, Sharpe는 기준선 대비 소폭 하락 |

## 시사점

1. **선정은 팩터, 배분은 최적화**로 나누면 MDD를 줄일 수 있습니다. `min_volatility`·`hrp` 모두 동일가중 대비 낙폭이 작습니다.
2. **`min_volatility`** 는 CAGR을 크게 희생하지 않으면서 Sharpe를 소폭 올렸습니다.
3. **`hrp`** 는 MDD 완화에 가장 효과적이었으나 Sharpe는 기준선보다 낮았습니다.
4. 대규모 분위수 유니버스에서는 `opt_max_assets`로 후보를 제한합니다. 솔버 실패 시 해당 리밸런싱은 동일가중으로 폴백합니다.
