"""Overview: KPI, market/country coverage bars, freshness snapshot."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from qseed.dashboard.db import get_data_paths, table_df

st.set_page_config(page_title="Overview | Q-SEED Stocks", layout="wide")

st.title("Overview")
st.caption("Active-listing universe only (survivorship bias). Stocks domain — no FX/macro.")

paths = get_data_paths()
st.sidebar.caption(f"DB: `{paths.db_path}`")

try:
    overview = table_df("rpt_stocks__overview")
    by_market = table_df("rpt_stocks__coverage_by_market")
    by_country = table_df("rpt_stocks__coverage_by_country")
    freshness = table_df("rpt_stocks__freshness")
except Exception as exc:  # noqa: BLE001
    st.error(f"Failed to load report tables. Run `dbt run --select stocks` first.\n\n{exc}")
    st.stop()

row = overview.iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Tickers", f"{int(row['total_ticker_count']):,}")
c2.metric("Rows", f"{int(row['total_row_count']):,}")
c3.metric("Markets", f"{int(row['total_market_count']):,}")
c4.metric(
    "Date range",
    f"{str(row['min_date'])[:10]} → {str(row['max_date'])[:10]}",
)

left, right = st.columns(2)
with left:
    st.subheader("Tickers by market")
    fig_m = px.bar(
        by_market.sort_values("ticker_count", ascending=True),
        x="ticker_count",
        y="Market",
        orientation="h",
        color="country",
        labels={"ticker_count": "Tickers", "Market": "Market"},
    )
    fig_m.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=360)
    st.plotly_chart(fig_m, width="stretch")

with right:
    st.subheader("Tickers by country")
    fig_c = px.bar(
        by_country.sort_values("ticker_count", ascending=True),
        x="ticker_count",
        y="country",
        orientation="h",
        color="currency",
        labels={"ticker_count": "Tickers", "country": "Country"},
    )
    fig_c.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=360)
    st.plotly_chart(fig_c, width="stretch")

st.subheader("Market freshness")
fresh_view = freshness.copy()
fresh_view["last_date"] = fresh_view["last_date"].astype(str).str[:10]
fresh_view["global_last_date"] = fresh_view["global_last_date"].astype(str).str[:10]
st.dataframe(
    fresh_view[["Market", "country", "last_date", "lag_days"]],
    width="stretch",
    hide_index=True,
)
