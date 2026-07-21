"""Sector coverage from dim_stocks__security."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from qseed.dashboard.db import get_data_paths, query_df, table_df

st.set_page_config(page_title="Sector Coverage | Q-SEED Stocks", layout="wide")

st.title("Sector coverage")
st.caption(
    "GICS-aligned sector counts from security metadata (run --update-security-metadata + dbt)."
)

paths = get_data_paths()
st.sidebar.caption(f"DB: `{paths.db_path}`")

try:
    by_sector = table_df("rpt_stocks__coverage_by_sector")
    dim = table_df("dim_stocks__security")
except Exception as exc:  # noqa: BLE001
    st.error(
        "Failed to load sector tables. Run:\n\n"
        "`uv run qseed --update-security-metadata --max-tickers 100`\n\n"
        "`dbt run --select dim_stocks__security rpt_stocks__coverage_by_sector`\n\n"
        f"{exc}"
    )
    st.stop()

total = int(dim.shape[0])
mapped = int((dim["sector_status"] == "mapped").sum()) if "sector_status" in dim.columns else 0
unclassified = int((dim["sector"] == "Unclassified").sum())
equity_pct = round(100.0 * mapped / total, 1) if total else 0.0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Securities in dim", f"{total:,}")
k2.metric("Mapped sector", f"{mapped:,}")
k3.metric("Unclassified", f"{unclassified:,}")
k4.metric("Mapped %", f"{equity_pct}%")

st.subheader("Tickers by sector")
fig = px.bar(
    by_sector.sort_values("ticker_count", ascending=True),
    x="ticker_count",
    y="sector",
    orientation="h",
    title="Ticker count by sector",
)
fig.update_layout(height=max(320, 28 * len(by_sector)), margin=dict(l=0, r=0, t=40, b=0))
st.plotly_chart(fig, width="stretch")

if "sector_status_reason" in dim.columns:
    st.subheader("Unclassified breakdown")
    reasons = (
        dim[dim["sector"] == "Unclassified"]
        .groupby("sector_status_reason", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
    )
    if reasons.empty:
        st.info("No Unclassified rows.")
    else:
        st.dataframe(reasons, width="stretch", hide_index=True)

st.subheader("Sector × market")
cross = query_df(
    """
    select Market, sector, count(*) as ticker_count
    from dim_stocks__security
    group by 1, 2
    order by 1, 3 desc
    """
)
if not cross.empty:
    heat = cross.pivot_table(
        index="sector",
        columns="Market",
        values="ticker_count",
        fill_value=0,
    )
    st.dataframe(heat, width="stretch")

with st.expander("Full dim_stocks__security sample"):
    st.dataframe(dim.head(200), width="stretch", hide_index=True)
