import base64
import json
import os
from io import BytesIO
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google import genai
from PIL import Image
from supabase import create_client

# helper.py 와 같은 방식 : .env 의 GEMINI_API_KEY 로 Gemini 를 부름
load_dotenv()

# .env 의 SUPABASE_URL, SUPABASE_KEY 로 Supabase 에 연결
# chat_logs 표 : id, created_at, tone, question, answer
CHAT_TABLE = "chat_logs"
HISTORY_LIMIT = 20

# 공식 문서(ai.google.dev/gemini-api/docs/quickstart, text-generation) 기준
# 모델 이름 · client.interactions.create · system_instruction · previous_interaction_id
MODEL = "gemini-3.8-flash"

PRD_PATH = Path(__file__).parent / "PRD.md"

# AI 에게 주는 고정 지시문 (my_service 폴더 맨 위의 chatbot_prompt.txt)
PROMPT_PATH = Path(__file__).parent / "chatbot_prompt.txt"

# 챗봇 캐릭터 그림 (my_service 폴더 맨 위의 bot.png)
BOT_IMAGE = Path(__file__).parent / "bot.png"

GREETING = "안녕하세요! 이 서비스에 대해 궁금한 걸 물어보세요"

# 답 점검 : 정확히 세 줄 · 300자 이하가 아니면 한 번 더 묻고, 두 번 다 벗어나면 RETRY_MESSAGE 를 띄움
# UNSURE_PREFIX 로 시작하는 답은 점검 없이 통과
ANSWER_LINES = 3
ANSWER_MAX_CHARS = 300
UNSURE_PREFIX = "[확실하지 않은 내용이에요]"
RETRY_MESSAGE = "다시 시도해 주세요"

# 대화창에서 고르는 말투 : 화면에 보이는 이름 → AI 에게 주는 말투 지시
TONES = {
    "친절하게": "부드럽고 친절한 존댓말(~해요)로 답해.",
    "간단하게": "꾸밈말 없이 핵심만 담은 짧은 존댓말(~해요)로 답해.",
    "다정하게": "옆에서 도와주는 친구처럼 다정하고 따뜻한 존댓말(~해요)로 답해.",
    "격식 있게": "공손한 격식체 존댓말(~합니다, ~하십시오)로 답해.",
}


@st.cache_data
def bot_image_png():
    # 원본(1254px)이 커서 화면에 쓸 때만 256px 로 줄임
    image = Image.open(BOT_IMAGE)
    image.thumbnail((256, 256))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@st.cache_data
def bot_image_data():
    return base64.b64encode(bot_image_png()).decode()


@st.cache_data
def load_prd():
    return PRD_PATH.read_text(encoding="utf-8-sig")


@st.cache_data
def load_prompt():
    return PROMPT_PATH.read_text(encoding="utf-8-sig").strip()


def system_instruction():
    return (
        load_prompt() + "\n\n"
        + tone_instruction() + "\n\n"
        "<PRD>\n" + load_prd() + "\n</PRD>"
    )


def tone_instruction():
    # 대화창에서 고른 말투 (말투만 바꾸고, 세 문장 규칙과 하지 않을 것은 그대로)
    tone = st.session_state.get("chat_tone", "친절하게")
    return (
        "[말투]\n"
        f"사용자가 고른 말투는 \"{tone}\"이야. {TONES[tone]}\n"
        "말투는 [역할]에 적힌 말투보다 이 칸을 따르되, [형식]의 세 문장 규칙과 [하지 않을 것]은 그대로 지켜."
    )


@st.cache_resource
def supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def save_log(question, answer):
    # 물은 말과 받은 답을 chat_logs 표에 한 줄로 남김 (저장이 안 돼도 대화는 이어감)
    try:
        supabase().table(CHAT_TABLE).insert(
            {"tone": st.session_state.chat_tone, "question": question, "answer": answer}
        ).execute()
    except Exception as e:
        st.session_state.chat_save_error = f"대화를 Supabase 에 남기지 못했어요 : {e}"


