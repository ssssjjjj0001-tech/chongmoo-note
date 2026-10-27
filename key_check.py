import os

import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="Claude 키 확인")

# .env 의 ANTHROPIC_API_KEY 를 읽음 (키 값 자체는 화면에 보여주지 않음)
load_dotenv()
api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

st.title("Claude 키 확인")

if api_key:
    st.success(".env 의 ANTHROPIC_API_KEY 가 채워져 있어요.")
else:
    st.error(".env 의 ANTHROPIC_API_KEY 가 비어 있어요.")
