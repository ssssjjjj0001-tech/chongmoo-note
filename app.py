import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import create_client

from chatbot import chatbot

# 넓은 화면 : 왼쪽 넣는 칸 · 가운데 결과를 스크롤 없이 한눈에 보도록
st.set_page_config(page_title="총무노트", page_icon="💰", layout="wide")

# .env 의 SUPABASE_URL, SUPABASE_KEY 로 Supabase 에 연결
load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# submissions 표 : 한 표에 모임 줄(row_type=group), 팀원 줄(row_type=member), 지출 줄(row_type=expense)을 함께 쌓음
# 팀원 줄과 지출 줄은 group_name 칸으로 어느 모임 것인지, book 칸으로 어느 장부(친목/여행) 것인지 나눔
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

# book 칸이 없을 때 Supabase SQL Editor 에서 한 번 실행할 SQL
# 기존 지출은 구분이 비어 있으면 친목, 예약/현장이면 여행으로, 기존 팀원은 친목으로 옮김
BOOK_SQL = """alter table submissions add column if not exists book text;

alter table submissions drop constraint if exists submissions_book_check;
alter table submissions add constraint submissions_book_check
  check (book is null or book in ('친목', '여행'));

update submissions set book = case when category is null then '친목' else '여행' end
where book is null and row_type = 'expense';

update submissions set book = '친목'
where book is null and row_type = 'member';"""

# 장부 : 친목모임 지출(화면 1)과 여행 경비(화면 3)를 따로 관리
BOOKS = ["친목", "여행"]
BOOK_TITLE = {"친목": "친목모임", "여행": "여행"}
LIST_TITLE = {"친목": "친목모임 지출", "여행": "여행 경비 지출"}

COLUMNS = ["구분", "날짜", "항목", "금액", "낸 사람", "돌려줄 금액"]

MONEY_COLUMNS = {
    "금액": st.column_config.NumberColumn(format="localized"),
    "돌려줄 금액": st.column_config.NumberColumn(format="localized"),
}


def load_rows(row_type, group=None, book=None):
    # 넣은 순서대로 불러오기 (group, book 을 주면 그 모임·장부 것만)
    query = supabase.table(TABLE).select("*").eq("row_type", row_type)
    if group is not None:
        query = query.eq("group_name", group)
    if book is not None:
        query = query.eq("book", book)
    return query.order("created_at").execute().data


def save(row, done_message):
    try:
        supabase.table(TABLE).insert(row).execute()
    except APIError as e:
        st.error(f"Supabase 에 저장하지 못했어요 : {e.message}")
        return False
    st.success(done_message)
    return True


def delete_rows(ids):
    # 고른 줄들을 한 번에 지움
    try:
        deleted = supabase.table(TABLE).delete().in_("id", ids).execute().data
    except APIError as e:
        st.error(f"Supabase 에서 삭제하지 못했어요 : {e.message}")
        return
    if len(deleted) < len(ids):
        # 삭제 권한(policy)이 없으면 오류 없이 0줄만 지워짐
        st.error("삭제되지 않았어요. Supabase 에서 삭제 권한(policy)을 확인해 주세요")
        return
    st.rerun()


# group_name, book 칸이 있는지 먼저 확인
for column, sql in [("group_name", GROUP_SQL), ("book", BOOK_SQL)]:
    try:
        supabase.table(TABLE).select(column).limit(1).execute()
    except APIError:
        st.error(f"저장할 칸({column})이 Supabase 표에 아직 없어요. Supabase SQL Editor 에서 아래 SQL 을 한 번 실행한 뒤 새로고침해 주세요")
        st.code(sql, language="sql")
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


def delete_groups(checked):
    if not checked:
        st.error("삭제할 모임에 체크해 주세요")
        return
    names = [g["group_name"] for g in checked]
    # 팀원이나 지출이 있는 모임은 지우지 않음 (그 줄들이 어느 모임 것도 아니게 되므로)
    used = (
        supabase.table(TABLE)
        .select("group_name")
        .in_("row_type", ["member", "expense"])
        .in_("group_name", names)
        .execute()
        .data
    )
    if used:
        blocked = " · ".join(sorted({r["group_name"] for r in used}))
        st.error(f"{blocked}에 등록된 팀원·지출이 있어서 삭제할 수 없어요. 팀원·지출을 먼저 삭제해 주세요")
        return
    delete_rows([g["id"] for g in checked])


def clear_inputs():
    # 모임을 바꾸면 앞 모임 팀원·지출을 고른 칸들을 비움
    for key in list(st.session_state.keys()):
        if key in ("payer_1", "payer_3") or key.startswith("delete_expense_target_"):
            st.session_state.pop(key)


def member_label(m):
    return m["member_alias"] + (" (총무)" if m["is_organizer"] else "")


