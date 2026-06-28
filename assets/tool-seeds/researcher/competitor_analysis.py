#!/usr/bin/env python3
"""Competitor Analysis — 경쟁사 URL을 크롤링하고 LLM이 강약점·차별화 전략을 분석.

설정: competitor_analysis.json
  COMPETITORS    : [{"name": "경쟁사명", "url": "https://..."}] (필수)
  MY_PRODUCT     : 내 제품/서비스 설명 (필수)
  OLLAMA_URL     : LLM 서버 주소
  MODEL          : 사용할 모델 (비우면 자동)

출력: competitor_analysis_report.md
"""
import os, json, sys, time, re, urllib.request, urllib.parse, html as html_module

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "competitor_analysis.json")
REPORT_PATH = os.path.join(HERE, "competitor_analysis_report.md")

MAX_PAGE_CHARS = 8000   # 한 페이지에서 추출할 최대 텍스트 양


# ── 설정 로드 ──────────────────────────────────────────────────────────────────
def load_config():
    if not os.path.exists(CONFIG_PATH):
        default = {
            "COMPETITORS": [
                {"name": "경쟁사 A", "url": "https://example.com"},
                {"name": "경쟁사 B", "url": "https://example2.com"}
            ],
            "MY_PRODUCT": "내 제품/서비스 설명을 여기에 입력하세요",
            "OLLAMA_URL": "http://127.0.0.1:11434",
            "MODEL": ""
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        print(f"⚙️  설정 파일 생성: {CONFIG_PATH}")
        print("   COMPETITORS와 MY_PRODUCT를 입력하고 다시 실행하세요.")
        sys.exit(0)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 웹 페이지 텍스트 추출 ────────────────────────────────────────────────────────
def fetch_page_text(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ConnectAI-Researcher/1.0)",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            body = raw.decode(charset, errors="replace")
    except Exception as e:
        return f"[페이지 로드 실패: {e}]"

    # 스크립트·스타일 제거
    body = re.sub(r"<script[^>]*>.*?</script>", " ", body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r"<style[^>]*>.*?</style>", " ", body, flags=re.DOTALL | re.IGNORECASE)
    # HTML 태그 제거
    text = re.sub(r"<[^>]+>", " ", body)
    text = html_module.unescape(text)
    # 공백 정리
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_PAGE_CHARS]


# ── LLM 호출 (web_search.py와 동일 패턴) ────────────────────────────────────────
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
            print("❌ 모델 자동 선택 실패. MODEL을 직접 지정하세요."); sys.exit(1)

    if is_lm:
        base = ollama_url.rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": 3000
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
    cfg         = load_config()
    competitors = cfg.get("COMPETITORS") or []
    my_product  = (cfg.get("MY_PRODUCT") or "").strip()
    ollama_url  = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    model       = (cfg.get("MODEL") or "").strip()

    if not competitors:
        print("⚠️  COMPETITORS가 비어있습니다."); sys.exit(1)
    if not my_product:
        print("⚠️  MY_PRODUCT를 입력하세요."); sys.exit(1)

    print(f"\n🕵️  경쟁사 분석 시작 ({len(competitors)}개)")

    # 각 경쟁사 페이지 크롤링
    crawled = []
    for comp in competitors:
        name = comp.get("name", "Unknown")
        url  = comp.get("url", "")
        if not url:
            continue
        print(f"   📡 {name} ({url}) 크롤링 중...")
        text = fetch_page_text(url)
        crawled.append({"name": name, "url": url, "text": text})
        time.sleep(1)  # 예의 있는 크롤링

    if not crawled:
        print("❌ 크롤링된 데이터 없음."); sys.exit(1)

    # LLM 분석 프롬프트
    comp_sections = "\n\n".join(
        f"## {c['name']} ({c['url']})\n{c['text'][:3000]}"
        for c in crawled
    )

    prompt = f"""당신은 전략 컨설턴트입니다. 아래 경쟁사 정보와 내 제품을 비교 분석하세요.

## 내 제품/서비스
{my_product}

## 경쟁사 정보
{comp_sections}

다음 구조로 한국어 분석 보고서를 작성하세요:

### 1. 경쟁사별 강점·약점 요약 (표 형식)
| 경쟁사 | 강점 | 약점 | 차별화 포인트 |

### 2. 시장 포지셔닝 분석
- 내 제품이 비어있는 틈새는?
- 직접 충돌하는 영역은?

### 3. 즉시 실행 가능한 차별화 전략 3가지
각 전략에 구체적 실행 방법 포함.

### 4. 위험 요소
경쟁사가 내 강점을 침범할 수 있는 시나리오.

간결하고 실용적으로 작성."""

    print(f"🧠 LLM 분석 중... (모델: {model or '자동'})")
    report = call_llm(ollama_url, model, prompt)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    comp_names = ", ".join(c["name"] for c in crawled)
    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n# 🕵️ 경쟁사 분석 보고서 — {now}\n")
        f.write(f"**대상:** {comp_names}\n\n")
        f.write(report)
        f.write("\n\n---\n")

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)
    print(f"\n✅ 보고서 저장: {REPORT_PATH}")


if __name__ == "__main__":
    main()
