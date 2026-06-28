# Fact Check — 팩트체크

주장을 입력받아 웹 검색으로 근거를 수집하고 로컬 LLM이 진위를 판단합니다.

## 설정 (fact_check.json)

```json
{
  "CLAIMS": [
    "ChatGPT는 2022년 11월에 출시됐다",
    "한국의 유튜브 사용자는 5000만 명이다"
  ],
  "OLLAMA_URL": "http://127.0.0.1:11434",
  "MODEL": "",
  "SEARCH_PER_CLAIM": 5
}
```

## 실행

```bash
python fact_check.py
```

## 판정 기준

| 마커 | 의미 |
|------|------|
| ✅ 사실 | 검색 근거가 주장을 뒷받침 |
| ❌ 거짓 | 검색 근거가 주장을 반박 |
| ⚠️ 부분적 사실 | 일부만 맞거나 맥락 필요 |
| ❓ 확인 불가 | 신뢰할 근거 부족 |

파일: `fact_check_report.md`
