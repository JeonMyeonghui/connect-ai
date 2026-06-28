#!/usr/bin/env python3
"""Caption Writer — 콘텐츠 주제를 입력하면 플랫폼별 캡션을 한 번에 생성.

플랫폼: YouTube 설명란 / Instagram / X(트위터) / LinkedIn
설정: caption_writer.json
  TOPIC          : 콘텐츠 주제 (필수)
  CONTENT_SUMMARY: 콘텐츠 핵심 내용 요약 (선택, 있으면 더 정확한 캡션)
  PLATFORMS      : ["youtube", "instagram", "twitter", "linkedin"] (기본 전체)
  BRAND_VOICE    : 브랜드 톤 (기본 "전문적이고 친근하게")
  HASHTAG_COUNT  : 해시태그 수 (기본 10)
  OLLAMA_URL / MODEL
출력: caption_writer_output.md
"""
import os, json, sys, time, urllib.request

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "caption_writer.json")
OUTPUT_PATH = os.path.join(HERE, "caption_writer_output.md")

PLATFORM_SPECS = {
    "youtube":   "YouTube 설명란: 200자 이내 핵심 요약 + 챕터 힌트. SEO 키워드 자연스럽게 포함. 해시태그 3개.",
    "instagram": "인스타그램: 이모지 적극 활용, 줄바꿈으로 가독성. 150자 이내 + 해시태그 별도 줄. 행동 유도 CTA 포함.",
    "twitter":   "X(트위터): 280자 제한. 핵심 1가지만. 링크 포함 가정하고 공간 확보. 해시태그 2개 이하.",
    "linkedin":  "LinkedIn: 전문적 톤. 인사이트 중심. 3-5줄 + 마무리 질문으로 댓글 유도. 해시태그 5개.",
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "TOPIC": "",
                "CONTENT_SUMMARY": "",
                "PLATFORMS": ["youtube", "instagram", "twitter", "linkedin"],
                "BRAND_VOICE": "전문적이고 친근하게",
                "HASHTAG_COUNT": 10,
                "OLLAMA_URL": "http://127.0.0.1:11434",
                "MODEL": ""
            }, f, ensure_ascii=False, indent=2)
        print(f"⚙️  설정 파일 생성: {CONFIG_PATH}\n   TOPIC을 입력하고 다시 실행하세요.")
        sys.exit(0)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def call_llm(url: str, model: str, prompt: str) -> str:
    is_lm = "1234" in url or "/v1" in url
    if not model:
        try:
            ep = f"{url}/v1/models" if is_lm else f"{url}/api/tags"
            with urllib.request.urlopen(ep, timeout=5) as r:
                data = json.loads(r.read())
            model = data["data"][0]["id"] if is_lm else data["models"][0]["name"]
        except Exception:
            print("❌ 모델 자동 선택 실패."); sys.exit(1)

    if is_lm:
        base = url.rstrip("/")
        if not base.endswith("/v1"): base += "/v1"
        payload = json.dumps({"model": model,
                               "messages": [{"role": "user", "content": prompt}],
                               "stream": False, "max_tokens": 3000}).encode()
        req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
    else:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{url}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=240) as r:
        data = json.loads(r.read())
        return (data["choices"][0]["message"]["content"] if is_lm else data["response"]).strip()


def main():
    cfg       = load_config()
    topic     = (cfg.get("TOPIC") or "").strip()
    summary   = (cfg.get("CONTENT_SUMMARY") or "").strip()
    platforms = cfg.get("PLATFORMS") or list(PLATFORM_SPECS.keys())
    voice     = cfg.get("BRAND_VOICE") or "전문적이고 친근하게"
    htag_cnt  = int(cfg.get("HASHTAG_COUNT") or 10)
    url       = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    model     = (cfg.get("MODEL") or "").strip()

    if not topic:
        print("⚠️  caption_writer.json의 TOPIC이 비어있습니다."); sys.exit(1)

    valid_platforms = [p for p in platforms if p in PLATFORM_SPECS]
    if not valid_platforms:
        valid_platforms = list(PLATFORM_SPECS.keys())

    specs_text   = "\n".join(f"- **{p.upper()}**: {PLATFORM_SPECS[p]}" for p in valid_platforms)
    summary_part = f"\n\n콘텐츠 요약: {summary}" if summary else ""

    prompt = f"""당신은 SNS 마케팅 전문 카피라이터입니다.

콘텐츠 주제: {topic}{summary_part}
브랜드 보이스: {voice}
해시태그: {htag_cnt}개 내외 (플랫폼별 적절히 배분)

아래 플랫폼별 규칙에 맞게 캡션을 작성하세요:
{specs_text}

출력 형식 (각 플랫폼 섹션으로 구분):

---
### 📺 YouTube
(캡션 내용)

---
### 📷 Instagram
(캡션 내용)

---
### 🐦 X (Twitter)
(캡션 내용)

---
### 💼 LinkedIn
(캡션 내용)

---
### #️⃣ 공통 해시태그 풀 ({htag_cnt}개)
(모든 플랫폼에서 골라 쓸 수 있는 해시태그 목록)
"""

    print(f"\n📝 캡션 생성 중: {topic}")
    print(f"   플랫폼: {', '.join(valid_platforms)} | 모델: {model or '자동'}")
    result = call_llm(url, model, prompt)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n# 📝 캡션 생성 — {now}\n**주제:** {topic}\n\n")
        f.write(result)
        f.write("\n\n---\n")

    print("\n" + "=" * 60)
    print(result)
    print("=" * 60)
    print(f"\n✅ 저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
