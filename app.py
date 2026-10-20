import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import create_client

from chatbot import chatbot

st.set_page_config(page_title="경비 지출 입력")

# .env 의 SUPABASE_URL, SUPABASE_KEY 로 Supabase 에 연결
load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# submissions 표 : 한 표에 모임 줄(row_type=group), 팀원 줄(row_type=member), 지출 줄(row_type=expense)을 함께 쌓음
# 팀원 줄과 지출 줄은 group_name 칸으로 어느 모임 것인지 나눔
TABLE = "submissions"

# group_name 칸이 없을 때 Supabase SQL Editor 에서 한 번 실행할 SQL
# 모임 줄에는 팀원 별칭이 없으므로 member_alias 를 비워도 되게 바꾸고, row_type 에 group 을 허용하고,
# 기존 팀원·지출은 "여행모임" 으로 옮김
GROUP_SQL = """alter table submissions alter column member_alias drop not null;

alter table submissions drop constraint if exists submissions_row_type_check;
alter table submissions add constraint submissions_row_type_check
  check (row_type in ('member', 'expense', 'group'));

alter table submissions add column if not exists group_name text;

update submissions set group_name = '여행모임'
where group_name is null and row_type in ('member', 'expense');

insert into submissions (row_type, group_name)
select 'group', '여행모임'
where not exists (
  select 1 from submissions where row_type = 'group' and group_name = '여행모임'
);"""

COLUMNS = ["구분", "날짜", "항목", "금액", "낸 사람", "돌려줄 금액"]

MONEY_COLUMNS = {
    "금액": st.column_config.NumberColumn(format="localized"),
    "돌려줄 금액": st.column_config.NumberColumn(format="localized"),
}


def load_rows(row_type, group=None):
    # 넣은 순서대로 불러오기 (group 을 주면 그 모임 것만)
    query = supabase.table(TABLE).select("*").eq("row_type", row_type)
    if group is not None:
        query = query.eq("group_name", group)
    return query.order("created_at").execute().data


def save(row, done_message):
    try:
        supabase.table(TABLE).insert(row).execute()
    except APIError as e:
        st.error(f"Supabase 에 저장하지 못했어요 : {e.message}")
        return False
    st.success(done_message)
    return True


# group_name 칸이 있는지 먼저 확인
try:
    supabase.table(TABLE).select("group_name").limit(1).execute()
except APIError:
    st.error("모임 이름을 저장할 칸(group_name)이 Supabase 표에 아직 없어요. Supabase SQL Editor 에서 아래 SQL 을 한 번 실행한 뒤 새로고침해 주세요")
    st.code(GROUP_SQL, language="sql")
    st.stop()

# 모임 목록
groups = load_rows("group")
GROUP_NAMES = [g["group_name"] for g in groups]


def add_group(name):
    name = name.strip()
    if not name:
        st.error("모임 이름을 넣어주세요")
        return
    if name in GROUP_NAMES:
        st.error("이미 등록된 모임이에요")
        return
    if save({"row_type": "group", "group_name": name}, "모임을 등록했어요"):
        # 다음 화면에서 새 모임을 골라 둠 (모임 선택 칸이 그려지기 전에 넣어야 함)
        st.session_state.new_group = name
        st.rerun()


def delete_group(group):
    if group is None:
        st.error("삭제할 모임을 골라주세요")
        return
    name = group["group_name"]
    # 이 모임에 팀원이나 지출이 있으면 지우지 않음 (그 줄들이 어느 모임 것도 아니게 되므로)
    used = (
        supabase.table(TABLE)
        .select("id")
        .in_("row_type", ["member", "expense"])
        .eq("group_name", name)
        .execute()
        .data
    )
    if used:
        st.error(f"{name}에 등록된 팀원·지출이 {len(used)}건 있어서 삭제할 수 없어요. 팀원·지출을 먼저 삭제해 주세요")
        return
    try:
        deleted = supabase.table(TABLE).delete().eq("id", group["id"]).execute().data
    except APIError as e:
        st.error(f"Supabase 에서 삭제하지 못했어요 : {e.message}")
        return
    if not deleted:
        # 삭제 권한(policy)이 없으면 오류 없이 0줄만 지워짐
        st.error("삭제되지 않았어요. Supabase 에서 삭제 권한(policy)을 확인해 주세요")
        return
    st.rerun()


