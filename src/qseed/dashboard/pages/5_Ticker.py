"""Ticker drill-down: metadata and Close/Volume series."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from qseed.dashboard.db import get_data_paths, query_df, table_df

st.set_page_config(page_title="Ticker | Q-SEED Stocks", layout="wide")

st.title("Ticker")
st.caption("Drill into a single Yahoo-style ticker from the stocks domain.")

paths = get_data_paths()
st.sidebar.caption(f"DB: `{paths.db_path}`")

try:
    history = table_df("rpt_stocks__history_length")
except Exception as exc:  # noqa: BLE001
    st.error(f"Failed to load ticker index.\n\n{exc}")
    st.stop()

tickers = sorted(history["Ticker"].astype(str).unique().tolist())
default_idx = tickers.index("005930.KS") if "005930.KS" in tickers else 0
ticker = st.selectbox("Ticker", tickers, index=default_idx)

meta = history[history["Ticker"] == ticker].iloc[0]
m1, m2, m3, m4 = st.columns(4)
m1.metric("Market", str(meta["Market"]))
m2.metric("Country", str(meta["country"]))
m3.metric("Rows", f"{int(meta['row_count']):,}")
m4.metric(
    "Period",
    f"{str(meta['start_date'])[:10]} → {str(meta['end_date'])[:10]}",
)

series = query_df(
    """
    select Date, Open, High, Low, Close, Volume, Dividends, Split
    from stg_stocks__raw_stocks
    where Ticker = ?
    order by Date
    """,
    params=(ticker,),
)

if series.empty:
    st.warning("No rows for this ticker.")
    st.stop()

fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    row_heights=[0.7, 0.3],
    vertical_spacing=0.06,
)
fig.add_trace(
    go.Scatter(x=series["Date"], y=series["Close"], name="Close", line=dict(width=1.5)),
    row=1,
    col=1,
)
fig.add_trace(
    go.Bar(x=series["Date"], y=series["Volume"], name="Volume", marker_color="#888"),
    row=2,
    col=1,
)
fig.update_layout(
    height=560,
    margin=dict(l=0, r=0, t=20, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
fig.update_yaxes(title_text="Close", row=1, col=1)
fig.update_yaxes(title_text="Volume", row=2, col=1)
st.plotly_chart(fig, width="stretch")

with st.expander("Recent rows"):
    tail = series.tail(30).copy()
    tail["Date"] = tail["Date"].astype(str).str[:10]
    st.dataframe(tail, width="stretch", hide_index=True)
