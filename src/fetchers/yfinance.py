"""yfinance 기반 주식 데이터 수집 모듈."""

from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf


@dataclass
class FetchResult:
    """주식 데이터 수집 결과.

    Attributes:
        dataframe: 수집된 주가 데이터 DataFrame
        success_tickers: 성공한 티커 목록
        requested_tickers: 요청한 티커 목록
    """

    dataframe: pd.DataFrame
    success_tickers: list[str] = field(default_factory=list)
    requested_tickers: list[str] = field(default_factory=list)

    @property
    def failed_tickers(self) -> list[str]:
        """실패한 티커 목록."""
        return list(set(self.requested_tickers) - set(self.success_tickers))

    @property
    def success_count(self) -> int:
        """성공 개수."""
        return len(self.success_tickers)

    @property
    def failed_count(self) -> int:
        """실패 개수."""
        return len(self.failed_tickers)


class YFinanceFetcher:
    """yfinance를 사용한 주식 데이터 수집기.

    yfinance API를 통해 여러 종목의 주가 데이터를 병렬로 수집합니다.

    Attributes:
        period: 데이터 수집 기간 (기본: "max")
        auto_adjust: 수정 주가 사용 여부 (기본: True)
        actions: 배당금/주식분할 포함 여부 (기본: True)
        threads: 멀티스레드 사용 여부 (기본: True)

    Examples:
        >>> fetcher = YFinanceFetcher(period="1y")
        >>> result = fetcher.fetch(["005930.KS", "000660.KS"])
        >>> result.success_count > 0
        True
    """

    # 삭제할 컬럼 목록
    DROP_COLUMNS: list[str] = ["Adj Close", "Capital Gains"]

    # 컬럼명 매핑 (원본 -> 변경)
    RENAME_COLUMNS: dict[str, str] = {"Stock Splits": "Split"}

    def __init__(
        self,
        period: str = "max",
        auto_adjust: bool = True,
        actions: bool = True,
        threads: bool = True,
    ) -> None:
        """YFinanceFetcher 초기화.

        Args:
            period: 데이터 수집 기간 ("1d", "5d", "1mo", "3mo", "6mo", "1y", \
            "2y", "5y", "10y", "ytd", "max")
            auto_adjust: 수정 주가 사용 여부
            actions: 배당금/주식분할 데이터 포함 여부
            threads: 멀티스레드 사용 여부
        """
        self.period = period
        self.auto_adjust = auto_adjust
        self.actions = actions
        self.threads = threads

    def fetch(self, tickers: list[str]) -> FetchResult:
        """여러 종목의 주가 데이터 수집.

        Args:
            tickers: 수집할 티커 목록

        Returns:
            FetchResult: 수집 결과 (DataFrame, 성공/실패 티커)
        """
        if not tickers:
            return FetchResult(
                dataframe=pd.DataFrame(),
                success_tickers=[],
                requested_tickers=[],
            )

        # yfinance로 데이터 다운로드
        raw_df: pd.DataFrame = yf.download(
            tickers,
            period=self.period,
            threads=self.threads,
            group_by="Ticker",
            auto_adjust=self.auto_adjust,
            actions=self.actions,
        )

        # 데이터가 없는 경우
        if raw_df.empty:
            return FetchResult(
                dataframe=pd.DataFrame(),
                success_tickers=[],
                requested_tickers=tickers,
            )

        # DataFrame 변환 및 정제
        df_flat = self._flatten_dataframe(raw_df)
        df_cleaned = self._clean_dataframe(df_flat)

        # 성공한 티커 추출
        success_tickers: list[str] = df_cleaned["Ticker"].unique().tolist()

        return FetchResult(
            dataframe=df_cleaned,
            success_tickers=success_tickers,
            requested_tickers=tickers,
        )

    def _flatten_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """MultiIndex DataFrame을 평탄화.

        Args:
            df: yfinance에서 반환된 MultiIndex DataFrame

        Returns:
            평탄화된 DataFrame (Ticker 컬럼 추가)
        """
        return df.stack(level=0, future_stack=True).reset_index()

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """DataFrame 정제 (불필요 컬럼 삭제, 컬럼명 변경, 기본값 추가).

        Args:
            df: 정제할 DataFrame

        Returns:
            정제된 DataFrame
        """
        df = df.copy()

        # 불필요한 컬럼 삭제
        for col in self.DROP_COLUMNS:
            if col in df.columns:
                df = df.drop(columns=[col])

        # 컬럼명 변경
        rename_map = {k: v for k, v in self.RENAME_COLUMNS.items() if k in df.columns}
        if rename_map:
            df = df.rename(columns=rename_map)

        # Dividends 컬럼 기본값
        if "Dividends" not in df.columns:
            df["Dividends"] = 0.0

        # Split 컬럼 기본값
        if "Split" not in df.columns:
            df["Split"] = 1.0

        # Close가 NaN인 행 제거 (데이터 없는 종목 식별)
        df = df.dropna(subset=["Close"])

        return df
