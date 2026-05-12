"""주식 종목 목록 제공 모듈."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import FinanceDataReader
import pandas as pd


@dataclass(frozen=True)
class MarketInfo:
    """시장 정보 데이터 클래스."""

    name: str  # yfinance 등에서 사용할 시장 이름 또는 표시 이름
    symbol: str  # FinanceDataReader.StockListing()에 전달할 심볼
    suffix: str = ""  # yfinance 호환을 위한 티커 접미사


class StockProvider:
    """FinanceDataReader를 사용하여 여러 시장의 종목 목록을 조회하는 제공자."""

    # 지원하는 시장 정의
    MARKETS: dict[str, MarketInfo] = {
        "KOSPI": MarketInfo(name="KOSPI", symbol="KOSPI", suffix=".KS"),
        "KOSDAQ": MarketInfo(name="KOSDAQ", symbol="KOSDAQ", suffix=".KQ"),
        "KONEX": MarketInfo(name="KONEX", symbol="KONEX", suffix=".KS"),
        "S&P500": MarketInfo(name="S&P500", symbol="S&P500"),
        "NASDAQ": MarketInfo(name="NASDAQ", symbol="NASDAQ"),
        "NYSE": MarketInfo(name="NYSE", symbol="NYSE"),
        "AMEX": MarketInfo(name="AMEX", symbol="AMEX"),
    }

    def get_market_tickers(self, market: str, max_count: int | None = None) -> pd.DataFrame:
        """특정 시장의 티커 목록 조회.

        Args:
            market: 시장 이름 (KOSPI, NASDAQ 등)
            max_count: 최대 종목 수

        Returns:
            Ticker와 Market 칼럼을 포함한 DataFrame
        """
        if market not in self.MARKETS:
            raise ValueError(f"지원하지 않는 시장입니다: {market}")

        info = self.MARKETS[market]
        df = cast(pd.DataFrame, FinanceDataReader.StockListing(info.symbol))

        if df.empty:
            return pd.DataFrame(columns=["Ticker", "Market"])

        # 티커 포맷팅 (접미사 추가)
        if "Symbol" in df.columns:  # 미국 시장 등
            ticker_col = "Symbol"
        elif "Code" in df.columns:  # 한국 시장
            ticker_col = "Code"
        else:
            # 예상치 못한 컬럼 구조인 경우 첫 번째 컬럼 사용 시도
            ticker_col = df.columns[0]

        result_df = pd.DataFrame()
        result_df["Ticker"] = (
            df[ticker_col].astype(str).map(lambda ticker: f"{ticker}{info.suffix}")
        )
        result_df["Market"] = info.name

        if max_count is not None:
            # 입력된 max_count가 실제 종목 수보다 크면 실제 종목 수만큼만 가져옴 (head는 자동 처리)
            # "최대 종목 수에 초과하는 수가 들어왔을 경우,
            # 자동으로 최대 종목의 개수로 숫자를 변경" 의미 반영
            actual_max = min(max_count, len(result_df))
            result_df = result_df.head(actual_max)

        return result_df

    def get_all_tickers(self, max_per_market: int | None = None) -> pd.DataFrame:
        """지원하는 모든 시장의 티커 목록 조회.

        Args:
            max_per_market: 시장당 최대 종목 수

        Returns:
            모든 시장의 티커가 합쳐진 DataFrame
        """
        dfs = []
        for market in self.MARKETS:
            try:
                df = self.get_market_tickers(market, max_count=max_per_market)
                dfs.append(df)
            except Exception as e:
                print(f"Error fetching tickers for {market}: {e}")

        if not dfs:
            return pd.DataFrame(columns=["Ticker", "Market"])

        return pd.concat(dfs, ignore_index=True)

    def save_tickers_to_csv(
        self,
        filepath: Path | str,
        tickers_df: pd.DataFrame,
    ) -> None:
        """티커 목록을 CSV 파일로 저장.

        Args:
            filepath: 저장할 파일 경로
            tickers_df: Ticker와 Market 칼럼을 가진 DataFrame
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        tickers_df.to_csv(filepath, index=False, encoding="utf-8")
