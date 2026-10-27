import os
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from storage3.exceptions import StorageApiError
from supabase import create_client

st.set_page_config(page_title="문서 보관함", layout="wide")

# .env 의 SUPABASE_URL, SUPABASE_KEY 로 Supabase 에 연결
load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# docs 버킷 : 비공개(private) 버킷이라 주소만으로는 못 열고, 잠깐만 열리는 내려받기 링크로만 받을 수 있음
# 버킷과 허용 규칙은 data/80_docs_storage.sql 을 Supabase SQL Editor 에서 실행해 만듦
# 허용 규칙은 보기(select)·올리기(insert) 두 가지뿐이라, 화면에서 문서를 덮어쓰거나 지울 수는 없음
BUCKET = "docs"
bucket = supabase.storage.from_(BUCKET)

# 내려받기 링크가 열려 있는 시간(초) : 화면을 새로 열 때마다 새 링크를 만듦
LINK_SECONDS = 5 * 60

# 올릴 수 있는 문서 종류 : 확장자 → content-type
TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "hwp": "application/x-hwp",
    "hwpx": "application/hwp+zip",
    "txt": "text/plain",
    "csv": "text/csv",
    "md": "text/markdown",
}

st.title("문서 보관함")


def load_docs():
    # 최근에 올린 문서가 먼저 오도록 불러오기 (빈 폴더 표시용 파일은 뺌)
    try:
        files = bucket.list(options={"limit": 1000, "sortBy": {"column": "created_at", "order": "desc"}})
    except StorageApiError as e:
        st.error(f"docs 버킷을 불러오지 못했어요 : {e.message}. data/80_docs_storage.sql 을 Supabase SQL Editor 에 붙여넣고 Run 한 뒤 새로고침해 주세요")
        st.stop()
    return [f for f in files if f.get("id") and not f["name"].startswith(".")]


def upload_doc(file):
    # 한글 파일 이름은 Storage 에 그대로 못 넣으므로 올린 시각 + 짧은 번호로 새 이름을 붙이고,
    # 원래 이름은 metadata 에 넣어 두었다가 목록과 내려받기에 씀
    # 덮어쓰기(upsert)는 고치기(update) 권한이 있어야 하므로, 이름이 겹치지 않게 해서 늘 새로 올림
    ext = Path(file.name).suffix.lower().lstrip(".")
    name = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.{ext}"
    try:
        bucket.upload(name, file.getvalue(), {"content-type": TYPES[ext], "metadata": {"original_name": file.name}})
    except StorageApiError as e:
        # 올리기 허용 규칙이 없으면 row-level security 오류가 남
        st.error(f"{file.name} 을(를) 올리지 못했어요. Supabase 에서 \"docs 올리기\" 허용 규칙을 확인해 주세요 : {e.message}")
        return False
    return True


@st.cache_data(show_spinner=False)
def original_name(name):
    # 올릴 때 넣어 둔 원래 이름 (문서는 고칠 수 없으니 한 번 읽으면 계속 같음)
    try:
        meta = bucket.info(name).get("metadata") or {}
    except StorageApiError:
        meta = {}
    return meta.get("original_name") or name


def download_link(name, filename):
    # 잠깐만 열리는 내려받기 링크 : 받을 때 파일 이름은 원래 이름으로
    try:
        res = bucket.create_signed_url(name, LINK_SECONDS, {"download": filename})
    except StorageApiError:
        return None
    return res.get("signedURL")


def doc_size(f):
    # 목록에 보일 크기 : KB 또는 MB
    size = (f.get("metadata") or {}).get("size") or 0
    return f"{size / 1024 / 1024:.1f} MB" if size >= 1024 * 1024 else f"{max(size / 1024, 0.1):.1f} KB"


def doc_created(f):
    # 목록에 보일 올린 시각
    created = f.get("created_at") or ""
    return created[:16].replace("T", " ")


# 앞 화면에서 올리기가 끝났으면 알림
if "done" in st.session_state:
    st.success(st.session_state.pop("done"))

# 넣는 자리 : 문서 올리기
with st.form("upload", clear_on_submit=True):
    files = st.file_uploader("올릴 문서", type=list(TYPES), accept_multiple_files=True)
    uploaded = st.form_submit_button("올리기", type="primary", width="stretch")
if uploaded:
    if not files:
        st.error("올릴 문서를 골라주세요")
    else:
        count = sum(upload_doc(f) for f in files)
        if count:
            st.session_state.done = f"문서 {count}개를 올렸어요"
            st.rerun()

# 결과 자리 : 올라와 있는 문서마다 내려받기 링크
docs = load_docs()
st.subheader(f"올라와 있는 문서 {len(docs)}개")
if not docs:
    # 보기 허용 규칙이 없으면 오류 없이 빈 목록만 옴
    st.info("아직 올라온 문서가 없어요. 위에서 문서를 올려 보세요. 올렸는데도 안 보이면 Supabase 에서 \"docs 목록 보기\" 허용 규칙을 확인해 주세요")
else:
    st.caption(f"내려받기 링크는 {LINK_SECONDS // 60}분 동안만 열려요. 시간이 지났으면 새로고침해서 새 링크를 받아 주세요")
    for f in docs:
        filename = original_name(f["name"])
        name_col, info_col, link_col = st.columns([5, 3, 2], vertical_alignment="center")
        name_col.write(filename)
        info_col.caption(f"{doc_created(f)} · {doc_size(f)}")
        url = download_link(f["name"], filename)
        if url:
            link_col.link_button("내려받기", url, width="stretch")
        else:
            link_col.caption("링크를 못 만들었어요")
