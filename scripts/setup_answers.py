"""
Setup script: chạy Day 18 pipeline trên 50 câu hỏi → lưu artifacts/answers_50q.json

Chạy TRƯỚC khi bắt đầu Phase A:
    python scripts/setup_answers.py --live

Yêu cầu:
    1. Có 5 module m1-m5 với giao diện trong doc/PIPELINE_INTERFACE.md
       Script tự lắp module; không gọi src/pipeline.py.
    2. docker compose -f infra/docker-compose.yml up -d  (Qdrant đang chạy trên port 6333)
    3. .env có OPENAI_API_KEY
"""
from __future__ import annotations

import json
import argparse
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ROOT_DIR, DATA_DIR, TEST_SET_PATH, ANSWERS_PATH, GENERATION_MODEL


def check_day18_files() -> bool:
    required = [
        "src/m1_chunking.py", "src/m2_search.py", "src/m3_rerank.py",
        "src/m4_eval.py",     "src/m5_enrichment.py",
    ]
    missing = [f for f in required if not os.path.exists(os.path.join(ROOT_DIR, f))]
    if missing:
        print("\n❌ Thiếu files từ Day 18. Copy chúng vào src/ trước:\n")
        for f in missing:
            print(f"   cp <Day18>/src/{os.path.basename(f)} src/")
        return False
    print(f"✓ Day 18 source files: {len(required)}/{len(required)} found")
    return True


def build_pipeline():
    # This assembler calls m1/m2/m3/m5 directly, NOT src.pipeline.py.
    from src.m1_chunking import load_documents, chunk_hierarchical
    from src.m2_search import HybridSearch
    from src.m3_rerank import CrossEncoderReranker
    from src.m5_enrichment import enrich_chunks
    from config import COLLECTION_NAME, RERANK_TOP_K

    print("\n[1/3] Chunking + enriching documents...")
    t0 = time.time()
    docs = load_documents()
    all_chunks = []
    for doc in docs:
        parents, children = chunk_hierarchical(doc["text"], metadata=doc["metadata"])
        for child in children:
            all_chunks.append({
                "text": child.text,
                "metadata": {**child.metadata, "parent_id": child.parent_id},
            })

    enriched = enrich_chunks(all_chunks)
    if enriched:
        if len(enriched) != len(all_chunks):
            raise ValueError("enrich_chunks must preserve chunk count/order; see doc/PIPELINE_INTERFACE.md")
        all_chunks = [{"text": e.enriched_text,
                       "metadata": {**original["metadata"], **e.auto_metadata}}
                      for original, e in zip(all_chunks, enriched)]
        print(f"  ✓ Enriched {len(enriched)} chunks ({time.time()-t0:.1f}s)")
    else:
        print(f"  ✓ Using {len(all_chunks)} raw chunks (M5 not implemented or no API key)")

    print("\n[2/3] Indexing (BM25 + Dense)...")
    t0 = time.time()
    search = HybridSearch()
    if os.getenv("DAY24_REUSE_DENSE_INDEX") == "1":
        search.bm25.index(all_chunks)
        client = search.dense.client
        count = client.count(COLLECTION_NAME, exact=True).count
        if count != len(all_chunks):
            raise ValueError(f"Stored dense index has {count} points, expected {len(all_chunks)}")
        edge_ids = [0, len(all_chunks) - 1]
        stored = {point.id: point.payload["text"] for point in client.retrieve(
            COLLECTION_NAME, ids=edge_ids, with_payload=True, with_vectors=False)}
        if any(stored.get(index) != all_chunks[index]["text"] for index in edge_ids):
            raise ValueError("Stored dense index differs from current corpus; reindex required")
        print(f"  Reused {count} matching Qdrant vectors; rebuilt BM25 in this process")
    else:
        search.index(all_chunks)
    print(f"  ✓ Indexed {len(all_chunks)} chunks ({time.time()-t0:.1f}s)")

    print("\n[3/3] Loading reranker...")
    t0 = time.time()
    reranker_kind = os.getenv("DAY24_RERANKER", "cross_encoder")
    if reranker_kind == "flashrank":
        from src.m3_rerank import FlashrankReranker
        reranker = FlashrankReranker()
    elif reranker_kind == "cross_encoder":
        reranker = CrossEncoderReranker()
    else:
        raise ValueError(f"Unknown DAY24_RERANKER: {reranker_kind}")
    print(f"  Reranker selected: {reranker_kind}")
    print(f"  ✓ Reranker ready ({time.time()-t0:.1f}s)")

    return search, reranker, RERANK_TOP_K


