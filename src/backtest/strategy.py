"""백테스트 전략 정의."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.factors.base import FactorSpec
from src.factors.registry import get_factor

PositionMode = Literal["long_short", "long_only"]
TOP_QUINTILE = 5
BOTTOM_QUINTILE = 1


@dataclass(frozen=True)
class BacktestStrategy:
    """팩터 기반 백테스트 전략 설정 (API·웹 서비스 직렬화 가능)."""

    factor_name: str
    position_mode: PositionMode = "long_short"
    long_quintile: int | None = None
    short_quintile: int | None = None
    rebalance_freq: int = 21
    min_observations: int = 30
    transaction_cost_bps: float = 0.0
    initial_capital: float = 100_000_000.0

    def resolved_long_quintile(self, *, higher_is_better: bool) -> int:
        if self.long_quintile is not None:
            return self.long_quintile
        return TOP_QUINTILE if higher_is_better else BOTTOM_QUINTILE

    def resolved_short_quintile(self, *, higher_is_better: bool) -> int:
        if self.short_quintile is not None:
            return self.short_quintile
        return BOTTOM_QUINTILE if higher_is_better else TOP_QUINTILE

    def to_dict(self) -> dict[str, object]:
        return {
            "factor_name": self.factor_name,
            "position_mode": self.position_mode,
            "long_quintile": self.long_quintile,
            "short_quintile": self.short_quintile,
            "rebalance_freq": self.rebalance_freq,
            "min_observations": self.min_observations,
            "transaction_cost_bps": self.transaction_cost_bps,
            "initial_capital": self.initial_capital,
        }


@dataclass(frozen=True)
class BacktestStrategyOverrides:
    """팩터 기반 전략 생성 시 덮어쓸 옵션."""

    position_mode: PositionMode = "long_short"
    long_quintile: int | None = None
    short_quintile: int | None = None
    rebalance_freq: int = 21
    min_observations: int = 30
    transaction_cost_bps: float = 0.0
    initial_capital: float = 100_000_000.0


def build_strategy_from_factor(
    factor_name: str,
    overrides: BacktestStrategyOverrides | None = None,
) -> BacktestStrategy:
    """팩터 이름으로 기본 롱숏/롱온리 전략을 구성."""
    _ = get_factor(factor_name)
    options = overrides or BacktestStrategyOverrides()
    return BacktestStrategy(
        factor_name=factor_name,
        position_mode=options.position_mode,
        long_quintile=options.long_quintile,
        short_quintile=options.short_quintile,
        rebalance_freq=options.rebalance_freq,
        min_observations=options.min_observations,
        transaction_cost_bps=options.transaction_cost_bps,
        initial_capital=options.initial_capital,
    )


def resolve_quintiles(strategy: BacktestStrategy, spec: FactorSpec) -> tuple[int, int | None]:
    """전략·팩터 메타데이터로 롱·숏 분위수를 확정."""
    long_q = strategy.resolved_long_quintile(higher_is_better=spec.higher_is_better)
    if strategy.position_mode == "long_only":
        return long_q, None
    short_q = strategy.resolved_short_quintile(higher_is_better=spec.higher_is_better)
    return long_q, short_q
