import os

import streamlit as st
from dotenv import load_dotenv

# 내 컴퓨터 : .env 에서 읽음 / 올린 곳(Streamlit Community Cloud) : 배포 설정의 Secrets 에서 같은 이름으로 읽음
load_dotenv()


def get_key(name):
    value = os.environ.get(name, "").strip()
    if value:
        return value
    # 내 컴퓨터에는 Secrets 파일이 없어서 st.secrets 가 FileNotFoundError 를 냄 (없으면 빈 값으로 처리)
    try:
        return str(st.secrets.get(name, "")).strip()
    except FileNotFoundError:
        return ""
