"""포트폴리오 가중치 방법 정의."""

from __future__ import annotations

from typing import Literal

WeightMethod = Literal["equal_weight", "min_volatility", "max_sharpe", "hrp"]

WEIGHT_METHODS: tuple[WeightMethod, ...] = (
    "equal_weight",
    "min_volatility",
    "max_sharpe",
    "hrp",
)

DEFAULT_WEIGHT_METHOD: WeightMethod = "min_volatility"
DEFAULT_LOOKBACK = 252
MIN_TICKERS_FOR_OPTIMIZE = 2
MIN_OBSERVATIONS_FOR_OPTIMIZE = 60
# EF/HRP는 대규모 유니버스에서 과도하게 느려지므로 슬리브당 상한
DEFAULT_MAX_ASSETS = 50
