#!/usr/bin/env python3
"""Web Search — DuckDuckGo로 검색하고 로컬 LLM이 핵심 인사이트 보고서를 작성.

설정: web_search.json
  QUERY          : 검색어 (필수)
  MAX_RESULTS    : 가져올 결과 수 (기본 10)
  OLLAMA_URL     : LLM 서버 주소 (기본 http://127.0.0.1:11434)
  MODEL          : 사용할 모델 (비우면 자동 선택)
  LANGUAGE       : 보고서 언어 (기본 "Korean")

출력: web_search_report.md
"""
import os, json, sys, time, re, urllib.request, urllib.parse, html

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "web_search.json")
REPORT_PATH = os.path.join(HERE, "web_search_report.md")


# ── 설정 로드 ──────────────────────────────────────────────────────────────────
def load_config():
    if not os.path.exists(CONFIG_PATH):
        default = {
            "QUERY": "",
            "MAX_RESULTS": 10,
            "OLLAMA_URL": "http://127.0.0.1:11434",
            "MODEL": "",
            "LANGUAGE": "Korean"
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        print(f"⚙️  설정 파일 생성: {CONFIG_PATH}")
        print("   QUERY에 검색어를 입력하고 다시 실행하세요.")
        sys.exit(0)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── DuckDuckGo HTML 검색 (API 키 불필요) ────────────────────────────────────────
def search_duckduckgo(query: str, max_results: int = 10) -> list[dict]:
    q = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={q}&kl=kr-ko"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ConnectAI-Researcher/1.0)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"❌ 검색 요청 실패: {e}")
        return []

    results = []
    # DuckDuckGo HTML 파싱 (간단한 정규식)
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        re.DOTALL
    )
    for m in pattern.finditer(body):
        href, title_raw, snippet_raw = m.groups()
        title   = html.unescape(re.sub(r"<[^>]+>", "", title_raw)).strip()
        snippet = html.unescape(re.sub(r"<[^>]+>", "", snippet_raw)).strip()
        if title and snippet:
            results.append({"url": href, "title": title, "snippet": snippet})
        if len(results) >= max_results:
            break

    # 폴백: result__url 패턴
    if not results:
        alt = re.compile(r'class="result__title"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        snip = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
        titles = alt.findall(body)
        snippets = [html.unescape(re.sub(r"<[^>]+>", "", s)).strip() for s in snip.findall(body)]
        for (href, title_raw), snip_text in zip(titles[:max_results], snippets):
            title = html.unescape(re.sub(r"<[^>]+>", "", title_raw)).strip()
            if title:
                results.append({"url": href, "title": title, "snippet": snip_text})

    return results


# ── 로컬 LLM 호출 ──────────────────────────────────────────────────────────────
def _auto_model(ollama_url: str, is_lm: bool) -> str:
    try:
        if is_lm:
            import urllib.request as r
            with r.urlopen(f"{ollama_url}/v1/models", timeout=5) as resp:
                data = json.loads(resp.read())
            return data["data"][0]["id"]
        else:
            with urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=5) as resp:
                data = json.loads(resp.read())
            return data["models"][0]["name"]
    except Exception:
        return ""


def call_llm(ollama_url: str, model: str, prompt: str) -> str:
    is_lm = "1234" in ollama_url or "/v1" in ollama_url
    if not model:
        model = _auto_model(ollama_url, is_lm)
    if not model:
        print("❌ 사용 가능한 모델이 없습니다.")
        sys.exit(1)

    if is_lm:
        base = ollama_url.rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": 2048
        }).encode()
        req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"].strip()
    else:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{ollama_url}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["response"].strip()


# ── 메인 ───────────────────────────────────────────────────────────────────────
def main():
    cfg         = load_config()
    query       = (cfg.get("QUERY") or "").strip()
    max_results = int(cfg.get("MAX_RESULTS") or 10)
    ollama_url  = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    model       = (cfg.get("MODEL") or "").strip()
    language    = cfg.get("LANGUAGE") or "Korean"

    if not query:
        print("⚠️  web_search.json의 QUERY가 비어있습니다.")
        sys.exit(1)

    print(f"\n🔍 검색: {query}")
    results = search_duckduckgo(query, max_results)
    if not results:
        print("❌ 검색 결과가 없습니다. 네트워크 연결을 확인하세요.")
        sys.exit(1)
    print(f"   {len(results)}개 결과 수집 완료")

    data_text = "\n".join(
        f"[{i+1}] {r['title']}\n    URL: {r['url']}\n    {r['snippet']}"
        for i, r in enumerate(results)
    )

    prompt = f"""You are a professional research analyst. Analyze the following search results for the query "{query}" and write a structured research report in {language}.

Search Results:
{data_text}

Write a report with these sections:
1. 🔍 핵심 요약 (3-5줄)
2. 📊 주요 발견사항 (불릿 포인트)
3. 💡 실행 가능한 인사이트 (3가지)
4. 🔗 참고할 만한 소스 (상위 3개 URL + 이유)

Be concise and actionable. No filler."""

    print(f"🧠 LLM 분석 중... (모델: {model or '자동'})")
    report = call_llm(ollama_url, model, prompt)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n# 🔍 웹 검색 보고서 — {now}\n")
        f.write(f"**검색어:** {query}\n\n")
        f.write(report)
        f.write("\n\n---\n")

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)
    print(f"\n✅ 보고서 저장: {REPORT_PATH}")


if __name__ == "__main__":
    main()
