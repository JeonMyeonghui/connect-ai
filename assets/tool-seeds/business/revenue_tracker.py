#!/usr/bin/env python3
"""Revenue Tracker — 수익 데이터를 입력하면 트렌드 분석 + LLM 인사이트 보고서 생성.

설정: revenue_tracker.json
  REVENUE_DATA   : [{"period": "2026-05", "amount": 1500000, "source": "유튜브 광고"}, ...]
  CURRENCY       : 통화 단위 (기본 "원")
  GOAL           : 목표 수익 (월간, 선택)
  OLLAMA_URL / MODEL
출력: revenue_tracker_report.md
"""
import os, json, sys, time, urllib.request
from datetime import datetime

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "revenue_tracker.json")
REPORT_PATH = os.path.join(HERE, "revenue_tracker_report.md")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "REVENUE_DATA": [
                    {"period": "2026-01", "amount": 0, "source": "유튜브 광고"},
                    {"period": "2026-02", "amount": 0, "source": "유튜브 광고"},
                    {"period": "2026-03", "amount": 0, "source": "유튜브 광고"}
                ],
                "CURRENCY": "원",
                "GOAL": 0,
                "OLLAMA_URL": "http://127.0.0.1:11434",
                "MODEL": ""
            }, f, ensure_ascii=False, indent=2)
        print(f"⚙️  설정 파일 생성: {CONFIG_PATH}\n   REVENUE_DATA에 수익 데이터를 입력하고 다시 실행하세요.")
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


def format_amount(n: float, currency: str) -> str:
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}백만{currency}"
    if abs(n) >= 10_000:
        return f"{n/10_000:.1f}만{currency}"
    return f"{n:,.0f}{currency}"


def main():
    cfg      = load_config()
    data     = cfg.get("REVENUE_DATA") or []
    currency = cfg.get("CURRENCY") or "원"
    goal     = float(cfg.get("GOAL") or 0)
    url      = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    model    = (cfg.get("MODEL") or "").strip()

    if not data:
        print("⚠️  REVENUE_DATA가 비어있습니다."); sys.exit(1)

    # 기본 통계 계산
    amounts  = [float(d.get("amount", 0)) for d in data]
    total    = sum(amounts)
    avg      = total / len(amounts) if amounts else 0
    peak     = max(amounts) if amounts else 0
    peak_period = data[amounts.index(peak)].get("period", "?") if amounts else "?"

    # 전월 대비 증감 (마지막 2개)
    mom_change = ""
    if len(amounts) >= 2 and amounts[-2] > 0:
        change = (amounts[-1] - amounts[-2]) / amounts[-2] * 100
        mom_change = f"전월 대비 {change:+.1f}%"

    # 소스별 합계
    by_source: dict[str, float] = {}
    for d in data:
        src = d.get("source", "기타")
        by_source[src] = by_source.get(src, 0) + float(d.get("amount", 0))
    source_summary = "\n".join(f"  - {k}: {format_amount(v, currency)}" for k, v in
                                sorted(by_source.items(), key=lambda x: -x[1]))

    data_table = "\n".join(
        f"  {d.get('period','?')} | {format_amount(float(d.get('amount',0)), currency)} | {d.get('source','')}"
        for d in data
    )
    goal_part = f"\n목표 수익: {format_amount(goal, currency)}/월 (달성률: {amounts[-1]/goal*100:.1f}%)" if goal > 0 else ""

    prompt = f"""당신은 1인 기업 재무 컨설턴트입니다. 아래 수익 데이터를 분석하세요.

## 수익 데이터
{data_table}

## 통계 요약
- 총 누적: {format_amount(total, currency)}
- 월평균: {format_amount(avg, currency)}
- 최고 달: {peak_period} ({format_amount(peak, currency)}){goal_part}
- {mom_change}

## 수익원별 합계
{source_summary}

다음 구조로 한국어 분석 보고서를 작성하세요:

### 📈 트렌드 분석
성장세·하락세·계절성 패턴 등 데이터가 말해주는 것

### 💡 핵심 인사이트 3가지
각 인사이트: 관찰 → 의미 → 행동

### 🎯 다음 달 수익 예측
데이터 기반 추정치 + 근거

### ⚡ 즉시 실행할 수익 최적화 액션 3가지
구체적이고 현실적인 것만"""

    print(f"\n💰 수익 분석 중... ({len(data)}개월 데이터)")
    report = call_llm(url, model, prompt)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n# 💰 수익 분석 보고서 — {now}\n")
        f.write(f"**기간:** {data[0].get('period','?')} ~ {data[-1].get('period','?')} | **총합:** {format_amount(total, currency)}\n\n")
        f.write(report)
        f.write("\n\n---\n")

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)
    print(f"\n✅ 저장: {REPORT_PATH}")


if __name__ == "__main__":
    main()