def load_logs():
    # 최신 대화가 위로 오게 불러오기
    try:
        return (
            supabase()
            .table(CHAT_TABLE)
            .select("tone, question, answer, created_at")
            .order("created_at", desc=True)
            .limit(HISTORY_LIMIT)
            .execute()
            .data
        )
    except Exception as e:
        st.caption(f"지난 대화를 불러오지 못했어요 : {e}")
        return []


def answer_ok(text):
    # 화면에 보여줘도 되는 답인지 점검
    text = text.strip()
    if text.startswith(UNSURE_PREFIX):
        return True
    lines = text.split("\n")
    return len(lines) == ANSWER_LINES and all(line.strip() for line in lines) and len(text) <= ANSWER_MAX_CHARS


def ask(question):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "GEMINI_API_KEY 가 비어 있어서 답할 수 없어요. .env 에 값을 넣어주세요"
    try:
        client = genai.Client(api_key=api_key)
        options = {}
        # 이전 대화를 이어가도록 직전 답의 id 를 넘김
        if st.session_state.chat_last_id:
            options["previous_interaction_id"] = st.session_state.chat_last_id
        # 점검을 못 넘으면 같은 질문을 한 번 더 물음 (못 넘은 답은 대화에 이어 붙이지 않음)
        for _ in range(2):
            interaction = client.interactions.create(
                model=MODEL,
                system_instruction=system_instruction(),
                input=question,
                **options,
            )
            if answer_ok(interaction.output_text):
                break
        else:
            return RETRY_MESSAGE
    except Exception as e:
        return f"Gemini 에서 답을 받지 못했어요 : {e}"
    st.session_state.chat_last_id = interaction.id
    # AI 가 제대로 답했을 때만 남김 (키가 비었거나 오류 난 안내 문구는 남기지 않음)
    save_log(question, interaction.output_text)
    return interaction.output_text


def toggle():
    st.session_state.chat_open = not st.session_state.chat_open


def style():
    dark = st.context.theme.type == "dark"
    panel_bg = "#1f2229" if dark else "#ffffff"
    border = "#3a3f4b" if dark else "#e3e6ec"
    # 대화창이 닫혀 있을 때는 단추를 캐릭터 그림으로 보여줌 (열리면 ✕ 단추)
    closed_icon = ""
    if not st.session_state.chat_open:
        closed_icon = f"""
        .st-key-chat_fab button, .st-key-chat_fab button:hover {{
            width: 88px; height: 88px; border-radius: 0; font-size: 0;
            background: url("data:image/png;base64,{bot_image_data()}") center / contain no-repeat;
            box-shadow: none; filter: drop-shadow(0 4px 10px rgba(0, 0, 0, .3));
        }}
        """
    st.html(
        f"""
        <style>
        .st-key-chat_fab {{
            position: fixed; right: 24px; bottom: 24px; z-index: 1000;
            width: auto !important;
        }}
        .st-key-chat_fab button {{
            width: 64px; height: 64px; border-radius: 50%;
            font-size: 30px; line-height: 1; padding: 0;
            background: #ffd54f; border: none; color: #3b2f00;
            box-shadow: 0 6px 18px rgba(0, 0, 0, .25);
            transition: transform .15s;
        }}
        .st-key-chat_fab button:hover {{ transform: scale(1.08); background: #ffca28; }}
        {closed_icon}
        .st-key-chat_panel {{
            position: fixed; right: 24px; bottom: 100px; z-index: 1000;
            width: min(380px, calc(100vw - 32px)) !important;
            max-height: 70vh; overflow-y: auto;
            padding: 16px; border-radius: 16px;
            background: {panel_bg}; border: 1px solid {border};
            box-shadow: 0 10px 30px rgba(0, 0, 0, .25);
        }}
        @media (max-width: 480px) {{
            .st-key-chat_panel {{ right: 16px; }}
            .st-key-chat_fab {{ right: 16px; }}
        }}
        </style>
        """
    )


