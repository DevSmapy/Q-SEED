"""Q-SEED data review Streamlit app (stocks + market pages)."""

import streamlit as st

from qseed.dashboard.db import get_data_paths

st.set_page_config(
    page_title="Q-SEED Data Review",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; max-width: 1200px; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

paths = get_data_paths()

st.title("Q-SEED Data Review")
st.caption(
    "Stocks pages review equity OHLCV (active listings, survivorship bias). "
    "Market pages review `raw_market_series` and `raw_market_breadth`."
)

st.sidebar.header("Data source")
st.sidebar.code(str(paths.base_dir), language=None)
st.sidebar.write(f"DB exists: `{paths.db_path.exists()}`")
st.sidebar.write(f"Log dir exists: `{paths.log_dir.exists()}`")

st.info(
    "Sidebar: Overview, Coverage, Freshness & Gaps, Descriptive, Ticker, "
    "Market Series, Market Breadth."
)
