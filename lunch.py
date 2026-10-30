import math

import altair as alt
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

from keys import get_key

st.set_page_config(page_title="맛집 대시보드", layout="wide")

# .env(내 컴퓨터) 또는 Secrets(올린 곳) 의 KAKAO_REST_API_KEY 로 카카오 로컬 API 를 부름

# 카카오 로컬 API (공식 문서: https://developers.kakao.com/docs/latest/ko/local/dev-guide)
# 인증 헤더는 "Authorization: KakaoAK {REST API 키}"
ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"
FOOD_CODE = "FD6"  # 카테고리 그룹 코드 : 음식점
PAGE_SIZE = 15  # size 는 1~15
MAX_PAGES = 3  # 한 번 검색에 최대 45곳 (15곳 x 3쪽)

# 주소 검색 결과의 address_type 을 화면에 보여 줄 이름
ADDRESS_TYPE = {"REGION": "지명(동네)", "ROAD": "도로명", "REGION_ADDR": "지번 주소", "ROAD_ADDR": "도로명 주소"}

# 찾을 음식 : "전체" 는 음식점 전체, "직접 입력" 은 아래 칸에 쓴 음식으로 찾음
FOOD_CHOICES = ["전체", "한식", "중식", "일식", "양식", "분식", "국밥", "고기", "치킨", "직접 입력"]

# 차트 막대 색 (한 계열이라 한 색만 씀)
BAR_COLOR = "#2a78d6"

# 지도 점 색 (RGB) : 가게는 차트와 같은 파랑, 기준 장소는 회색, 뽑힌 곳은 주황
SHOP_RGB = [42, 120, 214]
CENTER_RGB = [90, 90, 90]
PICK_RGB = [235, 110, 30]


def kakao_get(url, params):
    key = get_key("KAKAO_REST_API_KEY")
    if not key:
        raise RuntimeError(".env 또는 Secrets 에 KAKAO_REST_API_KEY 가 없어요. 키를 넣고 다시 실행해 주세요.")
    res = requests.get(url, headers={"Authorization": f"KakaoAK {key}"}, params=params, timeout=10)
    if res.status_code == 401:
        raise RuntimeError("카카오 REST API 키가 맞지 않아요. .env 또는 Secrets 의 KAKAO_REST_API_KEY 를 확인해 주세요.")
    if res.status_code == 403:
        raise RuntimeError("카카오맵(로컬) API 사용 권한이 없어요. 카카오 디벨로퍼스 앱 설정에서 카카오맵을 켜 주세요.")
    res.raise_for_status()
    return res.json()


def find_center(place):
    # 동네 이름(예: 영등동)이나 주소는 주소 검색으로 찾고, 없으면 역·건물 이름(예: 익산역)으로 보고 키워드 검색으로 찾음
    # 이름·주소·종류는 카카오가 돌려준 값만 그대로 씀 (좌표 x=경도, y=위도)
    data = kakao_get(ADDRESS_URL, {"query": place, "size": 1})
    if data["documents"]:
        doc = data["documents"][0]
        return {
            "name": doc["address_name"].split()[-1],
            "address": doc["address_name"],
            "kind": ADDRESS_TYPE.get(doc["address_type"], doc["address_type"]),
            "x": doc["x"],
            "y": doc["y"],
        }

    data = kakao_get(KEYWORD_URL, {"query": place, "size": 1})
    if not data["documents"]:
        raise RuntimeError(f"'{place}' 위치를 찾지 못했어요. 역·동네 이름을 바꿔 보세요.")
    doc = data["documents"][0]
    return {
        "name": doc["place_name"],
        "address": doc["road_address_name"] or doc["address_name"],
        "kind": doc["category_name"],
        "x": doc["x"],
        "y": doc["y"],
    }


def search_food(x, y, radius, keyword):
    # 검색어가 있으면 키워드 검색(음식점만), 없으면 카테고리 검색으로 반경 안 음식점 전체를 가까운 순으로 가져옴
    params = {
        "category_group_code": FOOD_CODE,
        "x": x,
        "y": y,
        "radius": radius,
        "sort": "distance",
        "size": PAGE_SIZE,
    }
    url = CATEGORY_URL
    if keyword:
        url = KEYWORD_URL
        params["query"] = keyword

    places = []
    total = 0
    for page in range(1, MAX_PAGES + 1):
        data = kakao_get(url, {**params, "page": page})
        places += data["documents"]
        total = data["meta"]["total_count"]
        if data["meta"]["is_end"]:
            break
    return places, total


