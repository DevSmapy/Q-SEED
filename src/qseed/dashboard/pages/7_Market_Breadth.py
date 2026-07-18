"""Market breadth: ADR, A/D line, percent above moving averages."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from qseed.dashboard.db import get_data_paths, table_df

st.set_page_config(page_title="Market Breadth | Q-SEED", layout="wide")

st.title("Market Breadth")
st.caption(
    "Advance/decline metrics derived from `raw_stocks` " "(ADR, A/D line, % above MA20 / MA200)."
)

paths = get_data_paths()
st.sidebar.caption(f"DB: `{paths.db_path}`")

try:
    breadth = table_df("stg_market__breadth")
except Exception:
    try:
        breadth = table_df("raw_market_breadth")
    except Exception as exc:  # noqa: BLE001
        st.error(
            "Failed to load market breadth. "
            "Run `uv run qseed --run-market-pipeline` "
            "(or `--breadth-only`) first.\n\n"
            f"{exc}"
        )
        st.stop()

if breadth.empty:
    st.warning("No rows in market breadth tables.")
    st.stop()

breadth = breadth.copy()
breadth["Date"] = breadth["Date"].astype("datetime64[ns]")

markets = sorted(breadth["Market"].astype(str).unique().tolist())
summary = (
    breadth.groupby("Market", as_index=False)
    .agg(
        rows=("Date", "count"),
        first_date=("Date", "min"),
        last_date=("Date", "max"),
        last_adr=("adr_20d", "last"),
        last_ad_line=("ad_line", "last"),
    )
    .sort_values("Market")
)

c1, c2, c3 = st.columns(3)
c1.metric("Markets", f"{len(markets):,}")
c2.metric("Rows", f"{int(breadth.shape[0]):,}")
c3.metric(
    "Date span",
    f"{str(breadth['Date'].min())[:10]} → {str(breadth['Date'].max())[:10]}",
)

st.subheader("Coverage by market")
cov = summary.copy()
cov["first_date"] = cov["first_date"].astype(str).str[:10]
cov["last_date"] = cov["last_date"].astype(str).str[:10]
st.dataframe(cov, width="stretch", hide_index=True)

market = st.selectbox("Market", options=markets, index=0)
metric = st.selectbox(
    "Metric",
    options=[
        "adr_20d",
        "ad_line",
        "pct_above_ma20",
        "pct_above_ma200",
        "advances",
        "declines",
    ],
    index=0,
)

mkt = breadth.loc[breadth["Market"].astype(str) == market].sort_values("Date")
fig = px.line(
    mkt,
    x="Date",
    y=metric,
    labels={"Date": "Date", metric: metric},
    title=f"{market} — {metric}",
)
fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=420, showlegend=False)
st.plotly_chart(fig, width="stretch")

left, right = st.columns(2)
with left:
    st.subheader("Advances vs declines (recent)")
    tail = mkt.tail(120)
    melt = tail.melt(
        id_vars=["Date"],
        value_vars=["advances", "declines"],
        var_name="side",
        value_name="count",
    )
    fig_ad = px.line(
        melt,
        x="Date",
        y="count",
        color="side",
        labels={"count": "Count", "side": ""},
    )
    fig_ad.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
    st.plotly_chart(fig_ad, width="stretch")

with right:
    st.subheader("% above MA")
    melt_ma = mkt.melt(
        id_vars=["Date"],
        value_vars=["pct_above_ma20", "pct_above_ma200"],
        var_name="ma",
        value_name="pct",
    )
    fig_ma = px.line(
        melt_ma,
        x="Date",
        y="pct",
        color="ma",
        labels={"pct": "% of tickers", "ma": ""},
    )
    fig_ma.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
    st.plotly_chart(fig_ma, width="stretch")

st.subheader("Latest row")
latest = mkt.tail(1).copy()
for col in ("Date",):
    latest[col] = latest[col].astype(str).str[:10]
st.dataframe(latest, width="stretch", hide_index=True)
