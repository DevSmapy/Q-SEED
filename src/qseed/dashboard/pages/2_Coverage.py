"""Coverage: listing vs loaded vs failed."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from qseed.dashboard.db import (
    failure_frame,
    get_data_paths,
    load_completed_tickers,
    load_no_data_tickers,
    load_ticker_list,
    query_df,
    table_df,
)

st.set_page_config(page_title="Coverage | Q-SEED Stocks", layout="wide")

st.title("Coverage")
st.caption("Listing universe vs successfully loaded tickers vs fetch failures.")

paths = get_data_paths()
st.sidebar.caption(f"Log dir: `{paths.log_dir}`")

try:
    by_market = table_df("rpt_stocks__coverage_by_market")
except Exception as exc:  # noqa: BLE001
    st.error(f"Failed to load coverage tables.\n\n{exc}")
    st.stop()

listing = load_ticker_list()
completed = set(load_completed_tickers())
failed = load_no_data_tickers()
fail_df = failure_frame()

listing_n = len(listing) if not listing.empty else 0
loaded_n = int(by_market["ticker_count"].sum())
failed_n = len(failed)
completed_n = len(completed)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Listing file rows", f"{listing_n:,}")
k2.metric("Loaded in DB", f"{loaded_n:,}")
k3.metric("Completed log", f"{completed_n:,}")
k4.metric("No-data / failed", f"{failed_n:,}")

if not listing.empty and "Market" in listing.columns:
    list_by_mkt = listing.groupby("Market", as_index=False).agg(listed=("Ticker", "count"))
    cov = by_market[["Market", "ticker_count"]].merge(list_by_mkt, on="Market", how="outer")
    cov = cov.fillna(0)
    cov["ticker_count"] = cov["ticker_count"].astype(int)
    cov["listed"] = cov["listed"].astype(int)
    cov["gap"] = cov["listed"] - cov["ticker_count"]

    st.subheader("Listed vs loaded by market")
    melt = cov.melt(
        id_vars=["Market"],
        value_vars=["listed", "ticker_count"],
        var_name="status",
        value_name="count",
    )
    melt["status"] = melt["status"].map({"listed": "listed", "ticker_count": "loaded"})
    fig = px.bar(
        melt,
        x="Market",
        y="count",
        color="status",
        barmode="group",
        labels={"count": "Tickers"},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=380)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(cov.sort_values("Market"), use_container_width=True, hide_index=True)
else:
    st.warning(f"Listing file missing or empty: `{paths.ticker_list_path}`")
    st.subheader("Loaded by market")
    st.dataframe(by_market, use_container_width=True, hide_index=True)

left, right = st.columns(2)
with left:
    st.subheader("Failure types")
    if fail_df.empty:
        st.write("No failed tickers in log.")
    else:
        counts = (
            fail_df.groupby("failure_type", as_index=False).size().rename(columns={"size": "count"})
        )
        fig_f = px.bar(counts, x="failure_type", y="count", labels={"count": "Tickers"})
        fig_f.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
        st.plotly_chart(fig_f, use_container_width=True)

with right:
    st.subheader("Failed ticker sample")
    if fail_df.empty:
        st.write("—")
    else:
        st.dataframe(fail_df.head(200), use_container_width=True, hide_index=True)

st.subheader("Tickers assigned to multiple markets")
multi = query_df(
    """
    select Ticker,
           count(distinct Market) as market_n,
           string_agg(distinct Market, ', ') as markets
    from stg_stocks__raw_stocks
    group by Ticker
    having count(distinct Market) > 1
    order by market_n desc
    """
)
if multi.empty:
    st.success("No tickers appear under more than one Market in the loaded table.")
else:
    st.dataframe(multi, use_container_width=True, hide_index=True)