def to_table(places):
    rows = []
    for p in places:
        # category_name 예 : "음식점 > 한식 > 비빔밥" → 분류 "한식", 세부 "비빔밥"
        parts = [s.strip() for s in p["category_name"].split(">")]
        rows.append(
            {
                "이름": p["place_name"],
                "분류": parts[1] if len(parts) > 1 else "기타",
                "세부": parts[-1] if len(parts) > 2 else "",
                "거리(m)": int(p["distance"]) if p.get("distance") else None,
                "주소": p["road_address_name"] or p["address_name"],
                "전화": p["phone"],
                "카카오맵": p["place_url"],
                # 지도에만 쓰고 표에서는 숨김
                "위도": float(p["y"]),
                "경도": float(p["x"]),
            }
        )
    return pd.DataFrame(rows)


st.title("근처 맛집 찾기")

# ---------- 내 조건 (검색 버튼을 눌렀을 때만 API 를 부름) ----------
with st.form("search"):
    c1, c2, c3 = st.columns([2, 2, 2])
    center_name = c1.text_input("기준 장소 (역·동네 이름)", value="익산역", placeholder="예: 익산역, 영등동")
    food_choice = c2.selectbox("찾을 음식", FOOD_CHOICES)
    food_text = c2.text_input("직접 입력 ('직접 입력' 을 골랐을 때)", placeholder="예: 짬뽕, 칼국수")
    radius = c3.slider("반경 (m)", min_value=100, max_value=5000, value=500, step=100)
    submitted = st.form_submit_button("검색", type="primary")

if submitted:
    keyword = food_text.strip() if food_choice == "직접 입력" else ("" if food_choice == "전체" else food_choice)
    if not center_name.strip():
        st.error("기준 장소를 넣어 주세요.")
    elif food_choice == "직접 입력" and not keyword:
        st.error("찾을 음식을 직접 입력 칸에 써 주세요.")
    else:
        try:
            with st.spinner("카카오에서 음식점을 찾는 중..."):
                center = find_center(center_name.strip())
                places, total = search_food(center["x"], center["y"], radius, keyword)
            st.session_state["lunch"] = {
                "df": to_table(places),
                "total": total,
                "query": center_name.strip(),
                "center": center["name"],
                "center_address": center["address"],
                "center_kind": center["kind"],
                "center_lat": float(center["y"]),
                "center_lon": float(center["x"]),
                "radius": radius,
                "keyword": keyword,
            }
            # 새로 검색하면 지난 뽑기 결과는 지움
            st.session_state.pop("lunch_pick", None)
        except RuntimeError as e:
            st.error(str(e))
        except requests.RequestException as e:
            st.error(f"카카오 API 를 부르지 못했어요: {e}")

result = st.session_state.get("lunch")
if not result:
    st.info("조건을 정하고 [검색] 을 눌러 주세요.")
    st.stop()

df = result["df"]
# 기준 장소로 카카오에서 실제로 찾은 이름·주소·종류 (지도를 붙이기 전 결과에는 주소가 없을 수 있음)
with st.container(border=True):
    if "query" in result:
        st.caption(f"입력한 기준 장소: {result['query']}")
    st.markdown(f"**찾은 기준 장소** {result['center']}")
    if result.get("center_address"):
        st.markdown(f"**주소** {result['center_address']}  \n**종류** {result['center_kind']}")
    st.caption(f"반경 {result['radius']:,}m · 찾을 음식: {result['keyword'] or '전체'}")
    st.caption("원하던 곳이 아니면 '익산 영등동' 처럼 시·구 이름을 같이 넣어 다시 검색해 보세요.")

if df.empty:
    st.warning("조건에 맞는 음식점이 없어요. 반경을 넓히거나 검색어를 바꿔 보세요.")
    st.stop()

# ---------- 요약 ----------
m1, m2, m3 = st.columns(3)
m1.metric("가져온 음식점", f"{len(df)}곳", help=f"카카오 검색 결과 전체 {result['total']}곳 중 가까운 순 최대 45곳")
m2.metric("가장 가까운 곳", f"{df['거리(m)'].min():,}m")
m3.metric("가장 많은 분류", df["분류"].value_counts().idxmax())

# ---------- 결과 안에서 거르기·정렬 ----------
f1, f2, f3, f4 = st.columns([2, 3, 2, 1])
name_filter = f1.text_input("이름으로 거르기")
categories = sorted(df["분류"].unique())
picked = f2.multiselect("분류", categories, default=categories)
sort_col = f3.selectbox("정렬 기준", ["거리(m)", "이름", "분류"])
ascending = f4.radio("순서", ["오름차순", "내림차순"]) == "오름차순"

view = df[df["분류"].isin(picked)]
if name_filter:
    view = view[view["이름"].str.contains(name_filter, case=False, regex=False)]