def clear_inputs():
    # 모임을 바꾸면 앞 모임 팀원을 고른 칸들을 비움
    for key in ["payer_1", "payer_3", "delete_target", "delete_expense_target_2", "delete_expense_target_3"]:
        st.session_state.pop(key, None)


# 왼쪽 칸 : 모임 고르기 · 새 모임 등록
with st.sidebar:
    st.header("모임")
    if "new_group" in st.session_state:
        st.session_state.group = st.session_state.pop("new_group")
        clear_inputs()
    if st.session_state.get("group") not in GROUP_NAMES:
        st.session_state.pop("group", None)
    if GROUP_NAMES:
        st.selectbox("지금 보는 모임", GROUP_NAMES, key="group", on_change=clear_inputs)
    with st.expander("새 모임 등록", expanded=not GROUP_NAMES):
        new_name = st.text_input("모임 이름", placeholder="예: 친정모임", key="new_group_name")
        if st.button("모임 등록", width="stretch"):
            add_group(new_name)

        if groups:
            st.divider()
            target = st.selectbox(
                "잘못 등록한 모임 삭제",
                groups,
                index=None,
                format_func=lambda g: g["group_name"],
                placeholder="삭제할 모임 선택",
                key="delete_group_target",
            )
            if st.button("삭제", width="stretch", key="delete_group"):
                delete_group(target)

if not GROUP_NAMES:
    st.title("경비 지출 입력")
    st.info("왼쪽 \"새 모임 등록\"에서 모임을 먼저 등록해 주세요")
    st.stop()

GROUP = st.session_state.group

# 팀원 목록 : 별칭, 총무 여부 (지금 고른 모임 것만)
members = load_rows("member", GROUP)
MEMBER_NAMES = [m["member_alias"] for m in members]
TREASURER = next((m["member_alias"] for m in members if m["is_organizer"]), None)


def refund_amount(payer, amount):
    # 총무가 낸 지출은 돌려줄 금액 0, 팀원이 낸 지출은 금액 그대로
    return 0 if payer == TREASURER else amount


def load_expenses():
    rows = load_rows("expense", GROUP)
    expenses = pd.DataFrame(
        [
            {
                "구분": r["category"],
                "날짜": r["spent_on"],
                "항목": r["item"],
                "금액": r["amount"],
                "낸 사람": r["member_alias"],
                "돌려줄 금액": refund_amount(r["member_alias"], r["amount"]),
            }
            for r in rows
        ],
        columns=COLUMNS,
    )
    return expenses


if "page" not in st.session_state:
    st.session_state.page = 1


def go(page):
    st.session_state.page = page


def add_member(alias, is_organizer):
    alias = alias.strip()
    if not alias:
        st.error("팀원 별칭을 넣어주세요")
        return
    if alias in MEMBER_NAMES:
        st.error("이미 등록된 별칭이에요")
        return
    if is_organizer and TREASURER:
        st.error(f"총무는 이미 {TREASURER}(으)로 등록되어 있어요")
        return
    row = {"row_type": "member", "group_name": GROUP, "member_alias": alias, "is_organizer": is_organizer}
    if save(row, "팀원을 등록했어요"):
        st.rerun()