def run_query(q: str, search, reranker, top_k: int, client=None) -> tuple[str, list[str], str, str | None]:
    from config import OPENAI_API_KEY

    for attempt in range(3):
        try:
            results = search.search(q)
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    docs    = [{"text": r.text, "score": r.score, "metadata": r.metadata} for r in results]
    # Child chunks locate the document; use its complete local text as the
    # context so a table row or policy condition split across chunks is not lost.
    # The document must first be returned by search and ranked by the reranker.
    reranked = reranker.rerank(q, docs, top_k=max(top_k, 8))
    contexts = []
    seen_sources = set()
    for row in reranked:
        metadata = getattr(row, "metadata", None) or {}
        source = metadata.get("source")
        if source in seen_sources:
            continue
        if source and source == os.path.basename(source) and source.lower().endswith(".md"):
            path = os.path.join(DATA_DIR, source)
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as document:
                    contexts.append(f"Trích từ tài liệu {source}.\n\n{document.read()}")
                seen_sources.add(source)
            else:
                contexts.append(row.text)
        else:
            contexts.append(row.text)
        if len(contexts) >= top_k:
            break
    if not contexts:
        contexts = [r.text for r in results[:3]]

    if (OPENAI_API_KEY or client is not None) and contexts:
        try:
            if client is None:
                from openai import OpenAI
                client = OpenAI()
            ctx = "\n\n".join(contexts)
            from src.llm import _request_with_rate_limit
            resp = _request_with_rate_limit(client,
                model=GENERATION_MODEL,
                temperature=0,
                max_tokens=512,
                messages=[
                    {"role": "system", "content": "Trả lời CHỈ dựa trên context. Nếu không có → nói 'Không tìm thấy.'"},
                    {"role": "user",   "content": f"Context:\n{ctx}\n\nCâu hỏi: {q}"},
                ],
            )
            reported_model = getattr(resp, "model", None)
            used_model = reported_model if isinstance(reported_model, str) and reported_model.strip() else GENERATION_MODEL
            return resp.choices[0].message.content, contexts, "llm", used_model
        except Exception as e:
            print(f"  LLM generation failed: {type(e).__name__}; using extractive fallback.")

    return (contexts[0] if contexts else "Không tìm thấy thông tin."), contexts, "extractive_fallback", None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Assemble previous modules and generate 50 answers (API cost).")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("Generation/enrichment may call APIs. Pass --live after completing pre-class setup.")
    print("=" * 60)
    print("K4 / TRACK 3B SETUP — Generating answers for 50 questions")
    print("=" * 60)

    if not check_day18_files():
        sys.exit(1)

    with open(TEST_SET_PATH, encoding="utf-8") as f:
        test_set = json.load(f)
    print(f"✓ Loaded {len(test_set)} questions (factual/multi_hop/adversarial)")

    try:
        search, reranker, top_k = build_pipeline()
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        print("→ Đảm bảo bạn đã copy src/ từ Day 18 và đã pip install -r requirements/requirements.txt")
        sys.exit(1)

    print(f"\nRunning {len(test_set)} queries...")
    from config import COLLECTION_NAME, EMBEDDING_MODEL
    signature = hashlib.sha256(
        (open(__file__, "rb").read() + open(TEST_SET_PATH, "rb").read() +
         f"{COLLECTION_NAME}|{EMBEDDING_MODEL}|{GENERATION_MODEL}|{os.getenv('DAY24_RERANKER', 'cross_encoder')}".encode())
    ).hexdigest()
    partial_path = ANSWERS_PATH.removesuffix(".json") + ".partial.json"
    answers = []
    if os.path.isfile(partial_path):
        with open(partial_path, encoding="utf-8") as f:
            partial = json.load(f)
        if partial.get("signature") == signature:
            answers = partial.get("answers", [])
            print(f"Resuming {len(answers)} previously saved answers")
    from config import OPENAI_API_KEY
    client = None
    if OPENAI_API_KEY:
        from openai import OpenAI
        client = OpenAI()
    t_start = time.time()

    for i, item in enumerate(test_set):
        if i < len(answers):
            if answers[i]["id"] != item["id"]:
                raise ValueError("Partial answer IDs differ from the fixture")
            continue
        answer, contexts, generation_mode, generation_model = run_query(item["question"], search, reranker, top_k, client)
        answers.append({
            "id":           item["id"],
            "distribution": item["distribution"],
            "question":     item["question"],
            "answer":       answer,
            "contexts":     contexts,
            "ground_truth": item["ground_truth"],
            "generation_mode": generation_mode,
            "generation_model": generation_model,
        })
        os.makedirs(os.path.dirname(ANSWERS_PATH), exist_ok=True)
        temporary = partial_path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as f:
            json.dump({"signature": signature, "answers": answers}, f, ensure_ascii=False, indent=2)
        os.replace(temporary, partial_path)
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(test_set)}] done ({time.time()-t_start:.0f}s elapsed)")

    os.makedirs(os.path.dirname(ANSWERS_PATH), exist_ok=True)
    with open(ANSWERS_PATH, "w", encoding="utf-8") as f:
        json.dump(answers, f, ensure_ascii=False, indent=2)
    if os.path.isfile(partial_path):
        os.remove(partial_path)

    print(f"\n✓ Saved {len(answers)} answers → artifacts/answers_50q.json")
    print(f"  Total time: {time.time()-t_start:.1f}s")
    print("\n→ Bây giờ bắt đầu Phase A:")
    print("     python scripts/run_experiments.py --phase a --live")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
