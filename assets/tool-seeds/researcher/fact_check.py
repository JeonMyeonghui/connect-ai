#!/usr/bin/env python3
"""Fact Check — 주장을 입력받아 웹 검색으로 근거를 수집하고 LLM이 진위를 판단.

설정: fact_check.json
  CLAIMS         : ["주장1", "주장2", ...] (필수)
  OLLAMA_URL     : LLM 서버 주소
  MODEL          : 사용할 모델 (비우면 자동)
  SEARCH_PER_CLAIM: 주장당 검색 결과 수 (기본 5)

출력: fact_check_report.md
"""
import os, json, sys, time, re, urllib.request, urllib.parse, html as html_module

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "fact_check.json")
REPORT_PATH = os.path.join(HERE, "fact_check_report.md")


# ── 설정 ───────────────────────────────────────────────────────────────────────
def load_config():
    if not os.path.exists(CONFIG_PATH):
        default = {
            "CLAIMS": [
                "ChatGPT는 2022년 11월에 출시됐다",
                "한국의 유튜브 사용자는 5000만 명이다"
            ],
            "OLLAMA_URL": "http://127.0.0.1:11434",
            "MODEL": "",
            "SEARCH_PER_CLAIM": 5
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        print(f"⚙️  설정 파일 생성: {CONFIG_PATH}")
        print("   CLAIMS에 검증할 주장을 입력하고 다시 실행하세요.")
        sys.exit(0)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── DuckDuckGo 검색 ────────────────────────────────────────────────────────────
def search(query: str, max_results: int = 5) -> list[dict]:
    q = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={q}&kl=kr-ko"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ConnectAI-FactCheck/1.0)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [{"title": "검색 실패", "url": "", "snippet": str(e)}]

    results = []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
        re.DOTALL
    )
    for m in pattern.finditer(body):
        href, title_raw, snippet_raw = m.groups()
        title   = html_module.unescape(re.sub(r"<[^>]+>", "", title_raw)).strip()
        snippet = html_module.unescape(re.sub(r"<[^>]+>", "", snippet_raw)).strip()
        if title and snippet:
            results.append({"title": title, "url": href, "snippet": snippet})
        if len(results) >= max_results:
            break
    return results


# ── LLM 호출 ──────────────────────────────────────────────────────────────────
def call_llm(ollama_url: str, model: str, prompt: str, max_tokens: int = 1500) -> str:
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
        if not base.endswith("/v1"):
            base += "/v1"
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False, "max_tokens": max_tokens
        }).encode()
        req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
    else:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{ollama_url}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
        if is_lm:
            return data["choices"][0]["message"]["content"].strip()
        return data["response"].strip()


# ── 주장 1건 검증 ──────────────────────────────────────────────────────────────
def verify_claim(claim: str, ollama_url: str, model: str,
                 search_per_claim: int) -> dict:
    print(f"\n   🔍 검색: {claim}")
    results = search(claim, search_per_claim)
    evidence = "\n".join(
        f"[{i+1}] {r['title']}\n    {r['snippet']}\n    출처: {r['url']}"
        for i, r in enumerate(results)
    )

    prompt = f"""당신은 팩트체커입니다. 다음 주장의 진위를 검색 결과 근거로 판단하세요.

주장: "{claim}"

검색 근거:
{evidence}

판정 형식 (반드시 이 구조로):
**판정:** ✅ 사실 / ❌ 거짓 / ⚠️ 부분적 사실 / ❓ 확인 불가
**신뢰도:** 높음/중간/낮음
**근거:** (2-3문장, 구체적 수치·출처 포함)
**보충 설명:** (맥락·주의사항, 1-2문장)"""

    result_text = call_llm(ollama_url, model, prompt)

    # 판정 추출
    verdict = "❓ 확인 불가"
    for marker in ["✅ 사실", "❌ 거짓", "⚠️ 부분적 사실", "❓ 확인 불가"]:
        if marker in result_text:
            verdict = marker
            break

    return {
        "claim": claim,
        "verdict": verdict,
        "analysis": result_text,
        "sources": [r["url"] for r in results if r.get("url")]
    }


# ── 메인 ───────────────────────────────────────────────────────────────────────
def main():
    cfg              = load_config()
    claims           = cfg.get("CLAIMS") or []
    ollama_url       = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    model            = (cfg.get("MODEL") or "").strip()
    search_per_claim = int(cfg.get("SEARCH_PER_CLAIM") or 5)

    if not claims:
        print("⚠️  CLAIMS가 비어있습니다."); sys.exit(1)

    print(f"\n✅ 팩트체크 시작 ({len(claims)}개 주장)")

    results = []
    for claim in claims:
        r = verify_claim(claim, ollama_url, model, search_per_claim)
        results.append(r)
        print(f"   {r['verdict']} — {claim[:50]}")
        time.sleep(1)

    # 최종 보고서 생성
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    verdicts_summary = "\n".join(
        f"| {r['verdict']} | {r['claim'][:60]} |"
        for r in results
    )

    report_lines = [
        f"# ✅ 팩트체크 보고서 — {now}",
        f"**검증 주장 수:** {len(results)}개\n",
        "## 요약",
        "| 판정 | 주장 |",
        "|------|------|",
        verdicts_summary,
        "",
        "## 상세 분석"
    ]
    for r in results:
        report_lines += [
            f"\n### 주장: {r['claim']}",
            r["analysis"],
            ""
        ]

    report = "\n".join(report_lines)

    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write("\n\n" + report + "\n\n---\n")

    print("\n" + "=" * 60)
    print(report[:2000])
    if len(report) > 2000:
        print(f"... (전체 보고서: {REPORT_PATH})")
    print("=" * 60)
    print(f"\n✅ 보고서 저장: {REPORT_PATH}")


if __name__ == "__main__":
    main()