def delete_member(member):
    if member is None:
        st.error("삭제할 팀원을 골라주세요")
        return
    alias = member["member_alias"]
    # 이 팀원이 낸 지출이 있으면 지우지 않음 (지출 줄의 낸 사람이 목록에서 사라지므로)
    used = (
        supabase.table(TABLE)
        .select("id")
        .eq("row_type", "expense")
        .eq("group_name", GROUP)
        .eq("member_alias", alias)
        .execute()
        .data
    )
    if used:
        st.error(f"{alias}(이)가 낸 지출이 {len(used)}건 있어서 삭제할 수 없어요")
        return
    try:
        deleted = supabase.table(TABLE).delete().eq("id", member["id"]).execute().data
    except APIError as e:
        st.error(f"Supabase 에서 삭제하지 못했어요 : {e.message}")
        return
    if not deleted:
        # 삭제 권한(policy)이 없으면 오류 없이 0줄만 지워짐
        st.error("삭제되지 않았어요. Supabase 에서 삭제 권한(policy)을 확인해 주세요")
        return
    st.rerun()


def delete_expense(expense):
    if expense is None:
        st.error("삭제할 지출을 골라주세요")
        return
    try:
        deleted = supabase.table(TABLE).delete().eq("id", expense["id"]).execute().data
    except APIError as e:
        st.error(f"Supabase 에서 삭제하지 못했어요 : {e.message}")
        return
    if not deleted:
        # 삭제 권한(policy)이 없으면 오류 없이 0줄만 지워짐
        st.error("삭제되지 않았어요. Supabase 에서 삭제 권한(policy)을 확인해 주세요")
        return
    st.rerun()


def expense_label(r):
    # 삭제할 지출 고르는 칸에 보일 한 줄 : 날짜 · 항목 · 금액 · 낸 사람
    return f"{r['spent_on']} · {r['item']} · {r['amount']:,}원 · {r['member_alias']}"


def add_expense(kind, date, item, amount, payer):
    if not date or not item or not amount or payer is None:
        st.error("날짜·항목·금액·낸 사람을 모두 넣어주세요")
        return
    if payer not in MEMBER_NAMES:
        st.error("등록된 팀원 중에 없는 이름이에요. 목록에서 골라주세요")
        st.caption("등록 팀원 : " + " · ".join(MEMBER_NAMES))
        return
    row = {
        "row_type": "expense",
        "group_name": GROUP,
        "member_alias": payer,
        "spent_on": date.isoformat(),
        "item": item,
        "amount": int(amount),
        "category": kind,
    }
    save(row, "지출을 추가했어요")


def date_field(where, key):
    # 직접 입력도 되고, 칸을 누르면 달력이 열려 클릭으로 고를 수도 있음
    return where.date_input("날짜", value=None, format="YYYY-MM-DD", key=key)


def expense_delete_form(page):
    # 잘못 입력한 지출 삭제 (화면 2, 3 에서 같이 씀)
    expense_rows = load_rows("expense", GROUP)
    if not expense_rows:
        return
    st.divider()
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    target = c1.selectbox(
        "잘못 입력한 지출 삭제",
        expense_rows,
        index=None,
        format_func=expense_label,
        placeholder="삭제할 지출 선택",
        key=f"delete_expense_target_{page}",
    )
    if c2.button("삭제", width="stretch", key=f"delete_expense_{page}"):
        delete_expense(target)


def member_form():
    # 팀원이 아직 없으면 펼쳐 둠
    with st.expander("팀원 등록", expanded=not MEMBER_NAMES):
        st.caption("실제 이름 대신 별칭(예: 팀원 A)으로 등록해 주세요")
        c1, c2 = st.columns([3, 1])
        alias = c1.text_input("팀원 별칭", key="alias")
        is_organizer = c2.checkbox("총무", key="is_organizer")
        if st.button("팀원 등록", width="stretch"):
            add_member(alias, is_organizer)

        if members:
            st.divider()
            c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
            target = c1.selectbox(
                "잘못 등록한 팀원 삭제",
                members,
                index=None,
                format_func=lambda m: m["member_alias"] + (" (총무)" if m["is_organizer"] else ""),
                placeholder="삭제할 팀원 선택",
                key="delete_target",
            )
            if c2.button("삭제", width="stretch"):
                delete_member(target)


