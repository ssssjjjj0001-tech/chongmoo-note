import streamlit as st

from keys import get_key

st.set_page_config(page_title="Claude 키 확인")

# .env(내 컴퓨터) 또는 Secrets(올린 곳) 의 ANTHROPIC_API_KEY 를 읽음 (키 값 자체는 화면에 보여주지 않음)
api_key = get_key("ANTHROPIC_API_KEY")

st.title("Claude 키 확인")

if api_key:
    st.success(".env 또는 Secrets 의 ANTHROPIC_API_KEY 가 채워져 있어요.")
else:
    st.error(".env 또는 Secrets 의 ANTHROPIC_API_KEY 가 비어 있어요.")
