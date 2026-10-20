# 화면 훅 block-lorem (PreToolUse, Write|Edit)
# - 대상: .html 화면 파일만 본다. 다른 파일(.md 문서 등)은 그대로 통과시킨다.
# - 검사 1 (안내 문구): "지출 입력"이 들어 있는 화면 1 파일이면, 고친 뒤의 파일 전체에
#   message.md 의 안내 문구가 한 글자도 틀리지 않고 들어 있는지 본다.
# - 검사 2 (비목표): 고친 뒤의 파일 전체에 scope.md(PRD.md 비목표) 기능 글자가 들어 있는지 본다.
# - 검사 0 (lorem): 고친 뒤의 파일 전체에 "lorem"(대소문자 무관) 이 들어 있는지 본다.
# - 막을 때: 맨 앞 경고창을 따로 띄우고, AI에게 deny 와 이유를 돌려보낸다.
import json
import os
import subprocess
import sys

LOREM_TITLE = "lorem 훅"
LOREM_TEXT = "[화면에 Lorem ipsum 자리채움 글은 넣지 않아요]"
LOREM_REASON = "Lorem ipsum 자리채움 글이 들어 있어요. 실제 화면 문구로 바꾸세요"

TITLE = "안내 문구 훅"
TEXT = "[화면 1에 안내 문구가 빠졌거나 바뀌었어요]"
REASON = "안내 문구가 빠졌거나 바뀌었어요. .claude/rules/message.md 문구를 그대로 넣으세요"

SCREEN1_MARK = "지출 입력"
REQUIRED = "등록된 팀원 중에 없는 이름이에요. 목록에서 골라주세요"

NONGOAL_TITLE = "비목표 훅"
NONGOAL_TEXT = "[비목표 기능은 넣지 않아요]"
NONGOAL_REASON = "PRD.md 비목표 기능({words})이 들어 있어요. .claude/rules/scope.md 대로 빼세요"

# PRD.md 비목표 기능을 가리키는 글자 (계좌번호 자동 기억 / 단톡방 메시지 생성 / 영수증 사진 인식 / 인당 금액 자동계산)
NONGOAL_WORDS = ["계좌번호", "입금해주세요", "영수증", "인당"]

# 이 스크립트 위치(.claude/hooks/)에서 두 단계 위가 프로젝트 폴더
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read_file(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read()
    except Exception:
        return None


def content_after(tool_name, tool_input, path):
    # 쓰기·고치기가 끝난 뒤 파일 내용을 미리 만들어 본다
    if tool_name == "Write":
        return tool_input.get("content") or ""
    current = read_file(path)
    if current is None:
        return None
    old = tool_input.get("old_string") or ""
    new = tool_input.get("new_string") or ""
    if not old or old not in current:
        return None  # Edit 자체가 실패할 것이니 판단하지 않는다
    if tool_input.get("replace_all"):
        return current.replace(old, new)
    return current.replace(old, new, 1)


def show_popup(title, text):
    # MB_ICONWARNING | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
    flags = 0x30 | 0x1000 | 0x10000 | 0x40000
    # 창을 띄우기 직전에 Windows 경고(느낌표) 소리를 한 번 낸다
    code = (
        "import ctypes, winsound;"
        "winsound.MessageBeep(winsound.MB_ICONEXCLAMATION);"
        f"ctypes.windll.user32.MessageBoxW(None, {text!r}, {title!r}, {flags})"
    )
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    # 별도 프로세스로 띄워서 확인 버튼을 기다리지 않고 훅은 바로 끝난다
    subprocess.Popen(
        [exe, "-c", code],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return
    tool_name = data.get("tool_name") or ""
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if tool_name not in ("Write", "Edit") or not file_path.lower().endswith(".html"):
        return

    path = os.path.abspath(os.path.join(PROJECT_DIR, file_path))
    after = content_after(tool_name, tool_input, path)
    if after is None:
        return

    found = [w for w in NONGOAL_WORDS if w in after]
    if "lorem" in after.lower():
        title, text, reason = LOREM_TITLE, LOREM_TEXT, LOREM_REASON
    elif found:
        title, text, reason = NONGOAL_TITLE, NONGOAL_TEXT, NONGOAL_REASON.format(words=", ".join(found))
    elif SCREEN1_MARK in after and REQUIRED not in after:
        title, text, reason = TITLE, TEXT, REASON
    else:
        return

    try:
        show_popup(title, text)
    except Exception:
        pass  # 경고창이 실패해도 차단은 반드시 한다

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
