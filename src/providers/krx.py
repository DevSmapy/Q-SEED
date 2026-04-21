"""KRX 주식 목록 제공 모듈."""

from pathlib import Path
from typing import cast

import FinanceDataReader
import pandas as pd


class KRXProvider:
    """KRX(한국거래소) 주식 목록 제공자.

    FinanceDataReader를 사용하여 KRX 상장 종목 목록을 조회합니다.

    Attributes:
        suffix: yfinance 호환을 위한 티커 접미사 (기본: ".KS")

    Examples:
        >>> provider = KRXProvider()
        >>> tickers = provider.get_tickers()
        >>> len(tickers) > 0
        True
    """

    def __init__(self, suffix: str = ".KS") -> None:
        """KRXProvider 초기화.

        Args:
            suffix: yfinance 호환을 위한 티커 접미사
        """
        self.suffix = suffix

    def _fetch_listing(self) -> pd.DataFrame:
        """KRX 상장 목록 조회 (내부용).

        Returns:
            KRX 상장 종목 DataFrame
        """
        return cast(pd.DataFrame, FinanceDataReader.StockListing("KRX"))

    def get_tickers(self, max_count: int | None = None) -> list[str]:
        """KRX 상장 종목 티커 목록 조회.

        Args:
            max_count: 최대 종목 수 (None이면 전체)

        Returns:
            yfinance 호환 티커 목록 (예: ["005930.KS", "000660.KS", ...])
        """
        krx_df: pd.DataFrame = FinanceDataReader.StockListing("KRX")
        tickers: pd.Series[str] = krx_df["Code"].apply(lambda x: str(x) + self.suffix)

        ticker_list: list[str] = tickers.tolist()

        if max_count is not None and len(ticker_list) > max_count:
            return ticker_list[:max_count]

        return ticker_list

    def get_ticker_count(self) -> int:
        """KRX 상장 종목 수 조회.

        Returns:
            전체 종목 수
        """
        krx_df = self._fetch_listing()
        return len(krx_df)

    def save_tickers_to_csv(
        self,
        filepath: Path | str,
        max_count: int | None = None,
    ) -> list[str]:
        """티커 목록을 CSV 파일로 저장.

        Args:
            filepath: 저장할 파일 경로
            max_count: 최대 종목 수 (None이면 전체)

        Returns:
            저장된 티커 목록
        """
        tickers = self.get_tickers(max_count=max_count)

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 헤더 없이 한 줄에 하나씩 저장
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(tickers))

        return tickers

    def get_listing_dataframe(self) -> pd.DataFrame:
        """KRX 상장 종목 전체 정보 조회.

        Returns:
            종목 정보 DataFrame (Code, Name, Market 등)
        """
        return self._fetch_listing()
