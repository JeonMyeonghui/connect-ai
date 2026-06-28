# Brain RAG 도구

Second Brain(.md 파일들)을 벡터 인덱스화하고 의미 검색을 제공합니다.  
`text-embedding-nomic-embed-text-v1.5` (LM Studio) 또는 `nomic-embed-text` (Ollama) 사용.

## 도구 목록

| 파일 | 기능 |
|------|------|
| `rag_index.py` | Brain .md 파일 → 청킹 → 벡터 인덱스 생성 |
| `rag_search.py` | 질문 → 유사 청크 TOP-K → LLM 답변 |

## 설치 및 설정 순서

### 1. rag_index.py 최초 실행 (인덱스 생성)
```bash
python rag_index.py
# → rag_config.json 생성 → BRAIN_PATH 입력(비우면 자동) → 재실행
```

### 2. 검색
```bash
python rag_search.py "MrBeast 전략에서 핵심 포인트가 뭐야?"
python rag_search.py "유튜브 알고리즘" --top 3
python rag_search.py "AI 에이전트" --no-llm   # LLM 없이 청크만
```

## rag_config.json 설정

```json
{
  "EMBED_URL":   "http://127.0.0.1:1234",
  "EMBED_MODEL": "text-embedding-nomic-embed-text-v1.5",
  "LLM_URL":     "http://127.0.0.1:11434",
  "LLM_MODEL":   "",
  "CHUNK_SIZE":  400,
  "CHUNK_OVERLAP": 80,
  "TOP_K":       5,
  "BRAIN_PATH":  ""
}
```

## Connect AI 채팅에서 사용

에이전트가 자동으로 `<search_brain>` 태그를 사용:
```
사용자: "내 브레인에서 MrBeast 관련 내용 찾아줘"
AI: <search_brain>MrBeast 콘텐츠 전략</search_brain>
→ RAG 검색 → 관련 청크 → 답변 생성
```

## 인덱스 업데이트

Brain에 새 파일이 추가되면 재실행 (변경된 파일만 재임베딩):
```bash
python rag_index.py
```

인덱스 위치: `{BRAIN_PATH}/.rag-index/index.json`
