import os

import streamlit as st
from dotenv import load_dotenv
from google import genai

st.set_page_config(page_title="챗봇")

# .env 의 GEMINI_API_KEY 가 채워져 있는지만 확인 (키 값은 화면에 보여주지 않음)
load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY", "").strip()

# 공식 문서(ai.google.dev/gemini-api/docs/quickstart) 기준 모델 이름
MODEL = "gemini-3.8-flash"

st.title("챗봇")

if api_key:
    st.write("GEMINI_API_KEY : 채워져 있어요")
else:
    st.write("GEMINI_API_KEY : 비어 있어요. .env 에 값을 넣어주세요")

question = st.text_input("물어볼 말")

if st.button("보내기"):
    question = question.strip()
    if not api_key:
        st.error("GEMINI_API_KEY 가 비어 있어서 보낼 수 없어요")
    elif not question:
        st.warning("물어볼 말을 적어주세요")
    else:
        try:
            client = genai.Client(api_key=api_key)
            with st.spinner("Gemini 가 답을 쓰는 중이에요"):
                interaction = client.interactions.create(model=MODEL, input=question)
            st.write(interaction.output_text)
        except Exception as e:
            st.error(f"Gemini 에서 답을 받지 못했어요 : {e}")
