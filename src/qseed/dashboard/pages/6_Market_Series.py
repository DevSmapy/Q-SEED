"""Market series: coverage KPIs and time-series charts."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from qseed.dashboard.db import get_data_paths, table_df

st.set_page_config(page_title="Market Series | Q-SEED", layout="wide")

st.title("Market Series")
st.caption(
    "External market indicators in `raw_market_series` "
    "(VIX, DXY, yield spread, KR investor deposit)."
)

paths = get_data_paths()
st.sidebar.caption(f"DB: `{paths.db_path}`")

try:
    series = table_df("stg_market__series")
except Exception:
    try:
        series = table_df("raw_market_series")
    except Exception as exc:  # noqa: BLE001
        st.error(
            "Failed to load market series. "
            "Run `uv run qseed --run-market-pipeline` first "
            "(optional: `uv run dbt run --select market`).\n\n"
            f"{exc}"
        )
        st.stop()

if series.empty:
    st.warning("No rows in market series tables.")
    st.stop()

series = series.copy()
series["Date"] = series["Date"].astype("datetime64[ns]")
series = series.sort_values(["series_id", "Date"])
latest_vals = (
    series.groupby("series_id", as_index=False)
    .tail(1)[["series_id", "value", "source"]]
    .rename(columns={"value": "last_value"})
)
summary = (
    series.groupby("series_id", as_index=False)
    .agg(
        rows=("value", "count"),
        first_date=("Date", "min"),
        last_date=("Date", "max"),
    )
    .merge(latest_vals, on="series_id", how="left")
    .sort_values("series_id")
)

c1, c2, c3 = st.columns(3)
c1.metric("Series", f"{summary.shape[0]:,}")
c2.metric("Rows", f"{int(series.shape[0]):,}")
c3.metric(
    "Date span",
    f"{str(series['Date'].min())[:10]} → {str(series['Date'].max())[:10]}",
)

st.subheader("Coverage by series")
view = summary.copy()
view["first_date"] = view["first_date"].astype(str).str[:10]
view["last_date"] = view["last_date"].astype(str).str[:10]
st.dataframe(view, width="stretch", hide_index=True)

ids = summary["series_id"].tolist()
selected = st.multiselect("Plot series", options=ids, default=ids[: min(2, len(ids))])
if not selected:
    st.info("Select at least one series.")
    st.stop()

plot_df = series.loc[series["series_id"].isin(selected)].sort_values("Date")
fig = px.line(
    plot_df,
    x="Date",
    y="value",
    color="series_id",
    labels={"value": "Value", "Date": "Date", "series_id": "Series"},
)
fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=420, legend_title_text="")
st.plotly_chart(fig, width="stretch")

st.subheader("Latest values")
latest = (
    series.sort_values("Date")
    .groupby("series_id", as_index=False)
    .tail(1)[["series_id", "Date", "value", "source"]]
)
latest["Date"] = latest["Date"].astype(str).str[:10]
st.dataframe(latest.sort_values("series_id"), width="stretch", hide_index=True)
