# 케이스 스터디: KOSPI·KOSDAQ 팩터 백테스트 (2026-07)

> **이름에 있는 `2026-07`**: 이 연구를 **처음 수행한 달**입니다. 아래 표는 로컬에 남아 있는
> 실행 산출물에서 옮긴 값이며, 재실행하면 유니버스·코드 버전에 따라 달라질 수 있습니다.

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
  uv run qseed --run-backtest \
    --factor "$factor" \
    --market KOSPI --market KOSDAQ \
    --data-dir "./data"
done
```

## 결과 요약

숫자는 **코드가 만든 산출물**에서만 옮겼습니다. (존재하지 않는
`backtest_summary.json` 경로를 쓰지 않습니다.)

| 팩터             | 출처 run_id / 파일                                                                 | CAGR   | MDD    | Sharpe | Win rate | Total return | 해석                                 |
| ---------------- | ---------------------------------------------------------------------------------- | ------ | ------ | ------ | -------- | ------------ | ------------------------------------ |
| `reversal_5d`    | `data/backtest/case_study_kr/reversal_5d_20260711_125444/manifest.json`            | +7.63% | −39.6% | +0.47  | 51%      | +590%        | Phase 4 `equal_weight`와 **동일 런** |
| `volatility_60d` | `data/backtest/volatility_60d/volatility_60d_20260707_103302/backtest_report.json` | −3.28% | −92.1% | −0.07  | 48%      | −58.2%       | 7/7 산출물 (7/11 재실행 산출물 없음) |

### 이전 문서와의 차이 (정합성)

예전 Phase 3 표의 `reversal_5d`(+0.32% CAGR)는 **2026-07-07** 산출물
(`data/backtest/reversal_5d/reversal_5d_20260707_102526/`)에서 왔습니다.
Phase 4가 인용한 `equal_weight`(+7.63%)는 **2026-07-11** 동일가중 런입니다.
전략 설정(시장·롱숏·21일·0bps)은 같아 보여도 **실행 날짜·데이터 빈티지·출력 스키마가 달라**
숫자가 갈렸습니다. 위 표는 Phase 4와 같은 7/11 `equal_weight` 런으로 `reversal_5d`를 맞췄습니다.

`reversal_5d` 7/11 스코프: 티커 2,778 · 거래일 6,622 · 리밸런싱 316회.

## 시사점

1. **IC·분위수 분석과 백테스트는 다른 질문**에 답합니다. 전자는 단면 예측력, 후자는 실제 리밸런싱·복리 수익입니다.
2. **`reversal_5d` (7/11)** 는 양(+) Sharpe이나 벤치마크 CAGR(약 +25%)에는 미치지 못합니다 (`excess_cagr` 음수).
3. **`volatility_60d` (7/7)** 는 동일가중 롱숏에서 손실이 컸습니다. 7/11과 같은 빈티지로 재검증하려면 `stocks.db`가 필요합니다.
4. 각 실행은 `run_id`로 식별되며, `manifest.json` / `runs_index.json`으로 이력을 추적합니다. 현재 코드는 schema 1.1에서 git·DB provenance도 기록합니다.

후속: [가중치 최적화 케이스 스터디](2026-07-kr-optimize.md)
