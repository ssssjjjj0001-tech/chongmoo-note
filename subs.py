from datetime import date

import pandas as pd
import streamlit as st
from postgrest.exceptions import APIError
from supabase import create_client

from keys import get_key

st.set_page_config(page_title="구독 정리함")

# .env(내 컴퓨터) 또는 Secrets(올린 곳) 의 SUPABASE_URL, SUPABASE_KEY 로 Supabase 에 연결
supabase = create_client(get_key("SUPABASE_URL"), get_key("SUPABASE_KEY"))

# subscriptions 표 : id, name(구독 이름), category(분류), monthly_fee(한 달 요금), last_used(마지막으로 쓴 날), created_at
# 표는 data/76_subscriptions.sql 을 Supabase SQL Editor 에서 실행해 만듦
TABLE = "subscriptions"

st.title("구독 정리함")

# 표가 있는지 먼저 확인
try:
    supabase.table(TABLE).select("id").limit(1).execute()
except APIError:
    st.error("Supabase 에 subscriptions 표가 아직 없어요. data/76_subscriptions.sql 을 Supabase SQL Editor 에 붙여넣고 Run 한 뒤 새로고침해 주세요")
    st.stop()


def load_subs():
    # 넣은 순서대로 불러오기
    return supabase.table(TABLE).select("*").order("id").execute().data


def check_row(name, category):
    if not name.strip() or not category.strip():
        st.error("구독 이름과 분류를 모두 넣어주세요")
        return False
    return True


def to_row(name, category, monthly_fee, last_used):
    return {
        "name": name.strip(),
        "category": category.strip(),
        "monthly_fee": int(monthly_fee),
        "last_used": last_used.isoformat() if last_used else None,
    }


def add_sub(row):
    try:
        supabase.table(TABLE).insert(row).execute()
    except APIError as e:
        st.error(f"Supabase 에 저장하지 못했어요 : {e.message}")
        return
    st.session_state.done = "구독을 추가했어요"
    st.rerun()


def update_sub(sub_id, row):
    try:
        updated = supabase.table(TABLE).update(row).eq("id", sub_id).execute().data
    except APIError as e:
        st.error(f"Supabase 에 고치지 못했어요 : {e.message}")
        return
    if not updated:
        # 고치기 권한(policy)이 없으면 오류 없이 0줄만 고쳐짐
        st.error("고쳐지지 않았어요. Supabase 에서 고치기 권한(policy)을 확인해 주세요")
        return
    st.session_state.done = "구독을 고쳤어요"
    st.rerun()


def delete_sub(sub_id):
    try:
        deleted = supabase.table(TABLE).delete().eq("id", sub_id).execute().data
    except APIError as e:
        st.error(f"Supabase 에서 삭제하지 못했어요 : {e.message}")
        return
    if not deleted:
        # 삭제 권한(policy)이 없으면 오류 없이 0줄만 지워짐
        st.error("삭제되지 않았어요. Supabase 에서 삭제 권한(policy)을 확인해 주세요")
        return
    st.session_state.done = "구독을 삭제했어요"
    st.rerun()


def sub_label(s):
    # 고치거나 지울 구독 고르는 칸에 보일 한 줄 : 이름 · 분류 · 요금
    return f"{s['name']} · {s['category']} · {s['monthly_fee']:,}원"


subs = load_subs()
CATEGORIES = sorted({s["category"] for s in subs})

# 앞 화면에서 저장·고치기·삭제가 끝났으면 알림
if "done" in st.session_state:
    st.success(st.session_state.pop("done"))

# 결과 자리 : 구독 표 · 한 달 합계
table = pd.DataFrame(
    [
        {
            "구독 이름": s["name"],
            "분류": s["category"],
            "한 달 요금": s["monthly_fee"],
            "마지막으로 쓴 날": s["last_used"],
        }
        for s in subs
    ],
    columns=["구독 이름", "분류", "한 달 요금", "마지막으로 쓴 날"],
)
st.dataframe(
    table,
    hide_index=True,
    width="stretch",
    column_config={"한 달 요금": st.column_config.NumberColumn(format="localized")},
)

c1, c2 = st.columns(2)
c1.metric("구독 수", f"{len(subs)}개")
c2.metric("한 달 합계", f"{int(table['한 달 요금'].sum()):,}원")
if CATEGORIES:
    st.caption("분류 : " + " · ".join(CATEGORIES))

# 넣는 자리 : 더하기 · 고치기 · 지우기
add_tab, edit_tab, delete_tab = st.tabs(["구독 더하기", "구독 고치기", "구독 지우기"])

with add_tab:
    with st.form("add"):
        c1, c2 = st.columns(2)
        name = c1.text_input("구독 이름", placeholder="예: 음악 구독")
        category = c2.text_input("분류", placeholder="예: 음악")
        c3, c4 = st.columns(2)
        monthly_fee = c3.number_input("한 달 요금 (원)", min_value=0, step=100)
        last_used = c4.date_input("마지막으로 쓴 날", value=None, format="YYYY-MM-DD")
        added = st.form_submit_button("더하기", type="primary", width="stretch")
    if added and check_row(name, category):
        add_sub(to_row(name, category, monthly_fee, last_used))

with edit_tab:
    target = st.selectbox("고칠 구독", subs, index=None, format_func=sub_label, placeholder="고칠 구독 선택", key="edit_target")
    if target is not None:
        # 고를 때마다 그 구독의 지금 값이 미리 들어가도록 칸 이름에 id 를 붙임
        sid = target["id"]
        with st.form(f"edit_{sid}"):
            c1, c2 = st.columns(2)
            name = c1.text_input("구독 이름", value=target["name"], key=f"name_{sid}")
            category = c2.text_input("분류", value=target["category"], key=f"category_{sid}")
            c3, c4 = st.columns(2)
            monthly_fee = c3.number_input(
                "한 달 요금 (원)", min_value=0, step=100, value=target["monthly_fee"], key=f"fee_{sid}"
            )
            last_used = c4.date_input(
                "마지막으로 쓴 날",
                value=date.fromisoformat(target["last_used"]) if target["last_used"] else None,
                format="YYYY-MM-DD",
                key=f"last_used_{sid}",
            )
            saved = st.form_submit_button("고친 내용 저장", type="primary", width="stretch")
        if saved and check_row(name, category):
            update_sub(sid, to_row(name, category, monthly_fee, last_used))

with delete_tab:
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    target = c1.selectbox("지울 구독", subs, index=None, format_func=sub_label, placeholder="지울 구독 선택", key="delete_target")
    if c2.button("삭제", width="stretch"):
        if target is None:
            st.error("삭제할 구독을 골라주세요")
        else:
            delete_sub(target["id"])
