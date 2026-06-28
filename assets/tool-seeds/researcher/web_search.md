# Web Search — 웹 검색 + LLM 분석

DuckDuckGo로 웹 검색 후 로컬 LLM이 핵심 인사이트 보고서를 작성합니다.  
**API 키 불필요.** 완전 오프라인 (검색만 인터넷 사용).

## 설정 (web_search.json)

처음 실행하면 자동으로 생성됩니다. 이후 수정:

```json
{
  "QUERY": "AI 에이전트 최신 트렌드 2026",
  "MAX_RESULTS": 10,
  "OLLAMA_URL": "http://127.0.0.1:11434",
  "MODEL": "",
  "LANGUAGE": "Korean"
}
```

| 항목 | 설명 | 기본값 |
|------|------|--------|
| `QUERY` | 검색어 (필수) | — |
| `MAX_RESULTS` | 가져올 결과 수 | 10 |
| `OLLAMA_URL` | LLM 서버 주소 | 11434 (Ollama) |
| `MODEL` | 모델명 (비우면 자동) | 자동 선택 |
| `LANGUAGE` | 보고서 언어 | Korean |

## 실행

```bash
python web_search.py
```

## 출력

- 콘솔: 분석 보고서 즉시 출력
- 파일: `web_search_report.md` (누적 저장)

보고서 구조:
1. 🔍 핵심 요약
2. 📊 주요 발견사항
3. 💡 실행 가능한 인사이트
4. 🔗 참고 소스

## 필요 패키지

표준 라이브러리만 사용 (pip install 불필요).
