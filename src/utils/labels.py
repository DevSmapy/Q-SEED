"""공유 라벨 헬퍼."""

from __future__ import annotations


def markets_label(markets: list[str] | None) -> str | None:
    """시장 목록을 정렬된 콤마 구분 라벨로 변환."""
    if not markets:
        return None
    return ",".join(sorted(markets))