st.caption(f"모임 : {GROUP} · 저장 위치 : Supabase {TABLE} 표 · 총무 : {TREASURER or '아직 없음'}")

# 모든 화면 오른쪽 아래에 챗봇 아이콘
chatbot()

# 화면 1 : 지출 입력
if st.session_state.page == 1:
    st.title("지출 입력")
    st.caption("화면 1 / 3")

    member_form()

    # 넣는 자리
    date = date_field(st, "date_1")
    item = st.text_input("항목", placeholder="예: 점심 식사", key="item_1")
    amount = st.number_input("금액 (원)", min_value=0, step=1000, key="amount_1")
    payer = st.selectbox(
        "낸 사람 (팀원 목록에서 선택)",
        MEMBER_NAMES,
        index=None,
        placeholder="팀원 선택",
        key="payer_1",
    )
    st.caption("등록 팀원 : " + (" · ".join(MEMBER_NAMES) or "아직 없음"))

    # 단추
    b1, b2 = st.columns(2)
    added = b1.button("추가", type="primary", width="stretch")
    b2.button("지출 목록 보기", on_click=go, args=(2,), width="stretch")

    if added:
        add_expense(None, date, item, amount, payer)

    # 결과 자리 : 가장 최근에 들어간 한 줄
    st.subheader("결과")
    latest = load_expenses().tail(1).drop(columns="구분")
    st.dataframe(latest, hide_index=True, width="stretch", column_config=MONEY_COLUMNS)

# 화면 2 : 지출 목록
elif st.session_state.page == 2:
    st.title("지출 목록")
    st.caption("화면 2 / 3")

    # 단추
    b1, b2 = st.columns(2)
    b1.button("← 지출 입력으로 돌아가기", on_click=go, args=(1,), width="stretch")
    b2.button("여행 경비 정리 보기 →", on_click=go, args=(3,), width="stretch")

    # 결과 자리
    expenses = load_expenses().drop(columns="구분")
    st.dataframe(expenses, hide_index=True, width="stretch", column_config=MONEY_COLUMNS)
    st.caption(f"지출 {len(expenses)}건")
    st.caption(f"낸 사람이 총무({TREASURER or '아직 없음'})가 아니면 \"돌려줄 금액\" 칸에 그 금액이 그대로 나와요")

    expense_delete_form(2)

# 화면 3 : 여행 경비 정리
else:
    st.title("여행 경비 정리")
    st.caption("화면 3 / 3")

    # 넣는 자리
    with st.container(border=True):
        st.markdown("**입력 칸**")
        kind = st.radio("구분", ["예약", "현장"], horizontal=True, key="kind_3")
        c1, c2 = st.columns(2)
        date = date_field(c1, "date_3")
        item = c2.text_input("항목", placeholder="예: 숙소", key="item_3")
        c3, c4 = st.columns(2)
        amount = c3.number_input("금액 (원)", min_value=0, step=1000, key="amount_3")
        payer = c4.selectbox(
            "낸 사람 (카드 주인)",
            MEMBER_NAMES,
            index=None,
            placeholder="팀원 선택",
            key="payer_3",
        )

        # 단추
        b1, b2 = st.columns(2)
        added = b1.button("추가", type="primary", width="stretch")
        b2.button("← 목록으로 돌아가기", on_click=go, args=(2,), width="stretch")

        if added:
            add_expense(kind, date, item, amount, payer)

    # 결과 자리
    st.dataframe(load_expenses(), hide_index=True, width="stretch", column_config=MONEY_COLUMNS)
    st.caption("예약 비용과 현장 경비가 입력한 순서대로 같은 표 안에 쌓여요")

    expense_delete_form(3)
