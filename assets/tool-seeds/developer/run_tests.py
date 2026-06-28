#!/usr/bin/env python3
"""Run Tests — 테스트를 실행하고 실패 원인을 LLM이 분석해서 수정 힌트를 제공.

설정: run_tests.json
  REPO_PATH      : 프로젝트 경로 (필수)
  TEST_CMD       : 실행할 테스트 명령 (기본: 자동 감지)
  OLLAMA_URL     : LLM 서버 주소
  MODEL          : 모델 (비우면 자동)
  TIMEOUT        : 테스트 타임아웃 초 (기본 120)

출력: run_tests_report.md
"""
import os, json, sys, time, subprocess, shutil, urllib.request

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "run_tests.json")
REPORT_PATH = os.path.join(HERE, "run_tests_report.md")

MAX_OUTPUT_CHARS = 8000


# ── 설정 ───────────────────────────────────────────────────────────────────────
def load_config():
    if not os.path.exists(CONFIG_PATH):
        default = {
            "REPO_PATH": "",
            "TEST_CMD": "",
            "OLLAMA_URL": "http://127.0.0.1:11434",
            "MODEL": "",
            "TIMEOUT": 120
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        print(f"⚙️  설정 파일 생성: {CONFIG_PATH}")
        print("   REPO_PATH를 입력하고 다시 실행하세요.")
        sys.exit(0)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 테스트 명령 자동 감지 ────────────────────────────────────────────────────────
def detect_test_cmd(repo_path: str) -> str:
    if os.path.exists(os.path.join(repo_path, "package.json")):
        with open(os.path.join(repo_path, "package.json"), encoding="utf-8") as f:
            pkg = json.load(f)
        scripts = pkg.get("scripts", {})
        if "test" in scripts:
            return "npm test"
        if "jest" in scripts:
            return "npm run jest"
    if os.path.exists(os.path.join(repo_path, "pytest.ini")) or \
       os.path.exists(os.path.join(repo_path, "pyproject.toml")) or \
       os.path.exists(os.path.join(repo_path, "setup.py")):
        return "pytest -v"
    if shutil.which("pytest"):
        return "pytest -v"
    if os.path.exists(os.path.join(repo_path, "Makefile")):
        return "make test"
    return "npm test"


# ── 테스트 실행 ──────────────────────────────────────────────────────────────────
def run_tests(repo_path: str, cmd: str, timeout: int) -> dict:
    print(f"   실행: {cmd}")
    start = time.time()
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=repo_path,
            capture_output=True, text=True, timeout=timeout
        )
        elapsed = time.time() - start
        output = (result.stdout + "\n" + result.stderr).strip()
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "output": output[:MAX_OUTPUT_CHARS],
            "elapsed": round(elapsed, 1),
            "cmd": cmd
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "output": f"❌ 타임아웃 ({timeout}초 초과)",
            "elapsed": timeout,
            "cmd": cmd
        }
    except Exception as e:
        return {
            "success": False,
            "returncode": -1,
            "output": f"실행 오류: {e}",
            "elapsed": 0,
            "cmd": cmd
        }


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
            "stream": False, "max_tokens": 2000
        }).encode()
        req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
    else:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{ollama_url}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
        if is_lm:
            return data["choices"][0]["message"]["content"].strip()
        return data["response"].strip()


# ── 메인 ───────────────────────────────────────────────────────────────────────
def main():
    cfg        = load_config()
    repo_path  = (cfg.get("REPO_PATH") or "").strip()
    test_cmd   = (cfg.get("TEST_CMD") or "").strip()
    ollama_url = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    model      = (cfg.get("MODEL") or "").strip()
    timeout    = int(cfg.get("TIMEOUT") or 120)

    if not repo_path or not os.path.isdir(repo_path):
        print("⚠️  REPO_PATH가 비어있거나 존재하지 않습니다."); sys.exit(1)

    if not test_cmd:
        test_cmd = detect_test_cmd(repo_path)
        print(f"   자동 감지된 테스트 명령: {test_cmd}")

    print(f"\n🧪 테스트 실행 중...")
    result = run_tests(repo_path, test_cmd, timeout)

    status_icon = "✅" if result["success"] else "❌"
    print(f"   {status_icon} 종료코드: {result['returncode']} ({result['elapsed']}초)")

    now = time.strftime("%Y-%m-%d %H:%M:%S")

    if result["success"]:
        # 통과 시 LLM 불필요
        report = f"# 🧪 테스트 결과 — {now}\n**상태:** ✅ 전체 통과 ({result['elapsed']}초)\n**명령:** `{test_cmd}`\n\n```\n{result['output'][:2000]}\n```"
        print("\n✅ 모든 테스트 통과!")
    else:
        # 실패 시 LLM이 원인 분석
        prompt = f"""소프트웨어 개발자로서 아래 테스트 실패 로그를 분석하세요.

프로젝트 경로: {repo_path}
실행 명령: {test_cmd}
종료 코드: {result['returncode']}

테스트 출력:
```
{result['output']}
```

다음 구조로 한국어 분석 보고서를 작성하세요:

### ❌ 실패한 테스트 목록
각 항목: 테스트명 — 실패 이유 (한 줄)

### 🔍 근본 원인 분석
가장 가능성 높은 원인 1-3가지 (구체적 파일명·줄번호 포함)

### 🔧 수정 방법
각 원인별 구체적 수정 코드 또는 명령어

### ⚡ 빠른 수정 순서
1번부터 시도해볼 것 순서대로"""

        print(f"🧠 LLM 실패 원인 분석 중...")
        analysis = call_llm(ollama_url, model, prompt)

        report = (
            f"# 🧪 테스트 결과 — {now}\n"
            f"**상태:** ❌ 실패 (종료코드 {result['returncode']}, {result['elapsed']}초)\n"
            f"**명령:** `{test_cmd}`\n\n"
            f"## 테스트 출력\n```\n{result['output'][:3000]}\n```\n\n"
            f"## LLM 분석\n{analysis}"
        )

        print("\n" + "=" * 60)
        print(analysis)
        print("=" * 60)

    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n{report}\n\n---\n")

    print(f"\n📄 보고서 저장: {REPORT_PATH}")


if __name__ == "__main__":
    main()
