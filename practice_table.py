from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="연습 문의 목록")

CSV_PATH = Path(__file__).parent / "data" / "56_practice-inquiries.csv"

st.title("연습 문의 목록")

inquiries = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
inquiries = inquiries.rename(
    columns={"date": "날짜", "type": "유형", "message": "문의 내용", "status": "상태"}
)

type_options = ["전체"] + sorted(inquiries["유형"].dropna().unique().tolist())
selected_type = st.selectbox("유형으로 거르기", type_options, index=0)

status_options = ["전체"] + sorted(inquiries["상태"].dropna().unique().tolist())
selected_status = st.selectbox("상태로 거르기", status_options, index=0)

if selected_type != "전체":
    inquiries = inquiries[inquiries["유형"] == selected_type]

if selected_status != "전체":
    inquiries = inquiries[inquiries["상태"] == selected_status]

st.caption(f"보이는 줄 {len(inquiries)}건")
st.dataframe(inquiries, hide_index=True, width="stretch")
