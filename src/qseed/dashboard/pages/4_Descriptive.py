"""Descriptive stats: returns, history length, stratified by market."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from qseed.dashboard.db import get_data_paths, table_df

st.set_page_config(page_title="Descriptive | Q-SEED Stocks", layout="wide")

st.title("Descriptive")
st.caption("Always stratified by market — KRW and USD must not be pooled.")

paths = get_data_paths()
st.sidebar.caption(f"DB: `{paths.db_path}`")

try:
    stats = table_df("rpt_stocks__return_stats")
    history = table_df("rpt_stocks__history_length")
except Exception as exc:  # noqa: BLE001
    st.error(f"Failed to load descriptive tables.\n\n{exc}")
    st.stop()

markets = sorted(stats["Market"].dropna().unique().tolist())
selected = st.selectbox("Market", markets, index=0)

row = stats[stats["Market"] == selected].iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Observations", f"{int(row['observation_count']):,}")
c2.metric("Median daily return", f"{row['median_return'] * 100:.3f}%")
c3.metric("Std daily return", f"{row['std_return'] * 100:.3f}%")
c4.metric("Zero-volume %", f"{row['zero_volume_pct']:.2f}%")

st.subheader("Return summary by market")
display = stats.copy()
for col in [
    "mean_return",
    "std_return",
    "p05_return",
    "median_return",
    "p95_return",
]:
    display[col] = display[col] * 100
st.dataframe(
    display[
        [
            "Market",
            "country",
            "currency",
            "observation_count",
            "mean_return",
            "std_return",
            "p05_return",
            "median_return",
            "p95_return",
            "extreme_return_pct",
            "median_close",
            "median_volume",
            "zero_volume_pct",
        ]
    ],
    width="stretch",
    hide_index=True,
    column_config={
        "mean_return": st.column_config.NumberColumn("Mean %", format="%.4f"),
        "std_return": st.column_config.NumberColumn("Std %", format="%.4f"),
        "p05_return": st.column_config.NumberColumn("P05 %", format="%.4f"),
        "median_return": st.column_config.NumberColumn("Median %", format="%.4f"),
        "p95_return": st.column_config.NumberColumn("P95 %", format="%.4f"),
        "extreme_return_pct": st.column_config.NumberColumn("|r|>20% %", format="%.4f"),
        "zero_volume_pct": st.column_config.NumberColumn("Zero vol %", format="%.2f"),
    },
)

hist_m = history[history["Market"] == selected]
left, right = st.columns(2)
with left:
    st.subheader(f"History length — {selected}")
    bucket_order = ["<1y", "1-3y", "3-5y", "5-10y", "10y+"]
    counts = (
        hist_m.groupby("history_bucket", as_index=False).size().rename(columns={"size": "tickers"})
    )
    counts["history_bucket"] = pd.Categorical(
        counts["history_bucket"], categories=bucket_order, ordered=True
    )
    counts = counts.sort_values("history_bucket")
    fig_b = px.bar(counts, x="history_bucket", y="tickers", labels={"tickers": "Tickers"})
    fig_b.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
    st.plotly_chart(fig_b, width="stretch")

with right:
    st.subheader(f"Row-count distribution — {selected}")
    fig_h = px.histogram(
        hist_m,
        x="row_count",
        nbins=40,
        labels={"row_count": "Rows per ticker"},
    )
    fig_h.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
    st.plotly_chart(fig_h, width="stretch")

st.subheader("Extreme return share by market (|r| > 20%)")
fig_e = px.bar(
    stats.sort_values("extreme_return_pct", ascending=False),
    x="Market",
    y="extreme_return_pct",
    color="country",
    labels={"extreme_return_pct": "% of days"},
)
fig_e.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
st.plotly_chart(fig_e, width="stretch")
