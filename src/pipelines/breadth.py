"""raw_stocks 기반 시장 폭넓음(breadth) 지표 계산."""

from __future__ import annotations

import pandas as pd


def compute_market_breadth(
    prices: pd.DataFrame,
    *,
    adr_window: int = 20,
    ma_windows: tuple[int, int] = (20, 200),
) -> pd.DataFrame:
    """Market별 advances/declines, ADR, AD line, MA 상회 비율 계산.

    Args:
        prices: Date, Ticker, Market, Close 컬럼을 가진 DataFrame
        adr_window: ADR 롤링 창
        ma_windows: (단기 MA, 장기 MA) 기간
    """
    empty_cols = [
        "Date",
        "Market",
        "advances",
        "declines",
        "unchanged",
        "adr_20d",
        "ad_line",
        "pct_above_ma20",
        "pct_above_ma200",
    ]
    if prices.empty:
        return pd.DataFrame(columns=empty_cols)

    required = {"Date", "Ticker", "Market", "Close"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"breadth 입력 컬럼 누락: {sorted(missing)}")

    ma_short, ma_long = ma_windows
    frame = prices.loc[:, ["Date", "Ticker", "Market", "Close"]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"])
    frame = frame.dropna(subset=["Date", "Ticker", "Market", "Close"])
    frame = frame.sort_values(["Market", "Ticker", "Date"])

    frame["prev_close"] = frame.groupby(["Market", "Ticker"], sort=False)["Close"].shift(1)
    frame["advance"] = (frame["Close"] > frame["prev_close"]).astype("int64")
    frame["decline"] = (frame["Close"] < frame["prev_close"]).astype("int64")
    frame["unchanged_flag"] = (
        (frame["Close"] == frame["prev_close"]) & frame["prev_close"].notna()
    ).astype("int64")

    # 전일 없는 첫 관측은 advances/declines 집계에서 제외
    valid_move = frame["prev_close"].notna()

    daily = (
        frame.loc[valid_move]
        .groupby(["Market", "Date"], sort=False)
        .agg(
            advances=("advance", "sum"),
            declines=("decline", "sum"),
            unchanged=("unchanged_flag", "sum"),
        )
        .reset_index()
    )
    daily = daily.sort_values(["Market", "Date"])

    # ADR: (sum adv / sum dec) over window * 100
    daily["adv_roll"] = (
        daily.groupby("Market", sort=False)["advances"]
        .rolling(adr_window, min_periods=adr_window)
        .sum()
        .reset_index(level=0, drop=True)
    )
    daily["dec_roll"] = (
        daily.groupby("Market", sort=False)["declines"]
        .rolling(adr_window, min_periods=adr_window)
        .sum()
        .reset_index(level=0, drop=True)
    )
    daily["adr_20d"] = (daily["adv_roll"] / daily["dec_roll"].replace(0, pd.NA)) * 100.0

    daily["net"] = daily["advances"] - daily["declines"]
    daily["ad_line"] = daily.groupby("Market", sort=False)["net"].cumsum()

    # MA 상회 비율
    frame["sma_short"] = frame.groupby(["Market", "Ticker"], sort=False)["Close"].transform(
        lambda s: s.rolling(ma_short, min_periods=ma_short).mean()
    )
    frame["sma_long"] = frame.groupby(["Market", "Ticker"], sort=False)["Close"].transform(
        lambda s: s.rolling(ma_long, min_periods=ma_long).mean()
    )

    short_ok = frame["sma_short"].notna()
    long_ok = frame["sma_long"].notna()
    frame["above_short"] = (frame["Close"] >= frame["sma_short"]).astype("float64")
    frame["above_long"] = (frame["Close"] >= frame["sma_long"]).astype("float64")

    pct_short = (
        frame.loc[short_ok]
        .groupby(["Market", "Date"], sort=False)["above_short"]
        .mean()
        .mul(100.0)
        .rename("pct_above_ma20")
    )
    pct_long = (
        frame.loc[long_ok]
        .groupby(["Market", "Date"], sort=False)["above_long"]
        .mean()
        .mul(100.0)
        .rename("pct_above_ma200")
    )

    daily = daily.merge(pct_short.reset_index(), on=["Market", "Date"], how="left")
    daily = daily.merge(pct_long.reset_index(), on=["Market", "Date"], how="left")

    out = daily.loc[
        :,
        [
            "Date",
            "Market",
            "advances",
            "declines",
            "unchanged",
            "adr_20d",
            "ad_line",
            "pct_above_ma20",
            "pct_above_ma200",
        ],
    ].copy()
    out["advances"] = out["advances"].astype("int64")
    out["declines"] = out["declines"].astype("int64")
    out["unchanged"] = out["unchanged"].astype("int64")
    return out.reset_index(drop=True)
