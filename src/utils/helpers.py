"""Q-SEED 유틸리티 함수 모듈."""

from collections.abc import Iterator
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


def chunked(lst: list[T], size: int) -> Iterator[list[T]]:
    """리스트를 지정된 크기의 청크로 분할.

    Args:
        lst: 분할할 리스트
        size: 청크 크기 (1 이상)

    Yields:
        지정된 크기의 리스트 청크

    Raises:
        ValueError: size가 1 미만인 경우

    Examples:
        >>> list(chunked([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    if size < 1:
        raise ValueError(f"청크 크기는 1 이상이어야 합니다: {size}")

    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def calculate_success_rate(success: int, total: int) -> float:
    """성공률 계산.

    Args:
        success: 성공 개수
        total: 전체 개수

    Returns:
        성공률 (0.0 ~ 100.0)

    Examples:
        >>> calculate_success_rate(80, 100)
        80.0
        >>> calculate_success_rate(0, 0)
        0.0
    """
    if total == 0:
        return 0.0
    return (success / total) * 100


def format_progress(success: int, failed: int, total: int) -> str:
    """진행 상황 포맷팅.

    Args:
        success: 성공 개수
        failed: 실패 개수
        total: 전체 시도 개수

    Returns:
        포맷팅된 진행 상황 문자열

    Examples:
        >>> format_progress(80, 20, 100)
        'Processed: 80 success / 20 failed / 100 total attempted'
    """
    return f"Processed: {success} success / {failed} failed / {total} total attempted"


def format_summary(
    total_attempted: int,
    success_count: int,
    failed_count: int,
) -> str:
    """최종 요약 포맷팅.

    Args:
        total_attempted: 전체 시도 개수
        success_count: 성공 개수
        failed_count: 실패 개수

    Returns:
        포맷팅된 요약 문자열

    Examples:
        >>> print(format_summary(100, 80, 20))
        <BLANKLINE>
        === Final Summary ===
        Total attempted: 100
        Success: 80
        Failed: 20
        Success rate: 80.00%
    """
    success_rate = calculate_success_rate(success_count, total_attempted)
    return (
        "\n=== Final Summary ===\n"
        f"Total attempted: {total_attempted}\n"
        f"Success: {success_count}\n"
        f"Failed: {failed_count}\n"
        f"Success rate: {success_rate:.2f}%"
    )


def save_list_to_file(items: list[str], filepath: str) -> None:
    """문자열 리스트를 파일에 저장.

    Args:
        items: 저장할 문자열 리스트
        filepath: 저장할 파일 경로

    Examples:
        >>> import tempfile
        >>> import os
        >>> with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        ...     filepath = f.name
        >>> save_list_to_file(['a', 'b', 'c'], filepath)
        >>> os.remove(filepath)
    """
    file_path = Path(filepath)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(items))
