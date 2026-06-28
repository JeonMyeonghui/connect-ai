#!/usr/bin/env python3
"""Hook Generator — 영상 첫 5초 후킹 오프닝을 5가지 패턴으로 생성.

패턴: 질문형 / 충격 수치 / 공감 / 역발상 / 스토리텔링
설정: hook_generator.json
  TOPIC          : 영상 주제 (필수)
  CONTEXT        : 추가 맥락 (타겟 시청자, 핵심 메시지 등)
  PLATFORM       : youtube | shorts | instagram (기본 youtube)
  COUNT          : 생성할 후크 수 (기본 5)
  OLLAMA_URL / MODEL
출력: hook_generator_output.md
"""
import os, json, sys, time, urllib.request

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "hook_generator.json")
OUTPUT_PATH = os.path.join(HERE, "hook_generator_output.md")

HOOK_PATTERNS = {
    "질문형":     "시청자가 '나도 이거 궁금했는데' 하고 멈추는 질문",
    "충격 수치":  "믿기 어려운 숫자나 통계로 시작",
    "공감":       "시청자의 고통·불편함을 정확히 짚어주는 문장",
    "역발상":     "상식을 뒤집는 반직관적 주장",
    "스토리텔링": "짧지만 궁금증을 유발하는 미니 스토리 시작",
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "TOPIC": "",
                "CONTEXT": "",
                "PLATFORM": "youtube",
                "COUNT": 5,
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
                               "stream": False, "max_tokens": 2000}).encode()
        req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
    else:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{url}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
        return (data["choices"][0]["message"]["content"] if is_lm else data["response"]).strip()


def main():
    cfg      = load_config()
    topic    = (cfg.get("TOPIC") or "").strip()
    context  = (cfg.get("CONTEXT") or "").strip()
    platform = (cfg.get("PLATFORM") or "youtube").lower()
    count    = min(int(cfg.get("COUNT") or 5), 10)
    url      = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    model    = (cfg.get("MODEL") or "").strip()

    if not topic:
        print("⚠️  hook_generator.json의 TOPIC이 비어있습니다."); sys.exit(1)

    patterns_text = "\n".join(f"- **{k}**: {v}" for k, v in list(HOOK_PATTERNS.items())[:count])
    context_part  = f"\n추가 맥락: {context}" if context else ""
    platform_note = "숏폼(60초) — 더 짧고 강렬하게" if platform in ("shorts", "instagram") else "롱폼 유튜브"

    prompt = f"""당신은 조회수 100만 이상의 유튜브 영상을 다수 기획한 전문가입니다.

주제: {topic}
플랫폼: {platform_note}{context_part}

아래 {count}가지 패턴으로 영상 첫 5초 후크를 각각 1개씩 작성하세요.
각 후크는 최대 2문장, 실제 나레이션으로 읽을 수 있게.

{patterns_text}

출력 형식:
### 1. [패턴명]
> (후크 문장)
*왜 효과적인가: 한 줄 설명*
"""

    print(f"\n🎣 후크 {count}가지 생성 중: {topic}")
    result = call_llm(url, model, prompt)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n# 🎣 후크 생성 — {now}\n**주제:** {topic} | **플랫폼:** {platform}\n\n")
        f.write(result)
        f.write("\n\n---\n")

    print("\n" + "=" * 60)
    print(result)
    print("=" * 60)
    print(f"\n✅ 저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
