# 케이스 스터디: KOSPI·KOSDAQ 팩터 IC (2026-07)

> **이름에 있는 `2026-07`**: 최초 연구 실행 달입니다.
> 아래 IC 표는 당시 요약을 유지합니다. 이 환경에는 재검증용
> `stocks.db`와 `analysis_report.json`이 없어 **숫자를 새로 돌리지는 못했고**,
> 경로·CLI만 현재 코드에 맞췄습니다. DB가 있으면 같은 명령으로 재실행한 뒤
> `data/factor_analysis/{factor}/analysis_report.json`을 인용하세요.

당시 기록: `stocks.db` 기준 **2026-07-06**, 전체 약 9,431종목 중 **KOSPI·KOSDAQ 2,778종목**.

관련 가이드: [팩터 분석 (Phase 2)](../factor-analysis.md)

## 설정

| 항목              | 값                         |
| ----------------- | -------------------------- |
| 대상 시장         | KOSPI, KOSDAQ              |
| 선행 수익률       | 21거래일                   |
| IC                | 일별 단면 Spearman         |
| 분위수            | 5분위, Q5−Q1 롱숏 스프레드 |
| 최소 단면 종목 수 | 30                         |

## 실행

6개 팩터 일괄:

```bash
for factor in momentum_12_1 momentum_6m reversal_5d volatility_60d volume_ratio_20d log_dollar_volume; do
  uv run qseed --run-factor-analysis \
    --factor "$factor" \
    --market KOSPI --market KOSDAQ
done
```

단일 팩터 예시:

```bash
uv run qseed --run-factor-analysis \
  --factor reversal_5d \
  --market KOSPI --market KOSDAQ
```

## 결과 요약

**현재 코드 산출물 경로** (팩터별):

`data/factor_analysis/{factor}/analysis_report.json`
(+ `ic_summary.parquet`, `quintile_summary.parquet`)

예전 문서가 가리키던 `data/factor_analysis/case_study_kr/case_study_summary.json`은
엔진이 만들지 않습니다.

| 팩터                | IC mean    | IC IR     | Hit rate | Q5−Q1 spread | 해석                                                              |
| ------------------- | ---------- | --------- | -------- | ------------ | ----------------------------------------------------------------- |
| `reversal_5d`       | **+0.036** | **+0.36** | 64%      | **+0.81%**   | 단기 반전 유효 (최근 5일 하락 종목이 이후 21일 수익 우세)         |
| `momentum_12_1`     | +0.016     | +0.14     | 57%      | −0.17%       | 모멘텀 신호 약함, 분위수 스프레드 미미                            |
| `momentum_6m`       | −0.026     | −0.21     | 43%      | −0.80%       | 6개월 모멘텀은 역방향 (한국 시장 반전 성격)                       |
| `volatility_60d`    | −0.106     | −0.73     | 22%      | +1.35%\*     | 저변동성 종목이 이후 수익 우세 (\*낮을수록 유리 → Q1−Q5 스프레드) |
| `volume_ratio_20d`  | +0.002     | +0.03     | 53%      | +0.48%       | 거래량 급증 신호는 IC·스프레드 모두 미약                          |
| `log_dollar_volume` | −0.088     | −0.67     | 23%      | −3.39%       | 고유동성·대형주가 이후 21일 수익 열위                             |

## 시사점

1. **단기 반전(`reversal_5d`)** 이 한국 시장 샘플에서 가장 일관된 IC·분위수 스프레드를 보였습니다.
2. **중기 모멘텀(`momentum_6m`)** 은 오히려 역신호에 가깝습니다. 12-1 모멘텀은 유의미하지 않습니다.
3. **저변동성(`volatility_60d`)** 은 IC가 음수이지만, 팩터 방향(낮을수록 유리) 기준 롱숏 스프레드는 양수입니다.
4. **거래량 비율(`volume_ratio_20d`)** 은 예측력이 거의 없고, **로그 달러 거래대금(`log_dollar_volume`)** 은 소형·저유동성 종목이 이후 수익에서 우세합니다.

> Phase 3 백테스팅에서는 위 팩터 중 `reversal_5d`, `volatility_60d`를 우선 전략 후보로 검증했습니다.
> → [백테스트 케이스 스터디](2026-07-kr-backtest.md)
