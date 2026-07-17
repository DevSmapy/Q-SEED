"""시장 지표 외부 시계열 수집."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.providers.market_series_provider import MarketSeriesSpec, get_series_specs

logger = logging.getLogger("qseed")


def _normalize_index_to_date(dataframe: pd.DataFrame) -> pd.DataFrame:
    """인덱스를 Date 컬럼으로 정규화."""
    out = dataframe.copy()
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"])
        return out
    out = out.reset_index()
    date_col = out.columns[0]
    out = out.rename(columns={date_col: "Date"})
    out["Date"] = pd.to_datetime(out["Date"])
    return out


def _pick_value_column(dataframe: pd.DataFrame, hint: str | None) -> str:
    """값 컬럼 선택. hint 부분문자열 우선, 없으면 Close/첫 수치 컬럼."""
    numeric_cols = [
        c
        for c in dataframe.columns
        if c != "Date" and pd.api.types.is_numeric_dtype(dataframe[c])
    ]
    if not numeric_cols:
        raise ValueError("수치형 값 컬럼이 없습니다")

    if hint:
        for col in numeric_cols:
            if hint in str(col):
                return str(col)

    if "Close" in numeric_cols:
        return "Close"
    return str(numeric_cols[0])


def _to_series_frame(
    dataframe: pd.DataFrame,
    *,
    series_id: str,
    source: str,
    value_column: str | None = None,
) -> pd.DataFrame:
    """임의 DataFrame → raw_market_series 스키마."""
    if dataframe.empty:
        return pd.DataFrame(columns=["Date", "series_id", "value", "source"])

    normalized = _normalize_index_to_date(dataframe)
    value_col = _pick_value_column(normalized, value_column)
    out = pd.DataFrame(
        {
            "Date": normalized["Date"],
            "series_id": series_id,
            "value": pd.to_numeric(normalized[value_col], errors="coerce"),
            "source": source,
        }
    )
    out = out.dropna(subset=["Date", "value"])
    return out.reset_index(drop=True)


def fetch_fdr_series(spec: MarketSeriesSpec) -> pd.DataFrame:
    """FinanceDataReader로 시리즈 조회."""
    import FinanceDataReader as fdr

    symbol = spec.symbol
    raw: Any
    if symbol.startswith("ECOS/"):
        raw = fdr.SnapDataReader(symbol)
    else:
        raw = fdr.DataReader(symbol)

    if not isinstance(raw, pd.DataFrame):
        raise TypeError(f"FDR 결과가 DataFrame이 아님: {type(raw)}")
    return _to_series_frame(
        raw,
        series_id=spec.series_id,
        source="fdr",
        value_column=spec.value_column,
    )


def fetch_yfinance_series(spec: MarketSeriesSpec) -> pd.DataFrame:
    """yfinance 단일 심볼 Close 조회."""
    import yfinance as yf

    raw = yf.download(
        spec.symbol,
        period="max",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise ValueError(f"yfinance 빈 결과: {spec.symbol}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [str(col[0]) for col in raw.columns]

    return _to_series_frame(
        raw, series_id=spec.series_id, source="yfinance", value_column="Close"
    )


def fetch_yfinance_spread(spec: MarketSeriesSpec) -> pd.DataFrame:
    """yfinance 두 심볼 Close 차이 (high - low)."""
    import yfinance as yf

    parts = spec.symbol.split("|")
    if len(parts) != 2:
        raise ValueError(f"yfinance_spread symbol은 'A|B' 형식이어야 함: {spec.symbol}")

    high_sym, low_sym = parts[0].strip(), parts[1].strip()
    frames: list[pd.DataFrame] = []
    for sym, label in ((high_sym, "high"), (low_sym, "low")):
        raw = yf.download(
            sym,
            period="max",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if not isinstance(raw, pd.DataFrame) or raw.empty:
            raise ValueError(f"yfinance 빈 결과: {sym}")
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [str(col[0]) for col in raw.columns]
        part = _normalize_index_to_date(raw)
        close_col = _pick_value_column(part, "Close")
        frames.append(
            pd.DataFrame(
                {
                    "Date": part["Date"],
                    label: pd.to_numeric(part[close_col], errors="coerce"),
                }
            )
        )

    merged = frames[0].merge(frames[1], on="Date", how="inner")
    merged["value"] = merged["high"] - merged["low"]
    out = pd.DataFrame(
        {
            "Date": merged["Date"],
            "series_id": spec.series_id,
            "value": merged["value"],
            "source": "yfinance",
        }
    )
    return out.dropna(subset=["Date", "value"]).reset_index(drop=True)


def fetch_series(spec: MarketSeriesSpec) -> pd.DataFrame:
    """스펙에 맞는 백엔드로 시리즈 수집."""
    if spec.backend == "fdr":
        return fetch_fdr_series(spec)
    if spec.backend == "yfinance":
        return fetch_yfinance_series(spec)
    if spec.backend == "yfinance_spread":
        return fetch_yfinance_spread(spec)
    raise ValueError(f"지원하지 않는 backend: {spec.backend}")


def fetch_all_series(
    specs: tuple[MarketSeriesSpec, ...] | None = None,
) -> pd.DataFrame:
    """등록 시리즈를 순회 수집. 실패한 시리즈는 로그 후 스킵."""
    selected = specs if specs is not None else get_series_specs()
    frames: list[pd.DataFrame] = []
    for spec in selected:
        try:
            frame = fetch_series(spec)
            if frame.empty:
                logger.warning("시장 시리즈 빈 결과, 스킵: %s", spec.series_id)
                continue
            frames.append(frame)
            logger.info(
                "시장 시리즈 수집 완료: %s (%d rows, source=%s)",
                spec.series_id,
                len(frame),
                spec.backend,
            )
        except Exception:
            logger.exception("시장 시리즈 수집 실패, 스킵: %s", spec.series_id)

    if not frames:
        return pd.DataFrame(columns=["Date", "series_id", "value", "source"])
    return pd.concat(frames, ignore_index=True)
