import os
from pathlib import Path

import duckdb
import plotly.express as px
import streamlit as st

db_path = Path("/Volumes/WD_BLACK/Careers/PythonProjects/Q-SEED/data/stocks.db")


# 1. 페이지 설정
st.set_page_config(page_title="데이터 품질 대시보드")

# 2. DuckDB 연결

print("Current Working Directory:", os.getcwd())
print(
    "Does file exist:",
    os.path.exists("/Volumes/WD_BLACK/Careers/PythonProjects/Q-SEED/data/stocks.db"),
)
if not db_path.exists():
    print(f"파일을 찾을 수 없음: {db_path}")
else:
    conn = duckdb.connect(str(db_path))

st.title("📊 데이터 엔지니어링 대시보드")

# 3. 데이터 가져오기 (dbt가 만들어둔 모델을 가져옵니다)
df = conn.execute("SELECT * FROM summary").df()

# 4. 화면에 테이블 표시
# st.subheader("데이터 요약 정보")
# st.dataframe(df) # 엑셀처럼 정렬/필터링 가능한 테이블
st.title("📊 데이터 대시보드")
st.dataframe(df)

fig = px.bar(df, x="Market", y="Ticker_counts", color="Market")
st.plotly_chart(fig, use_container_width=True)

df = conn.execute("SELECT * FROM data_quality").df()
st.subheader("종목별 데이터 공백 및 품질 검증")
st.dataframe(
    df,
    use_container_width=True,
    column_config={
        "데이터 누락률(%)": st.column_config.NumberColumn(format="%.2f%%"),
    },
)

"""
col1, col2, col3 = st.columns(3)
col1.metric("전체 행 개수", f"{df['total_row_count'][0]:,}")
col2.metric("총 종목 수", f"{df['total_ticker_count'][0]:,}")
col3.metric("총 시장 수", f"{df['total_market_count'][0]:,}")

# 5. 차트 그리기 (Plotly 사용 시)
import plotly.express as px
fig = px.bar(df, x='total_row_count', y='total_ticker_count')
st.plotly_chart(fig)

df = conn.execute("SELECT * FROM rpt_ticker_details").df()
st.dataframe(df)"""