def copy_button(text):
    # AI 답 전체를 한 번에 클립보드로 복사하는 작은 단추
    dark = st.context.theme.type == "dark"
    color = "#c9ccd3" if dark else "#555b66"
    border = "#3a3f4b" if dark else "#d5d9e0"
    hover = "#2a2e37" if dark else "#f1f3f6"
    # 답 글자는 JS 문자열로만 넣고 < 를 모두 바꿔서, 답 내용이 HTML 로 실행되지 않게 함
    payload = json.dumps(text).replace("<", "\\u003c")
    st.iframe(
        f"""
        <button id="copy">📋 복사</button>
        <style>
        body {{ margin: 0; font-family: sans-serif; }}
        #copy {{
            font-size: 12px; padding: 3px 10px; cursor: pointer;
            color: {color}; background: transparent;
            border: 1px solid {border}; border-radius: 999px;
        }}
        #copy:hover {{ background: {hover}; }}
        </style>
        <script>
        const text = {payload};
        const btn = document.getElementById("copy");
        btn.onclick = async () => {{
            try {{
                await navigator.clipboard.writeText(text);
                btn.textContent = "✓ 복사했어요";
            }} catch (e) {{
                btn.textContent = "복사하지 못했어요";
            }}
            setTimeout(() => (btn.textContent = "📋 복사"), 1500);
        }};
        </script>
        """,
        height=30,
    )


def chat_panel():
    with st.container(key="chat_panel"):
        st.markdown("**서비스 도우미**")
        st.caption("PRD.md 를 읽고 답해요")
        # 말투 고르는 칸 : 고른 말투는 다음 질문부터 적용됨
        st.radio("말투", list(TONES), horizontal=True, key="chat_tone")

        with st.chat_message("assistant", avatar=bot_image_png()):
            st.write(GREETING)
        for msg in st.session_state.chat_messages:
            avatar = bot_image_png() if msg["role"] == "assistant" else None
            with st.chat_message(msg["role"], avatar=avatar):
                # 마크다운은 줄바꿈 하나를 무시하므로, 문장마다 줄이 바뀌어 보이게 바꿔서 보여줌
                st.write(msg["text"].replace("\n", "  \n"))
                if msg["role"] == "assistant":
                    copy_button(msg["text"])

        with st.form("chat_form", clear_on_submit=True, border=False):
            question = st.text_input(
                "물어볼 말", placeholder="예: 돌려줄 금액은 어떻게 계산돼요?", label_visibility="collapsed"
            )
            sent = st.form_submit_button("보내기", width="stretch")

        if sent and question.strip():
            question = question.strip()
            st.session_state.chat_messages.append({"role": "user", "text": question})
            with st.spinner("답을 쓰는 중이에요"):
                answer = ask(question)
            st.session_state.chat_messages.append({"role": "assistant", "text": answer})
            st.rerun()

        # 저장하지 못한 이유는 다시 그린 뒤에 한 번만 보여줌
        if st.session_state.get("chat_save_error"):
            st.error(st.session_state.pop("chat_save_error"))

        history()


def history():
    # 대화창 아래 : chat_logs 표에 남은 지난 대화 목록
    with st.expander("지난 대화"):
        logs = load_logs()
        if not logs:
            st.write("아직 남긴 대화가 없어요")
        for log in logs:
            st.caption(f"{log['created_at'][:16].replace('T', ' ')} · {log['tone'] or '-'}")
            st.markdown("**물은 말**")
            st.text(log["question"])
            st.markdown("**받은 답**")
            st.text(log["answer"])
            st.divider()


def chatbot():
    # 화면 오른쪽 아래 챗봇 아이콘 : 누르면 대화창이 열리고 닫힘
    st.session_state.setdefault("chat_open", False)
    st.session_state.setdefault("chat_messages", [])
    st.session_state.setdefault("chat_last_id", None)
    # 대화창이 닫혀 있어도 고른 말투가 지워지지 않게 매번 다시 넣어 둠
    st.session_state.chat_tone = st.session_state.get("chat_tone", "친절하게")

    style()
    with st.container(key="chat_fab"):
        st.button(
            "✕" if st.session_state.chat_open else "챗봇 열기",
            on_click=toggle,
            help="대화창 닫기" if st.session_state.chat_open else "서비스 도우미에게 물어보기",
        )
    if st.session_state.chat_open:
        chat_panel()
