"""Q-SEED 웹 서버 HTTP 핸들러 모듈."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse

from qseed.web.config import WebServerConfig
from qseed.web.database import DuckDBSearchRepository


class ResearchRequestHandler(SimpleHTTPRequestHandler):
    """정적 HTML과 DuckDB 검색 API를 함께 제공하는 HTTP 핸들러."""

    config: WebServerConfig
    repository: DuckDBSearchRepository

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """ResearchRequestHandler 초기화."""
        super().__init__(*args, directory=str(self.config.static_dir), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        """GET 요청 처리."""
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._handle_health()
            return

        if parsed.path == "/api/tables":
            self._handle_tables()
            return

        if parsed.path == "/api/schema":
            self._handle_schema()
            return

        if parsed.path == "/api/summary":
            self._handle_summary()
            return

        if parsed.path == "/api/search":
            self._handle_search(parsed.query)
            return

        if parsed.path == "/api/ticker":
            self._handle_ticker(parsed.query)
            return

        self._handle_static_file()

    def _handle_static_file(self) -> None:
        """정적 파일 요청 처리."""
        if self.path == "/":
            self.path = "/research.html"

        super().do_GET()

    def _handle_health(self) -> None:
        """서버 상태 확인 API."""
        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "database": str(self.config.database_path),
                "table": self.config.table_name,
            },
        )

    def _handle_tables(self) -> None:
        """DuckDB 테이블 목록 API."""
        try:
            tables = self.repository.list_tables()
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "tables": tables,
                },
            )
        except Exception as error:
            self._send_error_json(error)

    def _handle_schema(self) -> None:
        """검색 대상 테이블 스키마 API."""
        try:
            schema = self.repository.describe_table()
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "table": self.config.table_name,
                    "schema": schema,
                },
            )
        except Exception as error:
            self._send_error_json(error)

    def _handle_summary(self) -> None:
        """검색 대상 테이블 요약 API."""
        try:
            summary = self.repository.get_summary()
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "summary": summary,
                },
            )
        except Exception as error:
            self._send_error_json(error)

    def _handle_search(self, query_string: str) -> None:
        """키워드 검색 API."""
        params = parse_qs(query_string)

        keyword = params.get("q", [""])[0]
        limit = self._parse_limit(params.get("limit", [str(self.config.default_limit)])[0])

        try:
            rows = self.repository.search(keyword=keyword, limit=limit)
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "query": keyword,
                    "limit": limit,
                    "count": len(rows),
                    "rows": rows,
                },
            )
        except Exception as error:
            self._send_error_json(error)

    def _handle_ticker(self, query_string: str) -> None:
        """Ticker 기준 조회 API."""
        params = parse_qs(query_string)

        ticker = params.get("ticker", [""])[0].strip()
        limit = self._parse_limit(params.get("limit", [str(self.config.default_limit)])[0])

        if not ticker:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "ok": False,
                    "error": "ticker 파라미터가 필요합니다.",
                },
            )
            return

        try:
            rows = self.repository.search_by_ticker(ticker=ticker, limit=limit)
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "ticker": ticker,
                    "limit": limit,
                    "count": len(rows),
                    "rows": rows,
                },
            )
        except Exception as error:
            self._send_error_json(error)

    def _parse_limit(self, value: str) -> int:
        """limit 쿼리 파라미터 파싱.

        Args:
            value: 문자열 limit 값

        Returns:
            검증된 limit 값
        """
        default_limit = int(self.config.default_limit)
        max_limit = int(self.config.max_limit)

        try:
            limit = int(value)
        except ValueError:
            return default_limit

        if limit < 1:
            return default_limit

        return min(limit, max_limit)

    def _send_error_json(self, error: Exception) -> None:
        """예외를 JSON 에러 응답으로 반환."""
        self._send_json(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            {
                "ok": False,
                "error": str(error),
            },
        )

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        """JSON 응답 전송."""
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")

        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_handler_class(
    config: WebServerConfig,
    repository: DuckDBSearchRepository,
) -> type[ResearchRequestHandler]:
    """설정과 저장소가 주입된 HTTP 핸들러 클래스 생성.

    Args:
        config: 웹 서버 설정
        repository: DuckDB 검색 저장소

    Returns:
        설정이 주입된 핸들러 클래스
    """

    class ConfiguredResearchRequestHandler(ResearchRequestHandler):
        pass

    ConfiguredResearchRequestHandler.config = config
    ConfiguredResearchRequestHandler.repository = repository

    return ConfiguredResearchRequestHandler
