import streamlit as st

# 첫 화면 색 : 배경 · 글자 · 강조 (기능 화면에는 쓰지 않음)
BACKGROUND = "#FFF8F0"
TEXT = "#1F2A44"
ACCENT = "#0B7A7A"

# PRD.md 한 줄 정의
INTRO = "여행모임 총무가 팀원 카드로 낸 지출을 표시하면, 그 사람에게 돌려줄 금액이 자동으로 나와서 손으로 계산하지 않아도 돼요"

# PRD.md 넣을 기능 1~3
FEATURES = [
    ("📝", "지출을 한 곳에 모아요", "지출마다 날짜·항목·금액·낸 사람(카드)을 입력하면, 나중에 계산기로 다시 계산할 필요 없이 한 곳에 모여요"),
    ("🧳", "예약부터 현장까지 한 번에", "여행 전 예약 비용과 여행 중 경비를 같은 화면에 함께 입력해, 여행 시작부터 끝까지 지출을 몰아볼 수 있어요"),
    ("💸", "돌려줄 금액이 자동으로", "총무가 아닌 팀원 카드로 낸 지출을 표시하면, 그 팀원에게 돌려줄 금액이 자동으로 나와요"),
]

STYLE = f"""<style>
[data-testid="stAppViewContainer"], [data-testid="stHeader"] {{ background: {BACKGROUND}; }}
[data-testid="stAppViewContainer"] * {{ color: {TEXT}; }}
.landing-title {{ text-align: center; font-size: 3.5rem; font-weight: 800; margin: 3rem 0 0.5rem; }}
.landing-intro {{ text-align: center; font-size: 1.2rem; margin-bottom: 2.5rem; }}
.landing-card {{ height: 100%; padding: 1.5rem; border: 2px solid {ACCENT}; border-radius: 1rem; background: rgba(255, 255, 255, 0.35); }}
.landing-card h3 {{ margin: 0.5rem 0; font-size: 1.2rem; }}
.landing-icon {{ font-size: 2rem; }}
.st-key-start {{ margin-top: 2.5rem; }}
.st-key-start button {{ background: {ACCENT}; border-color: {ACCENT}; }}
.st-key-start button, .st-key-start button * {{ color: #ffffff; font-size: 1.2rem; font-weight: 700; }}
</style>"""


def go_to_app():
    st.session_state.page = "app"


def landing():
    # 서비스 소개 첫 화면 : 큰 제목 · 한 줄 소개 · 하는 일 세 가지 · 시작하기 버튼
    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown('<div class="landing-title">💰 총무노트</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="landing-intro">{INTRO}</div>', unsafe_allow_html=True)

    for column, (icon, title, text) in zip(st.columns(3), FEATURES):
        column.markdown(
            f'<div class="landing-card"><div class="landing-icon">{icon}</div><h3>{title}</h3><p>{text}</p></div>',
            unsafe_allow_html=True,
        )

    _, center, _ = st.columns([2, 1, 2])
    center.button("시작하기", width="stretch", key="start", on_click=go_to_app)
