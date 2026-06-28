# Competitor Analysis — 경쟁사 분석

경쟁사 웹사이트를 크롤링하고 로컬 LLM이 강약점·차별화 전략을 분석합니다.

## 설정 (competitor_analysis.json)

```json
{
  "COMPETITORS": [
    {"name": "경쟁사 A", "url": "https://example.com"},
    {"name": "경쟁사 B", "url": "https://example2.com"}
  ],
  "MY_PRODUCT": "Connect AI — 100% 로컬 AI 에이전트 VSCode 확장",
  "OLLAMA_URL": "http://127.0.0.1:11434",
  "MODEL": ""
}
```

## 실행

```bash
python competitor_analysis.py
```

## 출력

- 경쟁사별 강점·약점 비교표
- 시장 포지셔닝 분석
- 즉시 실행 가능한 차별화 전략 3가지
- 위험 요소 시나리오

파일: `competitor_analysis_report.md`
