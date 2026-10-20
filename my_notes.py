import os

import streamlit as st
from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import create_client

st.set_page_config(page_title="내 지출 기록")

# .env 의 SUPABASE_URL, SUPABASE_KEY 로 Supabase 에 연결
load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# submissions 표 : 팀원 줄(row_type=member)과 지출 줄(row_type=expense)을 함께 쌓음
# 이 화면은 지출 줄을 넣고, 넣은 지출 줄을 다시 보여줌
TABLE = "submissions"

st.title("내 지출 기록")

# 낸 사람은 등록된 팀원(별칭) 중에서 고름
members = (
    supabase.table(TABLE)
    .select("id, member_alias, is_organizer")
    .eq("row_type", "member")
    .order("created_at")
    .execute()
    .data
)
MEMBER_NAMES = [m["member_alias"] for m in members]
TREASURER = next((m["member_alias"] for m in members if m["is_organizer"]), None)

# 팀원 등록 · 삭제 (팀원이 아직 없으면 펼쳐 둠)
with st.expander("팀원 등록", expanded=not MEMBER_NAMES):
    st.caption("실제 이름 대신 별칭(예: 팀원 A)으로 등록해 주세요")
    st.caption("등록 팀원 : " + (" · ".join(MEMBER_NAMES) or "아직 없음"))

    with st.form("member", clear_on_submit=True):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        alias = c1.text_input("팀원 별칭")
        is_organizer = c2.checkbox("총무")
        registered = st.form_submit_button("팀원 등록")

    if registered:
        alias = alias.strip()
        if not alias:
            st.warning("팀원 별칭을 넣어주세요")
        elif alias in MEMBER_NAMES:
            st.warning("이미 등록된 별칭이에요")
        elif is_organizer and TREASURER:
            st.warning(f"총무는 이미 {TREASURER}(으)로 등록되어 있어요")
        else:
            try:
                supabase.table(TABLE).insert(
                    {"row_type": "member", "member_alias": alias, "is_organizer": is_organizer}
                ).execute()
                st.rerun()
            except APIError as e:
                st.error(f"Supabase 에 저장하지 못했어요 : {e.message}")

    if members:
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        target = c1.selectbox(
            "잘못 등록한 팀원 삭제",
            members,
            index=None,
            format_func=lambda m: m["member_alias"] + (" (총무)" if m["is_organizer"] else ""),
            placeholder="삭제할 팀원 선택",
        )
        if c2.button("삭제", width="stretch"):
            if target is None:
                st.warning("삭제할 팀원을 골라주세요")
            else:
                # 이 팀원이 낸 지출이 있으면 지우지 않음 (지출 줄의 낸 사람이 목록에서 사라지므로)
                used = (
                    supabase.table(TABLE)
                    .select("id")
                    .eq("row_type", "expense")
                    .eq("member_alias", target["member_alias"])
                    .execute()
                    .data
                )
                if used:
                    st.warning(f"{target['member_alias']}(이)가 낸 지출이 {len(used)}건 있어서 삭제할 수 없어요")
                else:
                    deleted = supabase.table(TABLE).delete().eq("id", target["id"]).execute().data
                    if deleted:
                        st.rerun()
                    # 삭제 권한(policy)이 없으면 오류 없이 0줄만 지워짐
                    st.error("삭제되지 않았어요. Supabase 에서 삭제 권한(policy)을 확인해 주세요")

if not MEMBER_NAMES:
    st.info("등록된 팀원이 아직 없어요. 위 \"팀원 등록\"에서 먼저 등록해 주세요")

with st.form("write", clear_on_submit=True):
    kind = st.radio("구분", ["예약", "현장"], horizontal=True)
    spent_on = st.date_input("날짜", value=None, format="YYYY-MM-DD")
    item = st.text_input("항목", placeholder="예: 점심 식사")
    amount = st.number_input("금액 (원)", min_value=0, step=1000)
    payer = st.selectbox("낸 사람", MEMBER_NAMES, index=None, placeholder="팀원 선택")
    submitted = st.form_submit_button("저장")

if submitted:
    item = item.strip()
    if spent_on is None or not item or not amount or payer is None:
        st.warning("날짜·항목·금액·낸 사람을 모두 넣어주세요")
    else:
        row = {
            "row_type": "expense",
            "member_alias": payer,
            "spent_on": spent_on.isoformat(),
            "item": item,
            "amount": int(amount),
            "category": kind,
        }
        try:
            supabase.table(TABLE).insert(row).execute()
            st.success("지출을 저장했어요")
        except APIError as e:
            st.error(f"Supabase 에 저장하지 못했어요 : {e.message}")

# 최신 지출이 위로 오게 불러오기
rows = (
    supabase.table(TABLE)
    .select("category, spent_on, item, amount, member_alias, created_at")
    .eq("row_type", "expense")
    .order("created_at", desc=True)
    .execute()
    .data
)

st.subheader(f"저장한 지출 {len(rows)}건")
if not rows:
    st.write("아직 저장한 지출이 없어요")
for row in rows:
    # 총무가 낸 지출은 돌려줄 금액 0, 팀원이 낸 지출은 금액 그대로
    refund = 0 if row["member_alias"] == TREASURER else row["amount"]
    st.text(
        f"[{row['category'] or '-'}] {row['spent_on']} · {row['item']} · "
        f"{row['amount']:,}원 · 낸 사람 {row['member_alias']} · 돌려줄 금액 {refund:,}원"
    )
    st.caption(row["created_at"][:16].replace("T", " "))
