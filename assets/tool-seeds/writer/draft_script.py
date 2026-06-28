#!/usr/bin/env python3
"""Draft Script — 주제를 입력하면 LLM이 영상 스크립트 초안을 작성.

구조: 후크(0-5초) → 도입부 → 본론(3파트) → CTA
설정: draft_script.json
  TOPIC          : 영상 주제 (필수)
  TARGET_LENGTH  : 목표 영상 길이(분) — 기본 5
  TONE           : 톤앤매너 (기본 "친근하고 정보성 있게")
  PLATFORM       : youtube | shorts | instagram (기본 youtube)
  OLLAMA_URL     : LLM 서버 주소
  MODEL          : 모델 (비우면 자동)
출력: draft_script_output.md
"""
import os, json, sys, time, urllib.request

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "draft_script.json")
OUTPUT_PATH = os.path.join(HERE, "draft_script_output.md")

PLATFORM_GUIDE = {
    "youtube":   "5~15분 유튜브 영상. 도입·본론·마무리 완전한 구조.",
    "shorts":    "60초 이내 숏폼. 후크 3초 → 핵심 1가지 → CTA. 군더더기 없이.",
    "instagram": "30~60초 릴스. 비주얼 중심, 자막 의존도 높음. 짧고 강하게.",
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "TOPIC": "",
                "TARGET_LENGTH": 5,
                "TONE": "친근하고 정보성 있게",
                "PLATFORM": "youtube",
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
                               "stream": False, "max_tokens": 4000}).encode()
        req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
    else:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{url}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read())
        return (data["choices"][0]["message"]["content"] if is_lm else data["response"]).strip()


def main():
    cfg      = load_config()
    topic    = (cfg.get("TOPIC") or "").strip()
    length   = int(cfg.get("TARGET_LENGTH") or 5)
    tone     = cfg.get("TONE") or "친근하고 정보성 있게"
    platform = (cfg.get("PLATFORM") or "youtube").lower()
    url      = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    model    = (cfg.get("MODEL") or "").strip()

    if not topic:
        print("⚠️  draft_script.json의 TOPIC이 비어있습니다."); sys.exit(1)

    guide = PLATFORM_GUIDE.get(platform, PLATFORM_GUIDE["youtube"])

    prompt = f"""당신은 10년 경력의 유튜브 스크립트 작가입니다.

주제: {topic}
플랫폼: {platform.upper()} — {guide}
목표 길이: {length}분
톤앤매너: {tone}

다음 구조로 완성된 스크립트를 한국어로 작성하세요:

---
## 🎣 후크 (0-5초)
(시청자가 멈추게 만드는 첫 한 문장. 질문·충격·공감 중 하나)

## 📌 도입부 (5-30초)
(오늘 영상에서 얻어갈 것 + 왜 봐야 하는지)

## 🎯 본론 파트 1 — [소제목]
(내용 + 내레이션 대본)

## 🎯 본론 파트 2 — [소제목]
(내용 + 내레이션 대본)

## 🎯 본론 파트 3 — [소제목]
(내용 + 내레이션 대본)

## 🔔 마무리 + CTA
(핵심 요약 → 구독·좋아요·댓글 유도. 자연스럽게.)

---
**예상 길이:** X분 X초
**썸네일 키워드 제안:** (3개)
**제목 후보:** (3개, 알고리즘 최적화)
"""

    print(f"\n✍️  스크립트 작성 중: {topic}")
    print(f"   플랫폼: {platform} | 길이: {length}분 | 모델: {model or '자동'}")
    script = call_llm(url, model, prompt)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n# ✍️ 스크립트 초안 — {now}\n**주제:** {topic} | **플랫폼:** {platform}\n\n")
        f.write(script)
        f.write("\n\n---\n")

    print("\n" + "=" * 60)
    print(script)
    print("=" * 60)
    print(f"\n✅ 저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
