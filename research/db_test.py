"""DuckDB 저장/조회 기능 테스트 스크립트."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd

from src.repositories.duckdb import DuckDBRepository
from src.repositories.preview import DuckDBPreviewRepository

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HTML_OUTPUT_PATH = PROJECT_ROOT / "research" / "db_test_report.html"


@dataclass
class ReportData:
    """HTML 리포트 생성을 위한 데이터 컨테이너."""

    summary: dict[str, int | str | None]
    recent_df: pd.DataFrame
    tickers: list[str]
    first_ticker_df: pd.DataFrame
    date_range_df: pd.DataFrame
    duplicates_df: pd.DataFrame
    per_ticker_counts_df: pd.DataFrame
    missing_date_stats_df: pd.DataFrame


def parse_args() -> argparse.Namespace:
    """명령줄 인자 파싱."""
    parser = argparse.ArgumentParser(description="DuckDB 데이터 검증 및 리포트 생성 도구")
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "data" / "stocks.db"),
        help="DuckDB 데이터베이스 파일 경로 (기본값: data/stocks.db)",
    )
    return parser.parse_args()


def df_to_html(df: pd.DataFrame, title: str, empty_message: str = "데이터가 없습니다.") -> str:
    """DataFrame을 HTML 섹션으로 변환."""
    if df.empty:
        return f"""
        <section class="card">
          <h2>{escape(title)}</h2>
          <p class="muted">{escape(empty_message)}</p>
        </section>
        """

    table_html = df.to_html(index=False, escape=True, border=0, classes="dataframe")
    return f"""
    <section class="card">
      <h2>{escape(title)}</h2>
      {table_html}
    </section>
    """


def dict_to_html(data: Mapping[str, Any], title: str) -> str:
    """딕셔너리를 HTML 요약 카드로 변환."""
    rows = []
    for key, value in data.items():
        rows.append(f"<tr><th>{escape(str(key))}</th><td>{escape(str(value))}</td></tr>")

    return f"""
    <section class="card">
      <h2>{escape(title)}</h2>
      <table class="summary">
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </section>
    """


def build_html_report(data: ReportData) -> str:
    """HTML 리포트 생성."""
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ticker_preview_df = pd.DataFrame({"Ticker": data.tickers[:20]})

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='ko'>",
        "<head>",
        "<meta charset='utf-8' />",
        "<meta name='viewport' content='width=device-width, initial-scale=1' />",
        "<title>DuckDB DB Test Report</title>",
        "<style>",
        """
        :root {
            --bg: #f6f7fb;
            --card: #ffffff;
            --text: #1f2937;
            --muted: #6b7280;
            --border: #e5e7eb;
            --accent: #2563eb;
        }
        body {
            margin: 0;
            padding: 24px;
            font-family: -apple-system, BlinkMacSystemFont, \
            "Segoe UI", Roboto, "Noto Sans KR", sans-serif;
            background: var(--bg);
            color: var(--text);
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            margin-bottom: 24px;
            padding: 20px 24px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
        }
        .header h1 {
            margin: 0 0 8px 0;
            font-size: 28px;
        }
        .header p {
            margin: 4px 0;
            color: var(--muted);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
            gap: 16px;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 18px 20px;
            margin-bottom: 16px;
            overflow-x: auto;
        }
        .card h2 {
            margin: 0 0 12px 0;
            font-size: 18px;
            color: var(--accent);
        }
        .muted {
            color: var(--muted);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            white-space: nowrap;
        }
        th, td {
            border: 1px solid var(--border);
            padding: 8px 10px;
            text-align: left;
            vertical-align: top;
        }
        th {
            background: #f9fafb;
            font-weight: 600;
        }
        .summary th {
            width: 180px;
        }
        .dataframe {
            display: block;
            width: 100%;
        }
        """,
        "</style>",
        "</head>",
        "<body>",
        "<div class='container'>",
        f"""
        <div class="header">
          <h1>DuckDB DB Test Report</h1>
          <p>Generated at: {escape(generated_at)}</p>
          <p class="muted">이 리포트는 db_test.py 실행 결과를 HTML로 저장한 것입니다.</p>
        </div>
        """,
        "<h2>데이터 개요 및 통계</h2>",
        "<div class='grid'>",
        dict_to_html(data.summary, "기본 요약"),
        df_to_html(
            pd.DataFrame({"Value": [data.summary.get("min_date"), data.summary.get("max_date")]}),
            "날짜 범위 보조 확인",
        ),
        df_to_html(ticker_preview_df, "티커 목록 미리보기", empty_message="티커가 없습니다."),
        df_to_html(
            data.per_ticker_counts_df,
            "티커별 행 수 (Top 20)",
            empty_message="집계 결과가 없습니다.",
        ),
        df_to_html(
            data.missing_date_stats_df,
            "날짜 결측/이상치 점검",
            empty_message="점검 결과가 없습니다.",
        ),
        "</div>",
        "<h2>데이터 상세 미리보기</h2>",
        df_to_html(
            data.recent_df, "최근 전체 데이터 (최신순)", empty_message="최근 데이터가 없습니다."
        ),
        df_to_html(
            data.first_ticker_df,
            f"첫 번째 티커({data.tickers[0] if data.tickers else ''}) 상세 미리보기",
            empty_message="첫 번째 티커 데이터가 없습니다.",
        ),
        df_to_html(
            data.date_range_df,
            "날짜 범위 데이터 미리보기",
            empty_message="해당 범위 데이터가 없습니다.",
        ),
        df_to_html(
            data.duplicates_df,
            "중복 데이터 점검 (Ticker + Date)",
            empty_message="중복 데이터가 없습니다.",
        ),
        """
        <section class="card">
          <h2>추가 확인 포인트</h2>
          <ul>
            <li>raw_stocks 테이블이 정상적으로 읽히는지</li>
            <li>티커별 데이터가 충분히 들어오는지</li>
            <li>Date 기준 정렬이 기대대로 동작하는지</li>
            <li>중복 데이터가 있는지</li>
            <li>날짜 범위와 개별 티커 범위가 일관적인지</li>
          </ul>
        </section>
        """,
        "</div>",
        "</body>",
        "</html>",
    ]
    return "\n".join(html_parts)


def main() -> None:
    """DB 저장/조회 기능을 간단히 확인."""
    args = parse_args()
    db_path = Path(args.db)
    print(f"Checking database at: {db_path}")

    db_repo = DuckDBRepository(db_path=db_path)
    preview_repo = DuckDBPreviewRepository(db_path=db_path)

    try:
        db_repo.initialize()

        summary = preview_repo.get_basic_summary()
        print("=== Basic Summary ===")
        print(summary)

        print("\n=== Recent Preview ===")
        recent_df = preview_repo.preview_recent(limit=5)
        print(recent_df)

        tickers = preview_repo.get_tickers()
        print("\n=== Tickers ===")
        print(tickers[:10])

        first_ticker_df = pd.DataFrame()
        if tickers:
            print("\n=== First Ticker Preview ===")
            first_ticker_df = preview_repo.preview_by_ticker(tickers[0], limit=5)
            print(first_ticker_df)

        print("\n=== Date Range ===")
        date_range = preview_repo.get_date_range()
        print(date_range)

        print("\n=== Duplicates ===")
        duplicates_df = preview_repo.find_duplicates()
        print(duplicates_df)

        min_date, max_date = date_range
        date_range_df = pd.DataFrame()
        if min_date and max_date:
            date_range_df = preview_repo.preview_by_date_range(min_date, max_date, limit=20)

        per_ticker_counts_df = pd.DataFrame()
        try:
            per_ticker_counts_df = preview_repo.conn.execute(
                """
                SELECT
                    Ticker,
                    COUNT(*) AS row_count,
                    MIN(Date) AS min_date,
                    MAX(Date) AS max_date
                FROM raw_stocks
                GROUP BY Ticker
                ORDER BY row_count DESC, Ticker
                LIMIT 20
                """
            ).df()
        except Exception as exc:  # noqa: BLE001
            per_ticker_counts_df = pd.DataFrame([{"error": f"티커별 집계 실패: {exc}"}])

        missing_date_stats_df = pd.DataFrame()
        try:
            missing_date_stats_df = preview_repo.conn.execute(
                """
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(CASE WHEN Date IS NULL THEN 1 END) AS null_date_rows,
                    COUNT(CASE WHEN Ticker IS NULL OR Ticker = '' THEN 1 END) AS null_ticker_rows
                FROM raw_stocks
                """
            ).df()
        except Exception as exc:  # noqa: BLE001
            missing_date_stats_df = pd.DataFrame([{"error": f"이상치 점검 실패: {exc}"}])

        report_html = build_html_report(
            ReportData(
                summary=summary,
                recent_df=recent_df,
                tickers=tickers,
                first_ticker_df=first_ticker_df,
                date_range_df=date_range_df,
                duplicates_df=duplicates_df,
                per_ticker_counts_df=per_ticker_counts_df,
                missing_date_stats_df=missing_date_stats_df,
            )
        )

        HTML_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        HTML_OUTPUT_PATH.write_text(report_html, encoding="utf-8")
        print(f"\nHTML report saved to: {HTML_OUTPUT_PATH}")
    finally:
        db_repo.close()
        preview_repo.close()


if __name__ == "__main__":
    main()
