"""팩터 기본 타입 정의."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

# 입력: Date, Ticker, Market, Open, High, Low, Close, Volume 컬럼
# 출력: Date, Ticker, Market, factor_value 컬럼
FactorComputeFn = Callable[[pd.DataFrame], pd.DataFrame]


@dataclass(frozen=True)
class FactorSpec:
    """팩터 메타데이터."""

    name: str
    description: str
    higher_is_better: bool
    min_history_days: int
    compute: FactorComputeFn