view = view.sort_values(sort_col, ascending=ascending).reset_index(drop=True)

# ---------- 맛집 뽑기 (카카오를 다시 부르지 않고 지금 표에 보이는 가게 안에서 한 곳을 고름) ----------
if st.button("맛집 뽑기", disabled=view.empty):
    st.session_state["lunch_pick"] = view.sample(1).iloc[0].to_dict()

pick = st.session_state.get("lunch_pick")
if pick:
    kind = f"{pick['분류']} · {pick['세부']}" if pick["세부"] else pick["분류"]
    with st.container(border=True):
        st.caption("오늘은 여기!")
        st.markdown(f"# {pick['이름']}")
        p1, p2 = st.columns(2)
        p1.metric("종류", kind)
        p2.metric("거리", f"{int(pick['거리(m)']):,}m")

# ---------- 차트 ----------
ch1, ch2 = st.columns(2)

with ch1:
    st.subheader("분류별 음식점 수")
    counts = view["분류"].value_counts().rename_axis("분류").reset_index(name="곳 수")
    chart = (
        alt.Chart(counts)
        .mark_bar(color=BAR_COLOR, cornerRadiusEnd=4)
        .encode(
            x=alt.X("곳 수:Q", title="곳 수", axis=alt.Axis(tickMinStep=1)),
            y=alt.Y("분류:N", sort="-x", title=None),
            tooltip=["분류", "곳 수"],
        )
    )
    st.altair_chart(chart, width="stretch")

with ch2:
    st.subheader("가까운 곳 10")
    nearest = view.nsmallest(10, "거리(m)")
    chart = (
        alt.Chart(nearest)
        .mark_bar(color=BAR_COLOR, cornerRadiusEnd=4)
        .encode(
            x=alt.X("거리(m):Q", title="거리 (m)"),
            y=alt.Y("이름:N", sort="x", title=None),
            tooltip=["이름", "분류", "세부", "거리(m)"],
        )
    )
    st.altair_chart(chart, width="stretch")

# ---------- 지도 (지금 표에 보이는 가게 + 기준 장소 + 뽑힌 곳) ----------
st.subheader("지도")
if "center_lat" not in result:
    # 지도를 붙이기 전에 받아 둔 결과에는 좌표가 없음
    st.info("지도를 보려면 [검색] 을 한 번 더 눌러 주세요.")
else:
    shops = pd.DataFrame(
        {
            "lat": view["위도"],
            "lon": view["경도"],
            "label": view["이름"] + "\n" + view["분류"] + " · " + view["거리(m)"].map(lambda d: f"{int(d):,}m"),
        }
    )
    center = pd.DataFrame(
        [{"lat": result["center_lat"], "lon": result["center_lon"], "label": f"기준: {result['center']}"}]
    )
    layers = [
        pdk.Layer("ScatterplotLayer", shops, get_position="[lon, lat]", get_fill_color=SHOP_RGB,
                  get_radius=12, radius_min_pixels=5, pickable=True),
        pdk.Layer("ScatterplotLayer", center, get_position="[lon, lat]", get_fill_color=CENTER_RGB,
                  get_radius=20, radius_min_pixels=8, pickable=True),
    ]
    if pick and "위도" in pick:
        picked_point = pd.DataFrame([{"lat": pick["위도"], "lon": pick["경도"], "label": f"뽑힌 곳: {pick['이름']}"}])
        layers.append(
            pdk.Layer("ScatterplotLayer", picked_point, get_position="[lon, lat]", get_fill_color=PICK_RGB,
                      get_radius=20, radius_min_pixels=10, stroked=True, get_line_color=[255, 255, 255],
                      line_width_min_pixels=2, pickable=True)
        )
    # 반경 500m 일 때 15 쯤, 반경이 두 배가 될 때마다 한 단계씩 멀리 봄
    zoom = 16 - math.log2(result["radius"] / 250)
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(latitude=result["center_lat"], longitude=result["center_lon"], zoom=zoom),
            tooltip={"text": "{label}"},
            map_style=None,
        ),
        height=450,
    )
    st.caption(":blue[●] 가게 · :gray[●] 기준 장소 · :orange[●] 뽑힌 곳 — 점에 마우스를 올리면 이름이 나와요")

# ---------- 표 ----------
st.subheader(f"음식점 목록 ({len(view)}곳)")
st.dataframe(
    view.drop(columns=["위도", "경도"], errors="ignore"),
    width="stretch",
    hide_index=True,
    column_config={
        "거리(m)": st.column_config.NumberColumn(format="%d m"),
        "카카오맵": st.column_config.LinkColumn(display_text="열기"),
    },
)
