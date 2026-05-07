"""Q-SEED 로컬 웹 조회 서버 실행 모듈."""

from __future__ import annotations

from argparse import ArgumentParser
from http.server import ThreadingHTTPServer

from qseed.web.config import WebServerConfig, resolve_path
from qseed.web.database import DuckDBSearchRepository
from qseed.web.handlers import create_handler_class


def build_parser() -> ArgumentParser:
    """웹 서버 CLI 인자 파서 생성.

    Returns:
        ArgumentParser 인스턴스
    """
    parser = ArgumentParser(
        prog="qseed-web",
        description="Q-SEED DuckDB 검색 API와 research.html 정적 서버를 실행합니다.",
    )

    parser.add_argument(
        "--host",
        default="localhost",
        help="서버 바인딩 호스트. 기본값: localhost",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="서버 바인딩 포트. 기본값: 8000",
    )
    parser.add_argument(
        "--db",
        default="data/stocks.db",
        help="DuckDB 데이터베이스 파일 경로. 기본값: data/stocks.db",
    )
    parser.add_argument(
        "--static",
        default="research",
        help="research.html이 있는 정적 파일 디렉토리. 기본값: research",
    )
    parser.add_argument(
        "--table",
        default="raw_stocks",
        help="검색 대상 DuckDB 테이블명. 기본값: raw_stocks",
    )
    parser.add_argument(
        "--default-limit",
        type=int,
        default=50,
        help="검색 결과 기본 행 수. 기본값: 50",
    )
    parser.add_argument(
        "--max-limit",
        type=int,
        default=500,
        help="검색 결과 최대 행 수. 기본값: 500",
    )

    return parser


def parse_args() -> WebServerConfig:
    """CLI 인자를 파싱해 웹 서버 설정 생성.

    Returns:
        WebServerConfig 인스턴스
    """
    parser = build_parser()
    args = parser.parse_args()

    return WebServerConfig(
        host=args.host,
        port=args.port,
        database_path=resolve_path(args.db),
        static_dir=resolve_path(args.static),
        table_name=args.table,
        default_limit=args.default_limit,
        max_limit=args.max_limit,
    )


def validate_config(config: WebServerConfig) -> None:
    """웹 서버 설정 검증.

    Args:
        config: 검증할 웹 서버 설정

    Raises:
        FileNotFoundError: DB 파일 또는 정적 디렉토리가 없는 경우
        NotADirectoryError: static_dir이 디렉토리가 아닌 경우
        ValueError: limit 설정이 잘못된 경우
    """
    if not config.database_path.exists():
        raise FileNotFoundError(f"DuckDB 데이터베이스 파일이 없습니다: {config.database_path}")

    if not config.static_dir.exists():
        raise FileNotFoundError(f"정적 파일 디렉토리가 없습니다: {config.static_dir}")

    if not config.static_dir.is_dir():
        raise NotADirectoryError(f"정적 파일 경로가 디렉토리가 아닙니다: {config.static_dir}")

    if config.default_limit < 1:
        raise ValueError("default_limit은 1 이상이어야 합니다.")

    if config.max_limit < config.default_limit:
        raise ValueError("max_limit은 default_limit보다 크거나 같아야 합니다.")


def main() -> int:
    """웹 서버 메인 함수.

    Returns:
        종료 코드
    """
    config = parse_args()
    validate_config(config)

    repository = DuckDBSearchRepository(
        database_path=config.database_path,
        table_name=config.table_name,
    )

    handler_class = create_handler_class(
        config=config,
        repository=repository,
    )

    server = ThreadingHTTPServer((config.host, config.port), handler_class)

    print(f"Server running at http://{config.host}:{config.port}")
    print(f"Static directory: {config.static_dir}")
    print(f"DuckDB database: {config.database_path}")
    print(f"Search table: {config.table_name}")
    print("Available endpoints:")
    print(f"  http://{config.host}:{config.port}/")
    print(f"  http://{config.host}:{config.port}/api/health")
    print(f"  http://{config.host}:{config.port}/api/tables")
    print(f"  http://{config.host}:{config.port}/api/schema")
    print(f"  http://{config.host}:{config.port}/api/summary")
    print(f"  http://{config.host}:{config.port}/api/search?q=keyword&limit=50")
    print(f"  http://{config.host}:{config.port}/api/ticker?ticker=005930.KS&limit=50")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
