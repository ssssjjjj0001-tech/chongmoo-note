import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from storage3.exceptions import StorageApiError
from supabase import create_client

from keys import get_key

st.set_page_config(page_title="사진 보관함", layout="wide")

# .env(내 컴퓨터) 또는 Secrets(올린 곳) 의 SUPABASE_URL, SUPABASE_KEY 로 Supabase 에 연결
supabase = create_client(get_key("SUPABASE_URL"), get_key("SUPABASE_KEY"))

# photos 버킷 : 공개(public) 버킷이라 주소만 있으면 그림을 볼 수 있음
# 버킷과 허용 규칙은 data/79_photos_storage.sql 을 Supabase SQL Editor 에서 실행해 만듦
# 허용 규칙은 보기(select)·올리기(insert) 두 가지뿐이라, 화면에서 그림을 덮어쓰거나 지울 수는 없음
BUCKET = "photos"
bucket = supabase.storage.from_(BUCKET)

# 올릴 수 있는 그림 종류 : 확장자 → content-type
TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}

st.title("사진 보관함")


def load_photos():
    # 최근에 올린 그림이 먼저 오도록 불러오기 (빈 폴더 표시용 파일은 뺌)
    try:
        files = bucket.list(options={"limit": 1000, "sortBy": {"column": "created_at", "order": "desc"}})
    except StorageApiError as e:
        st.error(f"photos 버킷을 불러오지 못했어요 : {e.message}. data/79_photos_storage.sql 을 Supabase SQL Editor 에 붙여넣고 Run 한 뒤 새로고침해 주세요")
        st.stop()
    return [f for f in files if f.get("id") and not f["name"].startswith(".")]


def upload_photo(file):
    # 한글 파일 이름은 Storage 에 그대로 못 넣으므로 올린 시각 + 짧은 번호로 새 이름을 붙임
    # 덮어쓰기(upsert)는 고치기(update) 권한이 있어야 하므로, 이름이 겹치지 않게 해서 늘 새로 올림
    ext = Path(file.name).suffix.lower().lstrip(".")
    name = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.{ext}"
    try:
        bucket.upload(name, file.getvalue(), {"content-type": TYPES[ext]})
    except StorageApiError as e:
        # 올리기 허용 규칙이 없으면 row-level security 오류가 남
        st.error(f"{file.name} 을(를) 올리지 못했어요. Supabase 에서 \"photos 올리기\" 허용 규칙을 확인해 주세요 : {e.message}")
        return False
    return True


def photo_caption(f):
    # 그림 아래에 보일 한 줄 : 올린 시각
    created = f.get("created_at") or ""
    return created[:16].replace("T", " ") if created else f["name"]


# 앞 화면에서 올리기가 끝났으면 알림
if "done" in st.session_state:
    st.success(st.session_state.pop("done"))

# 넣는 자리 : 그림 올리기
with st.form("upload", clear_on_submit=True):
    files = st.file_uploader("올릴 그림", type=list(TYPES), accept_multiple_files=True)
    uploaded = st.form_submit_button("올리기", type="primary", width="stretch")
if uploaded:
    if not files:
        st.error("올릴 그림을 골라주세요")
    else:
        count = sum(upload_photo(f) for f in files)
        if count:
            st.session_state.done = f"그림 {count}장을 올렸어요"
            st.rerun()

# 결과 자리 : 올라와 있는 그림 모두 보기
photos = load_photos()
st.subheader(f"올라와 있는 그림 {len(photos)}장")
if not photos:
    # 보기 허용 규칙이 없으면 오류 없이 빈 목록만 옴
    st.info("아직 올라온 그림이 없어요. 위에서 그림을 올려 보세요. 올렸는데도 안 보이면 Supabase 에서 \"photos 목록 보기\" 허용 규칙을 확인해 주세요")
else:
    # 세 칸으로 나란히, 그림은 작게(가로 200px) 붙여서 보여줌
    # 세 칸 전체 폭을 그림 3장 + 사이 간격 4px 두 번(608px)으로 맞춰 칸이 화면 끝까지 벌어지지 않게 함
    cols = st.columns(3, gap=4, width=608)
    for i, f in enumerate(photos):
        cols[i % 3].image(bucket.get_public_url(f["name"]), caption=photo_caption(f), width="stretch")
