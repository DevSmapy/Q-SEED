"""내장 팩터 레지스트리."""

from __future__ import annotations

from src.factors import price_factors
from src.factors.base import FactorSpec

FACTOR_REGISTRY: dict[str, FactorSpec] = {
    "momentum_12_1": FactorSpec(
        name="momentum_12_1",
        description="12-1개월 모멘텀 (최근 1개월 제외 12개월 수익률)",
        higher_is_better=True,
        min_history_days=252,
        compute=price_factors.compute_momentum_12_1,
    ),
    "momentum_6m": FactorSpec(
        name="momentum_6m",
        description="6개월 모멘텀",
        higher_is_better=True,
        min_history_days=126,
        compute=price_factors.compute_momentum_6m,
    ),
    "reversal_5d": FactorSpec(
        name="reversal_5d",
        description="5일 단기 반전 (최근 5일 수익률의 음수)",
        higher_is_better=True,
        min_history_days=5,
        compute=price_factors.compute_reversal_5d,
    ),
    "volatility_60d": FactorSpec(
        name="volatility_60d",
        description="60일 수익률 변동성",
        higher_is_better=False,
        min_history_days=60,
        compute=price_factors.compute_volatility_60d,
    ),
    "volume_ratio_20d": FactorSpec(
        name="volume_ratio_20d",
        description="20일 평균 대비 거래량 비율",
        higher_is_better=True,
        min_history_days=20,
        compute=price_factors.compute_volume_ratio_20d,
    ),
    "log_dollar_volume": FactorSpec(
        name="log_dollar_volume",
        description="로그 달러 거래대금 (유동성·규모 프록시)",
        higher_is_better=True,
        min_history_days=1,
        compute=price_factors.compute_log_dollar_volume,
    ),
}


def get_factor(name: str) -> FactorSpec:
    """이름으로 팩터 스펙 조회."""
    try:
        return FACTOR_REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(FACTOR_REGISTRY))
        msg = f"알 수 없는 팩터: {name}. 사용 가능: {available}"
        raise KeyError(msg) from exc


def list_factors() -> list[FactorSpec]:
    """등록된 팩터 목록."""
    return [FACTOR_REGISTRY[name] for name in sorted(FACTOR_REGISTRY)]
