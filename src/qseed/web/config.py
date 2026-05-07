"""Q-SEED 웹 서버 설정 모듈."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WebServerConfig:
    """웹 서버 실행 설정.

    Attributes:
        host: 서버 바인딩 호스트
        port: 서버 바인딩 포트
        database_path: DuckDB 데이터베이스 파일 경로
        static_dir: research.html 등 정적 파일을 제공할 디렉토리
        table_name: 검색 대상 DuckDB 테이블명
        default_limit: 검색 결과 기본 행 수
        max_limit: 검색 결과 최대 행 수
    """

    host: str
    port: int
    database_path: Path
    static_dir: Path
    table_name: str
    default_limit: int = 50
    max_limit: int = 500


def resolve_path(path: str | Path) -> Path:
    """문자열 또는 Path를 절대 경로로 변환.

    Args:
        path: 변환할 경로

    Returns:
        절대 경로 Path
    """
    return Path(path).expanduser().resolve()
