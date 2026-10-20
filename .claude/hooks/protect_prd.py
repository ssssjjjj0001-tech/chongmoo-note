# PRD.md 자물쇠 훅 (PreToolUse, Write|Edit|Bash|PowerShell)
# - 대상 파일이 프로젝트 맨 위의 PRD.md 일 때만 막는다. 다른 파일은 그대로 통과시킨다.
# - Bash/PowerShell 명령은 PRD.md 를 바꾸는 명령(덮어쓰기·붙이기·지우기·옮기기 등)만 막고,
#   읽기만 하는 명령(cat, head, Get-Content 등)은 통과시킨다.
# - 막을 때: 맨 앞 경고창을 따로 띄우고, AI에게 deny 와 이유를 돌려보낸다.
import json
import os
import re
import subprocess
import sys

TITLE = "PRD 자물쇠"
TEXT = "[기획서는 직접 고쳐 주세요]"
REASON = "PRD.md 는 잠겨 있으니 고치지 말고 바꿀 내용을 제안만 하라"

# 이 스크립트 위치(.claude/hooks/)에서 두 단계 위가 프로젝트 폴더
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRD_PATH = os.path.normcase(os.path.join(PROJECT_DIR, "PRD.md"))

# 명령 안에서 PRD.md 로 끝나는 경로 조각
PRD_TOKEN = r"""["']?[^\s"';|&<>()]*PRD\.md["']?"""

# 명령을 조각으로 나누는 기준: 파이프, ;, &&, ||, 줄바꿈
SEGMENT_SPLIT = re.compile(r"\|\||&&|[|;\n]")

# 조각 안에 PRD.md 가 있으면 바꾸는 명령으로 보는 것들
WRITE_PATTERNS = [
    # 리다이렉트로 덮어쓰기/붙이기: > PRD.md, >> PRD.md, 2> PRD.md
    re.compile(r"(?:\d|&)?>>?\|?\s*" + PRD_TOKEN, re.I),
    # tee / Tee-Object 로 쓰기
    re.compile(r"\b(?:tee|tee-object)\b[^|;&\n]*" + PRD_TOKEN, re.I),
    # 그 자리에서 고치기: sed -i, perl -i 등
    re.compile(r"\b(?:sed|perl|ruby)\b[^|;&\n]*\s-[a-z]*i", re.I),
    # 지우기·옮기기·이름 바꾸기·만들기·비우기 (bash)
    re.compile(r"^\s*(?:sudo\s+)?(?:rm|mv|truncate|dd|touch|unlink|shred|ln|install)\b", re.I),
    # 지우기·옮기기·쓰기 (PowerShell cmdlet 과 별칭)
    re.compile(
        r"\b(?:set-content|add-content|out-file|clear-content|remove-item|move-item|"
        r"rename-item|new-item|set-item|clear-item)\b",
        re.I,
    ),
    re.compile(r"^\s*(?:sc|ac|ri|del|erase|rd|rmdir|move|mi|ren|rni|ni)\b", re.I),
    # .NET 으로 파일 쓰기/지우기/옮기기
    re.compile(
        r"(?:WriteAllText|WriteAllLines|WriteAllBytes|AppendAllText|AppendAllLines|"
        r"File\]::(?:Delete|Move|Copy|Replace|Create|Open|AppendText|CreateText))",
        re.I,
    ),
    # python/node 등 스크립트 안에서 쓰기
    re.compile(r"\b(?:write|writeFile|writeFileSync|appendFile|appendFileSync|unlink|remove|rename)\s*\(", re.I),
    re.compile(r"""open\s*\([^)]*,\s*["'][^"']*[wax+]""", re.I),
]

# 복사는 PRD.md 가 목적지(마지막 인자 또는 -Destination)일 때만 막는다
COPY_CMD = re.compile(r"^\s*(?:sudo\s+)?(?:cp|copy|cpi|copy-item)\b", re.I)
COPY_DEST = re.compile(r"-destination\s+" + PRD_TOKEN, re.I)

CD_CMD = re.compile(r"""^\s*(?:cd|pushd|set-location|sl|chdir)\s+(?:-path\s+|-literalpath\s+)?["']?([^"';|&]+?)["']?\s*$""", re.I)


def to_native(path):
    # Git Bash 형식(/c/Users/...)을 Windows 형식(C:/Users/...)으로 바꾼다
    m = re.match(r"^/([a-zA-Z])(/.*)?$", path)
    if m:
        return m.group(1) + ":" + (m.group(2) or "/")
    return path


def resolve(path, cwd):
    path = to_native(os.path.expanduser(path.strip("\"'")))
    return os.path.normcase(os.path.abspath(os.path.join(cwd, path)))


def is_prd(token, cwd):
    token = token.strip("\"'")
    # 변수가 들어간 경로는 어디를 가리키는지 알 수 없으니 PRD.md 로 본다
    if "$" in token or "%" in token:
        return True
    return resolve(token, cwd) == PRD_PATH


def command_changes_prd(command, cwd):
    cwd = to_native(cwd or PROJECT_DIR)
    for segment in SEGMENT_SPLIT.split(command):
        cd = CD_CMD.match(segment)
        if cd:
            cwd = resolve(cd.group(1), cwd)
            continue
        tokens = re.findall(PRD_TOKEN, segment, re.I)
        if not any(is_prd(t, cwd) for t in tokens):
            continue
        if COPY_CMD.match(segment):
            words = segment.split()
            if COPY_DEST.search(segment) or (words and re.fullmatch(PRD_TOKEN, words[-1], re.I) and is_prd(words[-1], cwd)):
                return True
            continue
        if any(p.search(segment) for p in WRITE_PATTERNS):
            return True
    return False


def show_popup():
    # MB_ICONWARNING | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
    flags = 0x30 | 0x1000 | 0x10000 | 0x40000
    # 창을 띄우기 직전에 Windows 경고(느낌표) 소리를 한 번 낸다
    code = (
        "import ctypes, winsound;"
        "winsound.MessageBeep(winsound.MB_ICONEXCLAMATION);"
        f"ctypes.windll.user32.MessageBoxW(None, {TEXT!r}, {TITLE!r}, {flags})"
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
    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command") or ""
    file_path = tool_input.get("file_path") or ""

    if command:
        if not command_changes_prd(command, data.get("cwd") or PROJECT_DIR):
            return
    elif file_path:
        target = os.path.normcase(os.path.abspath(os.path.join(PROJECT_DIR, file_path)))
        if target != PRD_PATH:
            return
    else:
        return

    try:
        show_popup()
    except Exception:
        pass  # 경고창이 실패해도 차단은 반드시 한다

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }
    sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    main()
