"""Q-SEED stocks data review Streamlit app (stocks domain only)."""

import streamlit as st

from qseed.dashboard.db import get_data_paths

st.set_page_config(
    page_title="Q-SEED Stocks Review",
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

st.title("Q-SEED Stocks Review")
st.caption(
    "Equity OHLCV only — independent of FX / macro domains. "
    "Universe is active listings (survivorship bias)."
)

st.sidebar.header("Data source")
st.sidebar.code(str(paths.base_dir), language=None)
st.sidebar.write(f"DB exists: `{paths.db_path.exists()}`")
st.sidebar.write(f"Log dir exists: `{paths.log_dir.exists()}`")

st.info("Use the sidebar pages: Overview, Coverage, Freshness & Gaps, Descriptive, Ticker.")
