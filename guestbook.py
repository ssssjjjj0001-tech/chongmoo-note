import os

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

st.set_page_config(page_title="한 줄 방명록")

# .env 의 SUPABASE_URL, SUPABASE_KEY 로 Supabase 에 연결
load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# guestbook 표 : id, created_at, message
TABLE = "guestbook"
MAX_LENGTH = 100

st.title("한 줄 방명록")

with st.form("write", clear_on_submit=True):
    message = st.text_input("한 줄 남기기", max_chars=MAX_LENGTH)
    submitted = st.form_submit_button("남기기")

if submitted:
    message = message.strip()
    if not message:
        st.warning("남길 글을 한 줄 적어주세요")
    else:
        supabase.table(TABLE).insert({"message": message}).execute()
        st.success("방명록에 남겼어요")

# 최신 글이 위로 오게 불러오기
rows = (
    supabase.table(TABLE)
    .select("message, created_at")
    .order("created_at", desc=True)
    .execute()
    .data
)

st.subheader(f"남긴 글 {len(rows)}개")
if not rows:
    st.write("아직 남긴 글이 없어요")
for row in rows:
    st.text(row["message"])
    st.caption(row["created_at"][:16].replace("T", " "))
