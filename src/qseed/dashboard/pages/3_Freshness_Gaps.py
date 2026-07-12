"""Freshness and per-ticker gap / quality review."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from qseed.dashboard.db import get_data_paths, table_df

st.set_page_config(page_title="Freshness & Gaps | Q-SEED Stocks", layout="wide")

st.title("Freshness & Gaps")
st.caption("Missing-rate uses a weekday calendar only — exchange holidays inflate gaps.")

paths = get_data_paths()
st.sidebar.caption(f"DB: `{paths.db_path}`")

try:
    freshness = table_df("rpt_stocks__freshness")
    quality = table_df("rpt_stocks__data_quality")
except Exception as exc:  # noqa: BLE001
    st.error(f"Failed to load quality tables.\n\n{exc}")
    st.stop()

st.subheader("Market lag vs global max date")
fig = px.bar(
    freshness.sort_values("lag_days", ascending=True),
    x="lag_days",
    y="Market",
    orientation="h",
    color="country",
    labels={"lag_days": "Lag (days)"},
)
fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=360)
st.plotly_chart(fig, use_container_width=True)

fresh_view = freshness.copy()
fresh_view["last_date"] = fresh_view["last_date"].astype(str).str[:10]
st.dataframe(
    fresh_view[["Market", "country", "last_date", "lag_days"]],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Highest missing-rate tickers")
markets = ["All"] + sorted(quality["Market"].dropna().unique().tolist())
selected = st.selectbox("Market filter", markets)
top_n = st.slider("Top N", min_value=20, max_value=500, value=100, step=20)

view = quality.copy()
if selected != "All":
    view = view[view["Market"] == selected]

view = view.sort_values("missing_rate_pct", ascending=False).head(top_n)
view["start_date"] = view["start_date"].astype(str).str[:10]
view["end_date"] = view["end_date"].astype(str).str[:10]

st.dataframe(
    view[
        [
            "Ticker",
            "Market",
            "country",
            "start_date",
            "end_date",
            "expected_business_days",
            "actual_days",
            "missing_days",
            "missing_rate_pct",
            "zero_volume_days",
            "high_lt_low_days",
            "close_outside_hl_days",
        ]
    ],
    use_container_width=True,
    hide_index=True,
    column_config={
        "missing_rate_pct": st.column_config.NumberColumn("Missing %", format="%.2f"),
    },
)

anom = quality[(quality["high_lt_low_days"] > 0) | (quality["close_outside_hl_days"] > 0)]
st.subheader("OHLC anomalies")
if anom.empty:
    st.success("No High<Low or Close-outside-HL rows flagged.")
else:
    st.dataframe(
        anom.sort_values(["high_lt_low_days", "close_outside_hl_days"], ascending=False).head(100),
        use_container_width=True,
        hide_index=True,
    )
