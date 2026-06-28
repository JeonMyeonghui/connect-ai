#!/usr/bin/env python3
"""RAG Search — Brain 인덱스에서 유사 청크를 검색하고 LLM이 답변 생성.

사용법:
  python rag_search.py "질문"
  python rag_search.py "질문" --top 5
  python rag_search.py "질문" --no-llm   # 검색 결과만 (LLM 없이)

설정: rag_config.json (rag_index.py와 공유)
  추가 설정:
  LLM_URL        : LLM 서버 (기본 http://127.0.0.1:11434)
  LLM_MODEL      : LLM 모델 (비우면 자동)
  TOP_K          : 가져올 청크 수 (기본 5)
"""
import os, json, sys, math, urllib.request, pathlib, argparse

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_EMBED_URL   = "http://127.0.0.1:1234"
DEFAULT_EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
DEFAULT_LLM_URL     = "http://127.0.0.1:11434"
DEFAULT_TOP_K       = 5

# ── 설정 ───────────────────────────────────────────────────────────────────────
def get_brain_path(cfg: dict) -> str:
    raw = (cfg.get("BRAIN_PATH") or "").strip()
    return os.path.expanduser(raw) if raw else os.path.join(pathlib.Path.home(), ".connect-ai-brain")

def load_config() -> dict:
    cfg_path = os.path.join(HERE, "rag_config.json")
    if not os.path.exists(cfg_path):
        print("⚠️  rag_config.json 없음. rag_index.py를 먼저 실행하세요.")
        sys.exit(1)
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)

# ── 벡터 연산 (순수 Python, numpy 불필요) ────────────────────────────────────
def cosine_sim(a: list[float], b: list[float]) -> float:
    dot  = sum(x * y for x, y in zip(a, b))
    mag  = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    return dot / mag if mag else 0.0

# ── 임베딩 ────────────────────────────────────────────────────────────────────
def embed(text: str, url: str, model: str) -> list[float]:
    is_lm = "1234" in url or "/v1" in url
    if is_lm:
        base = url.rstrip("/")
        if not base.endswith("/v1"): base += "/v1"
        payload = json.dumps({"model": model, "input": text}).encode()
        req = urllib.request.Request(f"{base}/embeddings", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["data"][0]["embedding"]
    else:
        payload = json.dumps({"model": model, "prompt": text}).encode()
        req = urllib.request.Request(f"{url}/api/embeddings", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["embedding"]

# ── 인덱스 검색 ───────────────────────────────────────────────────────────────
def search(query: str, brain_path: str, embed_url: str, embed_model: str,
           top_k: int) -> list[dict]:
    index_file = os.path.join(brain_path, ".rag-index", "index.json")
    if not os.path.exists(index_file):
        print("❌ 인덱스 없음. rag_index.py를 먼저 실행하세요.")
        sys.exit(1)

    with open(index_file, encoding="utf-8") as f:
        index = json.load(f)

    if not index:
        print("⚠️  인덱스가 비어있습니다."); sys.exit(1)

    q_vec = embed(query, embed_url, embed_model)
    scored = [(cosine_sim(q_vec, e["embedding"]), e) for e in index]
    scored.sort(key=lambda x: -x[0])
    return [{"score": s, **e} for s, e in scored[:top_k]]

# ── LLM 답변 생성 ─────────────────────────────────────────────────────────────
def ask_llm(query: str, chunks: list[dict], llm_url: str, llm_model: str) -> str:
    is_lm = "1234" in llm_url or "/v1" in llm_url

    if not llm_model:
        try:
            ep = f"{llm_url}/v1/models" if is_lm else f"{llm_url}/api/tags"
            with urllib.request.urlopen(ep, timeout=5) as r:
                data = json.loads(r.read())
            llm_model = data["data"][0]["id"] if is_lm else data["models"][0]["name"]
        except Exception:
            print("❌ LLM 모델 자동 선택 실패."); sys.exit(1)

    context = "\n\n---\n\n".join(
        f"[출처: {c['file']}] (유사도: {c['score']:.3f})\n{c['chunk']}"
        for c in chunks
    )
    prompt = f"""당신은 사용자의 개인 지식 베이스(Second Brain)에서 답변을 찾아주는 AI 어시스턴트입니다.
아래 검색된 관련 문서를 바탕으로 질문에 답하세요.
문서에 없는 내용은 "제 지식 베이스에서 관련 내용을 찾지 못했습니다"라고 솔직히 말하세요.

질문: {query}

관련 문서:
{context}

답변 (출처 파일명을 [파일명] 형태로 인용하며 작성):"""

    if is_lm:
        base = llm_url.rstrip("/")
        if not base.endswith("/v1"): base += "/v1"
        payload = json.dumps({"model": llm_model,
                               "messages": [{"role": "user", "content": prompt}],
                               "stream": False, "max_tokens": 2000}).encode()
        req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                     headers={"Content-Type": "application/json"})
    else:
        payload = json.dumps({"model": llm_model, "prompt": prompt,
                              "stream": False}).encode()
        req = urllib.request.Request(f"{llm_url}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
        return (data["choices"][0]["message"]["content"] if is_lm else data["response"]).strip()

# ── 메인 ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="RAG Brain Search")
    parser.add_argument("query", nargs="?", default="", help="검색 질문")
    parser.add_argument("--top", type=int, default=0, help="TOP-K 결과 수")
    parser.add_argument("--no-llm", action="store_true", help="LLM 없이 검색 결과만")
    args = parser.parse_args()

    cfg        = load_config()
    brain_path = get_brain_path(cfg)
    embed_url  = (cfg.get("EMBED_URL")   or DEFAULT_EMBED_URL).rstrip("/")
    embed_model= (cfg.get("EMBED_MODEL") or DEFAULT_EMBED_MODEL).strip()
    llm_url    = (cfg.get("LLM_URL")     or DEFAULT_LLM_URL).rstrip("/")
    llm_model  = (cfg.get("LLM_MODEL")   or "").strip()
    top_k      = args.top or int(cfg.get("TOP_K") or DEFAULT_TOP_K)

    query = args.query.strip()
    if not query:
        query = input("🔍 질문: ").strip()
    if not query:
        print("⚠️  질문을 입력하세요."); sys.exit(1)

    print(f"\n🔍 검색: {query}")
    results = search(query, brain_path, embed_url, embed_model, top_k)

    print(f"\n📄 관련 문서 TOP {len(results)}")
    print("─" * 60)
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r['file']}  (유사도: {r['score']:.3f})")
        print(f"    {r['chunk'][:120].replace(chr(10),' ')}...")
    print("─" * 60)

    if not args.no_llm:
        print(f"\n🧠 LLM 답변 생성 중...")
        answer = ask_llm(query, results, llm_url, llm_model)
        print(f"\n{'=' * 60}")
        print(answer)
        print('=' * 60)

if __name__ == "__main__":
    main()