def group_section():
    # 모임 등록 · 체크한 모임 삭제 (모임·팀원 관리 탭, 모임이 하나도 없으면 첫 화면에 바로 보임)
    st.subheader("모임 등록·삭제")
    new_name = st.text_input("모임 이름", placeholder="예: 낭만아줌모임", key="new_group_name")
    if st.button("모임 등록", width="stretch"):
        add_group(new_name)

    if groups:
        st.divider()
        st.caption("잘못 등록한 모임은 체크하고 삭제를 눌러주세요")
        checked = [g for g in groups if st.checkbox(g["group_name"], key=f"del_group_{g['id']}")]
        if st.button("체크한 모임 삭제", width="stretch", key="delete_groups"):
            delete_groups(checked)


def service_header():
    # 첫 화면 맨 위 : 서비스 이름 크게 + 처음 쓰는 사람도 알 수 있는 한 줄 설명
    st.title("💰 총무노트")
    st.caption("지출마다 날짜·항목·금액·낸 사람(카드)을 적으면, 총무가 아닌 팀원 카드로 낸 지출은 그 팀원에게 돌려줄 금액이 자동으로 나와요")


# 사이드바 : 지금 보는 모임 고르기
with st.sidebar:
    st.header("모임")
    if "new_group" in st.session_state:
        st.session_state.group = st.session_state.pop("new_group")
        clear_inputs()
    if st.session_state.get("group") not in GROUP_NAMES:
        st.session_state.pop("group", None)
    if GROUP_NAMES:
        st.selectbox("지금 보는 모임", GROUP_NAMES, key="group", on_change=clear_inputs)

if not GROUP_NAMES:
    # 모임이 하나도 없으면 첫 화면 가운데 열에 모임 등록 칸만
    _, center, _ = st.columns([1, 2, 1])
    with center:
        service_header()
        st.info("아래에서 모임을 먼저 등록해 주세요")
        group_section()
    st.stop()

GROUP = st.session_state.group

# 팀원 목록 : 별칭, 총무 여부 (지금 고른 모임 것만, 장부별로 나눔)
members = load_rows("member", GROUP)
MEMBERS = {b: [m for m in members if m["book"] == b] for b in BOOKS}
MEMBER_NAMES = {b: [m["member_alias"] for m in MEMBERS[b]] for b in BOOKS}
TREASURERS = {b: next((m["member_alias"] for m in MEMBERS[b] if m["is_organizer"]), None) for b in BOOKS}


def refund_amount(book, payer, amount):
    # 그 장부의 총무가 낸 지출은 돌려줄 금액 0, 팀원이 낸 지출은 금액 그대로
    return 0 if payer == TREASURERS[book] else amount


