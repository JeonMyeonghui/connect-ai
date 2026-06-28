#!/usr/bin/env python3
"""KPI Report — KPI 데이터를 입력하면 주간/월간 보고서를 자동 생성.

설정: kpi_report.json
  KPIS           : [{"name": "구독자 수", "current": 1200, "target": 5000, "unit": "명"}, ...]
  PERIOD         : 보고서 기간 (기본 "이번 주")
  WINS           : ["이번 주 잘된 것"] (선택)
  BLOCKERS       : ["막히는 것"] (선택)
  OLLAMA_URL / MODEL
출력: kpi_report_output.md
"""
import os, json, sys, time, urllib.request

HERE        = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "kpi_report.json")
OUTPUT_PATH = os.path.join(HERE, "kpi_report_output.md")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "KPIS": [
                    {"name": "유튜브 구독자", "current": 0, "previous": 0, "target": 10000, "unit": "명"},
                    {"name": "월 수익",        "current": 0, "previous": 0, "target": 1000000, "unit": "원"},
                    {"name": "영상 업로드",     "current": 0, "previous": 0, "target": 4, "unit": "개/월"},
                    {"name": "평균 조회수",     "current": 0, "previous": 0, "target": 5000, "unit": "회"}
                ],
                "PERIOD": "이번 주",
                "WINS": [],
                "BLOCKERS": [],
                "OLLAMA_URL": "http://127.0.0.1:11434",
                "MODEL": ""
            }, f, ensure_ascii=False, indent=2)
        print(f"⚙️  설정 파일 생성: {CONFIG_PATH}\n   KPIS에 현재 수치를 입력하고 다시 실행하세요.")
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
                               "stream": False, "max_tokens": 2500}).encode()
        req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
    else:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{url}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
        return (data["choices"][0]["message"]["content"] if is_lm else data["response"]).strip()


def progress_bar(current: float, target: float, width: int = 10) -> str:
    if target <= 0: return "N/A"
    pct = min(current / target, 1.0)
    filled = int(pct * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {pct*100:.1f}%"


def main():
    cfg      = load_config()
    kpis     = cfg.get("KPIS") or []
    period   = cfg.get("PERIOD") or "이번 주"
    wins     = cfg.get("WINS") or []
    blockers = cfg.get("BLOCKERS") or []
    url      = (cfg.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    model    = (cfg.get("MODEL") or "").strip()

    if not kpis:
        print("⚠️  KPIS가 비어있습니다."); sys.exit(1)

    # KPI 테이블 생성
    kpi_rows = []
    for k in kpis:
        name    = k.get("name", "?")
        current = float(k.get("current", 0))
        prev    = float(k.get("previous", 0))
        target  = float(k.get("target", 0))
        unit    = k.get("unit", "")

        mom = ""
        if prev > 0:
            change = (current - prev) / prev * 100
            mom = f" ({change:+.1f}%)"

        bar = progress_bar(current, target) if target > 0 else ""
        kpi_rows.append(
            f"| {name} | {current:,.0f}{unit}{mom} | {target:,.0f}{unit} | {bar} |"
        )

    kpi_table = (
        "| KPI | 현재 | 목표 | 달성률 |\n"
        "|-----|------|------|--------|\n" +
        "\n".join(kpi_rows)
    )

    wins_text     = "\n".join(f"- {w}" for w in wins) if wins else "없음"
    blockers_text = "\n".join(f"- {b}" for b in blockers) if blockers else "없음"

    prompt = f"""당신은 1인 기업 비즈니스 코치입니다. 아래 KPI를 바탕으로 {period} 보고서를 작성하세요.

## KPI 현황
{kpi_table}

## 잘된 것
{wins_text}

## 막히는 것
{blockers_text}

다음 구조로 한국어 보고서를 작성하세요:

### 📊 {period} 종합 평가
한 줄 총평 + 전체 점수 (X/10)

### 🟢 잘 된 것 & 왜 중요한가
### 🔴 개선 필요 & 다음 주 액션
### 🎯 다음 주 집중 목표 (최대 3가지)
각 목표: 구체적 수치 포함

### ⚡ 즉시 해야 할 것 TOP 1
가장 레버리지 높은 단 하나의 행동"""

    print(f"\n📊 KPI 보고서 생성 중... ({period})")
    report = call_llm(url, model, prompt)

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n\n# 📊 KPI 보고서 — {period} ({now})\n\n")
        f.write(kpi_table + "\n\n")
        f.write(report)
        f.write("\n\n---\n")

    print("\n" + "=" * 60)
    print(kpi_table)
    print()
    print(report)
    print("=" * 60)
    print(f"\n✅ 저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
