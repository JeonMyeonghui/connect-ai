#!/usr/bin/env python3
"""Code Review — git diff를 로컬 LLM이 분석해서 코드 리뷰 보고서 작성.

설정: code_review.json
  REPO_PATH      : 리뷰할 git 저장소 경로 (기본: 현재 디렉토리)
  DIFF_TARGET    : "staged" | "unstaged" | "HEAD~1" | 커밋 해시 (기본: staged)
  FOCUS          : 리뷰 집중 포인트 (보안/성능/가독성/버그, 비우면 전체)
  MAX_DIFF_CHARS : diff 최대 길이 (기본 6000)
  OLLAMA_URL     : LLM 서버 주소
  MODEL          : 사용할 모델 (비우면 자동)

출력: code_review_report.md
"""
import os, json, sys, time, subprocess, urllib.request

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "code_review.json")
REPORT_PATH = os.path.join(HERE, "code_review_report.md")


# ── 설정 ───────────────────────────────────────────────────────────────────────
def load_config():
    if not os.path.exists(CONFIG_PATH):
        default = {
            "REPO_PATH": "",
            "DIFF_TARGET": "staged",
            "FOCUS": "",
            "MAX_DIFF_CHARS": 6000,
            "OLLAMA_URL": "http://127.0.0.1:11434",
            "MODEL": ""
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        print(f"⚙️  설정 파일 생성: {CONFIG_PATH}")
        print("   REPO_PATH를 입력하고 다시 실행하세요. (비우면 현재 경로 사용)")
        sys.exit(0)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── git diff 가져오기 ─────────────────────────────────────────────────────────
def get_diff(repo_path: str, target: str, max_chars: int) -> tuple[str, str]:
    """(diff_text, stat_text) 반환"""
    cwd = repo_path if repo_path and os.path.isdir(repo_path) else os.getcwd()

    def run(*args):
        r = subprocess.run(["git"] + list(args), cwd=cwd,
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip()

    if target == "staged":
        stat = run("diff", "--staged", "--stat")
        diff = run("diff", "--staged")
    elif target == "unstaged":
        stat = run("diff", "--stat")
        diff = run("diff")
    elif target == "HEAD~1":
        stat = run("diff", "HEAD~1", "--stat")
        diff = run("diff", "HEAD~1")
    else:
        # 커밋 해시로 간주
        stat = run("show", "--stat", target)
        diff = run("show", target)

    if not diff:
        # staged 없으면 unstaged 시도
        if target == "staged":
            stat = run("diff", "--stat")
            diff = run("diff")

    return diff[:max_chars], stat


# ── LLM 호출 ──────────────────────────────────────────────────────────────────
def call_llm(ollama_url: str, model: str, prompt: str) -> str:
    is_lm = "1234" in ollama_url or "/v1" in ollama_url
    if not model:
        try:
            if is_lm:
                with urllib.request.urlopen(f"{ollama_url}/v1/models", timeout=5) as r:
                    model = json.loads(r.read())["data"][0]["id"]
            else:
                with urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=5) as r:
                    model = json.loads(r.read())["models"][0]["name"]
        except Exception:
            print("❌ 모델 자동 선택 실패."); sys.exit(1)

    if is_lm:
        base = ollama_url.rstrip("/")
        if not base.endswith("/v1"): base += "/v1"
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False, "max_tokens": 3000
        }).encode()
        req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
    else:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{ollama_url}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=240) as resp:
        data = json.loads(resp.read())
        if is_lm:
            return data["choices"][0]["message"]["content"].strip()
        return data["response"].strip()


# ── 메인 ───────────────────────────────────────────────────────────────────────
def main():
    cfg        = load_config()
    repo_path  = (cfg.get("REPO_PATH") or "").strip()
    target     = (cfg.get("DIFF_TARGET") or "staged").strip()
    focus      = (cfg.get("FOCUS") or "").strip()
    max_chars  = int(cfg.get("MAX_DIFF_CHARS") or 6000)
    ollama_url = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    model      = (cfg.get("MODEL") or "").strip()

    print(f"\n💻 코드 리뷰 시작 (target: {target})")
    diff, stat = get_diff(repo_path, target, max_chars)

    if not diff:
        print("⚠️  변경사항이 없습니다."); sys.exit(0)

    focus_part = f"\n특히 집중해서 리뷰: {focus}" if focus else ""
    prompt = f"""당신은 시니어 소프트웨어 엔지니어입니다. 아래 git diff를 코드 리뷰하세요.{focus_part}

변경 통계:
{stat}

변경 코드:
```diff
{diff}
```

다음 구조로 한국어 리뷰 보고서를 작성하세요:

### 🔴 즉시 수정 필요 (버그·보안·크래시 위험)
각 항목: 파일명:줄번호 — 문제 설명 + 수정 방법

### 🟡 권장 개선사항 (코드 품질·성능·가독성)
각 항목: 파일명:줄번호 — 개선 이유 + 개선 방법

### 🟢 잘 된 점
간략히 2-3가지

### 📋 종합 평가
점수: X/10 — 한 줄 총평

없는 카테고리는 "없음"으로 표시. 구체적이고 실용적으로."""

    print(f"🧠 LLM 분석 중... (모델: {model or '자동'})")
    review = call_llm(ollama_url, model, prompt)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n# 💻 코드 리뷰 — {now}\n")
        f.write(f"**대상:** `{target}` | **저장소:** `{repo_path or '현재 디렉토리'}`\n\n")
        f.write(f"**변경 통계:**\n```\n{stat}\n```\n\n")
        f.write(review)
        f.write("\n\n---\n")

    print("\n" + "=" * 60)
    print(review)
    print("=" * 60)
    print(f"\n✅ 리뷰 저장: {REPORT_PATH}")


if __name__ == "__main__":
    main()