def per_person(total, count):
    # 1인당 금액 : 100원 단위에서 올림 (예: 100,000원 ÷ 3명 = 33,400원)
    return -(-total // (count * 100)) * 100


def won(amount):
    return f"{int(amount):,}원"


def load_expenses(book):
    rows = load_rows("expense", GROUP, book)
    expenses = pd.DataFrame(
        [
            {
                "구분": r["category"],
                "날짜": r["spent_on"],
                "항목": r["item"],
                "금액": r["amount"],
                "낸 사람": r["member_alias"],
                "돌려줄 금액": refund_amount(book, r["member_alias"], r["amount"]),
            }
            for r in rows
        ],
        columns=COLUMNS,
    )
    return expenses


def sort_expenses(expenses, order):
    # 날짜는 YYYY-MM-DD 글자라 글자 순서가 곧 날짜 순서
    if order == "날짜순":
        return expenses.sort_values("날짜", kind="stable")
    if order == "팀원별":
        return expenses.sort_values(["낸 사람", "날짜"], kind="stable")
    return expenses


def add_member(book, alias, is_organizer):
    alias = alias.strip()
    if not alias:
        st.error("팀원 별칭을 넣어주세요")
        return
    if alias in MEMBER_NAMES[book]:
        st.error("이미 등록된 별칭이에요")
        return
    if is_organizer and TREASURERS[book]:
        st.error(f"{BOOK_TITLE[book]} 총무는 이미 {TREASURERS[book]}(으)로 등록되어 있어요")
        return
    row = {"row_type": "member", "group_name": GROUP, "book": book, "member_alias": alias, "is_organizer": is_organizer}
    if save(row, "팀원을 등록했어요"):
        st.rerun()


def delete_members(book, checked):
    if not checked:
        st.error("삭제할 팀원에 체크해 주세요")
        return
    aliases = [m["member_alias"] for m in checked]
    # 이 팀원이 낸 지출이 있으면 지우지 않음 (지출 줄의 낸 사람이 목록에서 사라지므로)
    used = (
        supabase.table(TABLE)
        .select("member_alias")
        .eq("row_type", "expense")
        .eq("group_name", GROUP)
        .eq("book", book)
        .in_("member_alias", aliases)
        .execute()
        .data
    )
    if used:
        blocked = " · ".join(sorted({r["member_alias"] for r in used}))
        st.error(f"{blocked}(이)가 낸 지출이 있어서 삭제할 수 없어요")
        return
    delete_rows([m["id"] for m in checked])


def member_section(book):
    # 모임·팀원 관리 탭 : 장부별 팀원 목록 (이름 옆 체크박스로 삭제) · 팀원 등록
    st.subheader(f"{BOOK_TITLE[book]} 팀원")
    if MEMBERS[book]:
        checked = [m for m in MEMBERS[book] if st.checkbox(member_label(m), key=f"del_member_{m['id']}")]
        if st.button("체크한 팀원 삭제", width="stretch", key=f"delete_members_{book}"):
            delete_members(book, checked)
    else:
        st.caption("아직 없음")

    # 팀원이 아직 없으면 펼쳐 둠
    with st.expander("팀원 등록", expanded=not MEMBERS[book]):
        st.caption("실제 이름 대신 별칭(예: 팀원 A)으로 등록해 주세요")
        alias = st.text_input("팀원 별칭", key=f"alias_{book}")
        is_organizer = st.checkbox("총무", key=f"is_organizer_{book}")
        if st.button("팀원 등록", width="stretch", key=f"add_member_{book}"):
            add_member(book, alias, is_organizer)


# 사이드바 : 장부별 팀원 목록 (보기만, 등록·삭제는 모임·팀원 관리 탭에서)
with st.sidebar:
    for book in BOOKS:
        st.divider()
        st.subheader(f"{BOOK_TITLE[book]} 팀원")
        if MEMBERS[book]:
            st.markdown("\n".join(f"- {member_label(m)}" for m in MEMBERS[book]))
        else:
            st.caption("아직 없음")


def expense_label(r):
    # 삭제할 지출 고르는 칸에 보일 한 줄 : 날짜 · 항목 · 금액 · 낸 사람
    return f"{r['spent_on']} · {r['item']} · {r['amount']:,}원 · {r['member_alias']}"


def add_expense(book, kind, date, item, amount, payer):
    if not date or not item or not amount or payer is None:
        st.error("날짜·항목·금액·낸 사람을 모두 넣어주세요")
        return
    if payer not in MEMBER_NAMES[book]:
        st.error("등록된 팀원 중에 없는 이름이에요. 목록에서 골라주세요")
        st.caption("등록 팀원 : " + " · ".join(MEMBER_NAMES[book]))
        return
    row = {
        "row_type": "expense",
        "group_name": GROUP,
        "book": book,
        "member_alias": payer,
        "spent_on": date.isoformat(),
        "item": item,
        "amount": int(amount),
        "category": kind,
    }
    save(row, "지출을 추가했어요")


def date_field(where, key):
    # 오늘 날짜가 미리 들어가 있고, 직접 입력도 되고, 칸을 누르면 달력이 열려 클릭으로 고를 수도 있음
    return where.date_input("날짜", value="today", format="YYYY-MM-DD", key=key)


def expense_delete_form(book):
    # 잘못 입력한 지출 삭제 (모임·팀원 관리 탭에서 장부를 골라 씀)
    expense_rows = load_rows("expense", GROUP, book)
    if not expense_rows:
        st.caption(f"{LIST_TITLE[book]}이 아직 없어요")
        return
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    target = c1.selectbox(
        "잘못 입력한 지출 삭제",
        expense_rows,
        index=None,
        format_func=expense_label,
        placeholder="삭제할 지출 선택",
        key=f"delete_expense_target_{book}",
    )
    if c2.button("삭제", width="stretch", key=f"delete_expense_{book}"):
        if target is None:
            st.error("삭제할 지출을 골라주세요")
        else:
            delete_rows([target["id"]])


def show_totals(book, expenses):
    # 총액 · 1인당 금액을 한 줄로 (여행은 예약·현장 합계까지 4칸, 돌려줄 금액과 서로 빼지 않고 보여주기만 함)
    total = int(expenses["금액"].sum())
    count = len(MEMBERS[book])
    cells = st.columns(4 if book == "여행" else 2)
    if book == "여행":
        cells[0].metric("예약 합계", won(expenses.loc[expenses["구분"] == "예약", "금액"].sum()))
        cells[1].metric("현장 합계", won(expenses.loc[expenses["구분"] == "현장", "금액"].sum()))
    cells[-2].metric("총액", won(total))
    if count:
        cells[-1].metric(f"1인당 ({count}명)", won(per_person(total, count)))
        st.caption(f"1인당 금액 = 총액 ÷ {BOOK_TITLE[book]} 팀원 {count}명, 100원 단위에서 올림 · \"돌려줄 금액\"과 서로 빼지 않아요")
    else:
        cells[-1].metric("1인당", "-")
        st.caption(f"모임·팀원 관리 탭에서 {BOOK_TITLE[book]} 팀원을 등록하면 1인당 금액이 나와요")


def expense_list(book):
    # 가운데 열 : 맨 위 합계 한 줄, 그 아래 정렬과 지출 목록 표 (입력순이면 방금 추가한 줄이 표 맨 아래에 쌓임)
    expenses = load_expenses(book)
    show_totals(book, expenses)
    order = st.radio("정렬", ["입력순", "날짜순", "팀원별"], horizontal=True, key=f"sort_order_{book}")
    shown = sort_expenses(expenses, order)
    if book == "친목":
        shown = shown.drop(columns="구분")
    st.dataframe(shown, hide_index=True, width="stretch", column_config=MONEY_COLUMNS)
    st.caption(f"{LIST_TITLE[book]} {len(expenses)}건")
    st.caption(f"낸 사람이 {BOOK_TITLE[book]} 총무({TREASURERS[book] or '아직 없음'})가 아니면 \"돌려줄 금액\" 칸에 그 금액이 그대로 나와요")
    if book == "여행":
        st.caption("예약 비용과 현장 경비가 입력한 순서대로 같은 표 안에 쌓여요")


# 모든 화면 오른쪽 아래에 챗봇 아이콘
chatbot()

service_header()

# 위 탭 3개 : 장부 두 개 + 가끔 쓰는 관리
tab_friend, tab_trip, tab_manage = st.tabs(["친목모임 지출", "여행 경비", "모임·팀원 관리"])

# 탭 1 : 친목모임 지출 (왼쪽 넣는 칸 · 가운데 결과)
with tab_friend:
    st.caption(f"모임 : {GROUP} · 총무 : {TREASURERS['친목'] or '아직 없음'}")
    left, center = st.columns([1, 2])

    # 넣는 자리
    with left, st.container(border=True):
        date = date_field(st, "date_1")
        item = st.text_input("항목", placeholder="예: 점심 식사", key="item_1")
        amount = st.number_input("금액 (원)", min_value=0, step=1000, key="amount_1")
        payer = st.selectbox(
            "낸 사람 (친목모임 팀원 목록에서 선택)",
            MEMBER_NAMES["친목"],
            index=None,
            placeholder="팀원 선택",
            key="payer_1",
        )
        st.caption("등록 팀원 : " + (" · ".join(MEMBER_NAMES["친목"]) or "아직 없음 (모임·팀원 관리 탭에서 친목모임 팀원을 등록해 주세요)"))

        if st.button("추가", type="primary", width="stretch", key="add_expense_1"):
            add_expense("친목", None, date, item, amount, payer)

    # 결과 자리
    with center:
        expense_list("친목")

# 탭 2 : 여행 경비 (왼쪽 넣는 칸 · 가운데 결과)
with tab_trip:
    st.caption(f"모임 : {GROUP} · 총무 : {TREASURERS['여행'] or '아직 없음'}")
    left, center = st.columns([1, 2])

    # 넣는 자리
    with left, st.container(border=True):
        kind = st.radio("구분", ["예약", "현장"], horizontal=True, key="kind_3")
        date = date_field(st, "date_3")
        item = st.text_input("항목", placeholder="예: 숙소", key="item_3")
        amount = st.number_input("금액 (원)", min_value=0, step=1000, key="amount_3")
        payer = st.selectbox(
            "낸 사람 (여행 팀원 중 카드 주인)",
            MEMBER_NAMES["여행"],
            index=None,
            placeholder="팀원 선택",
            key="payer_3",
        )
        if not MEMBER_NAMES["여행"]:
            st.caption("모임·팀원 관리 탭에서 여행 팀원을 먼저 등록해 주세요")

        if st.button("추가", type="primary", width="stretch", key="add_expense_3"):
            add_expense("여행", kind, date, item, amount, payer)

    # 결과 자리
    with center:
        expense_list("여행")

# 탭 3 : 모임·팀원 관리 (가끔 쓰는 등록·삭제)
with tab_manage:
    c1, c2, c3 = st.columns(3)
    with c1:
        group_section()
    for column, book in zip((c2, c3), BOOKS):
        with column:
            member_section(book)

    st.divider()
    st.subheader("잘못 입력한 지출 삭제")
    delete_book = st.radio("장부", BOOKS, format_func=lambda b: LIST_TITLE[b], horizontal=True, key="delete_book")
    expense_delete_form(delete_book)
