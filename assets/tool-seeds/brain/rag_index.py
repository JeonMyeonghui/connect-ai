#!/usr/bin/env python3
"""RAG Index — Brain 폴더의 .md 파일을 청킹·임베딩해서 벡터 인덱스 생성.

text-embedding-nomic-embed-text-v1.5 (LM Studio) 또는
nomic-embed-text (Ollama) 사용.

설정: rag_config.json (brain 폴더 안에 자동 생성)
  EMBED_URL      : 임베딩 서버 (기본 http://127.0.0.1:1234)
  EMBED_MODEL    : 임베딩 모델 (기본 text-embedding-nomic-embed-text-v1.5)
  CHUNK_SIZE     : 청크 최대 글자 수 (기본 400)
  CHUNK_OVERLAP  : 청크 겹침 글자 수 (기본 80)
  BRAIN_PATH     : Brain 폴더 경로 (비우면 ~/.connect-ai-brain)

인덱스 저장: {BRAIN_PATH}/.rag-index/index.json
"""
import os, json, sys, time, math, urllib.request, urllib.parse, pathlib

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_EMBED_URL   = "http://127.0.0.1:1234"
DEFAULT_EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
DEFAULT_CHUNK_SIZE  = 400
DEFAULT_OVERLAP     = 80

# ── 설정 로드 ──────────────────────────────────────────────────────────────────
def get_brain_path(cfg: dict) -> str:
    raw = (cfg.get("BRAIN_PATH") or "").strip()
    if raw:
        return os.path.expanduser(raw)
    return os.path.join(pathlib.Path.home(), ".connect-ai-brain")

def load_config() -> dict:
    # rag_config.json은 brain 폴더 안에 위치 (Brain Pack과 같은 공간)
    # 첫 실행 시 brain 경로를 모르므로 HERE에 임시 생성 후 brain으로 이동
    tmp_cfg = os.path.join(HERE, "rag_config.json")
    if not os.path.exists(tmp_cfg):
        default = {
            "EMBED_URL":   DEFAULT_EMBED_URL,
            "EMBED_MODEL": DEFAULT_EMBED_MODEL,
            "CHUNK_SIZE":  DEFAULT_CHUNK_SIZE,
            "CHUNK_OVERLAP": DEFAULT_OVERLAP,
            "BRAIN_PATH":  ""
        }
        with open(tmp_cfg, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        print(f"⚙️  설정 파일 생성: {tmp_cfg}")
        print("   BRAIN_PATH를 입력하거나 비워두면 ~/.connect-ai-brain 사용.")
    with open(tmp_cfg, encoding="utf-8") as f:
        return json.load(f)

# ── 텍스트 청킹 ───────────────────────────────────────────────────────────────
def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """단락 우선 → 크기 초과 시 슬라이딩 윈도우."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, buf = [], ""
    for para in paragraphs:
        if len(buf) + len(para) + 2 <= size:
            buf = (buf + "\n\n" + para).strip()
        else:
            if buf:
                chunks.append(buf)
            # 단락 자체가 size 초과 → 슬라이딩
            if len(para) > size:
                for i in range(0, len(para), size - overlap):
                    chunks.append(para[i:i + size])
            else:
                buf = para
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) >= 20]  # 너무 짧은 조각 제외

# ── 임베딩 호출 ───────────────────────────────────────────────────────────────
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
        # Ollama: POST /api/embeddings
        payload = json.dumps({"model": model, "prompt": text}).encode()
        req = urllib.request.Request(f"{url}/api/embeddings", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["embedding"]

# ── 인덱스 빌드 ───────────────────────────────────────────────────────────────
def build_index(brain_path: str, embed_url: str, model: str,
                chunk_size: int, overlap: int) -> int:
    index_dir  = os.path.join(brain_path, ".rag-index")
    index_file = os.path.join(index_dir, "index.json")
    os.makedirs(index_dir, exist_ok=True)

    # 기존 인덱스 로드 (증분 업데이트용)
    existing: dict[str, dict] = {}
    if os.path.exists(index_file):
        try:
            with open(index_file, encoding="utf-8") as f:
                for entry in json.load(f):
                    key = f"{entry['file']}::{entry['chunk_id']}"
                    existing[key] = entry
        except Exception:
            pass

    # Brain 폴더에서 .md 파일 수집 (숨김 폴더 제외)
    md_files = []
    for root, dirs, files in os.walk(brain_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in files:
            if fn.endswith(".md"):
                md_files.append(os.path.join(root, fn))

    if not md_files:
        print(f"⚠️  {brain_path} 에서 .md 파일을 찾을 수 없습니다.")
        return 0

    print(f"📚 {len(md_files)}개 파일 처리 중...")
    entries, total_chunks, new_chunks = [], 0, 0

    for fpath in md_files:
        rel = os.path.relpath(fpath, brain_path)
        mtime = os.path.getmtime(fpath)
        try:
            with open(fpath, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception:
            continue

        chunks = chunk_text(text, chunk_size, overlap)
        for i, chunk in enumerate(chunks):
            total_chunks += 1
            key = f"{rel}::{i}"
            # mtime 변경 없으면 기존 임베딩 재사용
            if key in existing and existing[key].get("mtime") == mtime:
                entries.append(existing[key])
                continue
            try:
                vec = embed(chunk, embed_url, model)
                entries.append({
                    "file": rel, "chunk_id": i, "chunk": chunk,
                    "embedding": vec, "mtime": mtime
                })
                new_chunks += 1
            except Exception as e:
                print(f"   ⚠️  임베딩 실패 ({rel} #{i}): {e}")
            time.sleep(0.05)  # API 과부하 방지

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False)

    print(f"✅ 인덱스 완료 — 총 {total_chunks}개 청크 ({new_chunks}개 새로 임베딩)")
    print(f"   저장: {index_file}  ({os.path.getsize(index_file)//1024}KB)")
    return len(entries)

# ── 메인 ───────────────────────────────────────────────────────────────────────
def main():
    cfg        = load_config()
    brain_path = get_brain_path(cfg)
    embed_url  = (cfg.get("EMBED_URL") or DEFAULT_EMBED_URL).rstrip("/")
    model      = (cfg.get("EMBED_MODEL") or DEFAULT_EMBED_MODEL).strip()
    chunk_size = int(cfg.get("CHUNK_SIZE") or DEFAULT_CHUNK_SIZE)
    overlap    = int(cfg.get("CHUNK_OVERLAP") or DEFAULT_OVERLAP)

    if not os.path.isdir(brain_path):
        print(f"❌ Brain 폴더 없음: {brain_path}")
        print("   VS Code 설정에서 connectAiLab.localBrainPath를 확인하세요.")
        sys.exit(1)

    print(f"\n🧠 RAG 인덱스 빌드")
    print(f"   Brain: {brain_path}")
    print(f"   임베딩 서버: {embed_url} ({model})")
    print(f"   청크 크기: {chunk_size}자 (겹침 {overlap}자)")
    build_index(brain_path, embed_url, model, chunk_size, overlap)

if __name__ == "__main__":
    main()
