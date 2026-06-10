from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
import pandas as pd
from sentence_transformers import SentenceTransformer


# ----------------------------
# Paths / config
# ----------------------------

PROCESSED_DIR = Path("data/processed")
CHUNKS_JSONL = PROCESSED_DIR / "chunks.jsonl"

CHROMA_DIR = Path("data/chroma_db")
COLLECTION_NAME = "asu_offcampus_housing"

MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64
DEFAULT_TOP_K = 5
CANDIDATE_POOL = 20

# Keep this list aligned with the apartment names in your corpus.
KNOWN_PROPERTIES = [
    "University House",
    "The Emerson",
    "Emerson",
    "The Local",
    "Union Tempe",
    "Union",
    "Oliv",
    "Skye",
    "Skye at McClintock Station",
    "West 6",
    "West 6th",
    "District on Apache",
    "The District on Apache",
    "Paseo on University",
    "Rise",
    "Apollo",
    "Park Place",
    "The Access",
    "Canvas",
    "Vertex",
    "The Cameron",
    "Lakeside Drive",
    "Hyve",
    "Nexa",
    "The Piedmont",
    "Sol",
    "Redpoint",
    "Gateway",
    "Tempe Metro",
    "Atmosphere",
]

REVIEW_SOURCE_HINTS = {
    "reddit",
    "ratemyapartments",
    "apartmentratings",
    "birdeye",
}

GUIDE_SOURCE_HINTS = {
    "uhomes",
    "offcampus_universe",
    "off-campus universe",
    "guide",
    "collegepads",
    "apartments.com",
    "apartmentlist",
    "forrent",
    "asu_official",
    "offcampushousing",
}


# ----------------------------
# Loading / storage
# ----------------------------

def load_chunks(jsonl_path: Path) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if str(item.get("text", "")).strip():
                chunks.append(item)
    return chunks


def get_client() -> chromadb.PersistentClient:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection(client: chromadb.PersistentClient):
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def build_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    source_file = str(item.get("source_file", "")).lower()
    title = str(item.get("title", "")).lower()

    if "reddit" in source_file or "source: reddit" in title:
        source_type = "reddit"
    elif any(hint in source_file for hint in ["birdeye", "ratemyapartments", "apartmentratings"]):
        source_type = "review"
    elif any(hint in source_file for hint in ["guide", "uhomes", "collegepads", "apartments_com", "apartmentlist", "forrent"]):
        source_type = "guide"
    else:
        source_type = "listing"

    return {
        "source_file": str(item.get("source_file", "")),
        "title": str(item.get("title", "")),
        "chunk_id": str(item.get("chunk_id", "")),
        "chunk_index": int(item.get("chunk_index", 0)),
        "char_count": int(item.get("char_count", 0)),
        "word_count": int(item.get("word_count", 0)),
        "token_estimate": int(item.get("token_estimate", 0)),
        "source_type": source_type,
    }


def clear_collection(collection) -> None:
    try:
        collection.delete()
    except Exception:
        pass


def build_vector_store() -> None:
    if not CHUNKS_JSONL.exists():
        raise FileNotFoundError(
            f"Missing {CHUNKS_JSONL}. Run your document pipeline first."
        )

    print(f"Loading embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    chunks = load_chunks(CHUNKS_JSONL)
    if not chunks:
        raise ValueError("No chunks found in chunks.jsonl")

    client = get_client()
    collection = get_collection(client)
    clear_collection(collection)
    collection = get_collection(client)

    ids: List[str] = []
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for item in chunks:
        ids.append(str(item["chunk_id"]))
        texts.append(str(item["text"]))
        metadatas.append(build_metadata(item))

    print(f"Embedding {len(texts)} chunks...")

    for start in range(0, len(texts), BATCH_SIZE):
        end = min(start + BATCH_SIZE, len(texts))
        batch_texts = texts[start:end]
        batch_ids = ids[start:end]
        batch_meta = metadatas[start:end]

        embeddings = model.encode(
            batch_texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            metadatas=batch_meta,
            embeddings=embeddings,
        )

        print(f"Added chunks {start + 1}-{end}")

    print("\nVector store build complete.")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Storage path: {CHROMA_DIR.resolve()}")


# ----------------------------
# Retrieval helpers
# ----------------------------

def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_property_name(query: str) -> Optional[str]:
    q = normalize_for_match(query)
    for name in sorted(KNOWN_PROPERTIES, key=len, reverse=True):
        if normalize_for_match(name) in q:
            return name
    return None


def is_opinion_query(query: str) -> bool:
    q = query.lower()
    opinion_markers = [
        "what do students say about",
        "what do people say about",
        "what do people think about",
        "what do students think about",
        "is ",
        "are ",
        "should i avoid",
        "worth it",
        "recommend",
        "good apartment",
        "bad apartment",
        "reviews",
        "horror stories",
        "how is",
        "how are",
    ]
    return any(marker in q for marker in opinion_markers)


def source_type_allowed_for_query(source_type: str, query: str) -> bool:
    """
    Opinion questions should prefer review/reddit chunks.
    Generic apartment-finding questions can use any source.
    """
    if not is_opinion_query(query):
        return True

    return source_type in {"reddit", "review"}


def rerank_results(query: str, raw_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    target = extract_property_name(query)
    opinion_mode = is_opinion_query(query)

    scored: List[Dict[str, Any]] = []

    ids = raw_results.get("ids", [[]])[0]
    docs = raw_results.get("documents", [[]])[0]
    metas = raw_results.get("metadatas", [[]])[0]
    dists = raw_results.get("distances", [[]])[0]

    for i in range(len(ids)):
        text = str(docs[i])
        meta = metas[i] or {}
        dist = float(dists[i])
        source_type = str(meta.get("source_type", "listing")).lower()
        source_file = str(meta.get("source_file", "")).lower()
        title = str(meta.get("title", "")).lower()
        full_text = f"{title} {text}".lower()

        # Start with cosine distance from Chroma (lower is better)
        score = dist

        # Strong boost for exact apartment/property matches
        if target and normalize_for_match(target) in normalize_for_match(full_text):
            score -= 0.22

        # Prefer review/reddit sources for opinion questions
        if opinion_mode:
            if source_type in {"reddit", "review"}:
                score -= 0.10
            else:
                score += 0.10

        # Light bonus if the source file suggests the right apartment-related source
        if target:
            target_norm = normalize_for_match(target)
            if target_norm in source_file or target_norm in title:
                score -= 0.05

        scored.append(
            {
                "rank": i + 1,
                "id": ids[i],
                "distance": dist,
                "score": score,
                "text": text,
                "metadata": meta,
            }
        )

    # Sort by the custom rerank score, not just raw distance
    scored.sort(key=lambda x: x["score"])
    return scored


def retrieve(query: str, top_k: int = DEFAULT_TOP_K, candidate_k: int = CANDIDATE_POOL) -> List[Dict[str, Any]]:
    if not CHUNKS_JSONL.exists():
        raise FileNotFoundError(f"Missing {CHUNKS_JSONL}. Build your chunks first.")

    model = SentenceTransformer(MODEL_NAME)
    client = get_client()
    collection = get_collection(client)

    q_emb = model.encode([query], normalize_embeddings=True).tolist()[0]

    raw = collection.query(
        query_embeddings=[q_emb],
        n_results=candidate_k,
        include=["documents", "metadatas", "distances"],
    )

    reranked = rerank_results(query, raw)

    # Optional source filtering for opinion questions:
    # keep only review/reddit chunks if possible; if that yields nothing, fall back.
    if is_opinion_query(query):
        filtered = [hit for hit in reranked if source_type_allowed_for_query(str(hit["metadata"].get("source_type", "listing")), query)]
        if filtered:
            reranked = filtered

    return reranked[:top_k]


# ----------------------------
# Display / testing
# ----------------------------

def print_results(query: str, top_k: int = DEFAULT_TOP_K, candidate_k: int = CANDIDATE_POOL) -> None:
    hits = retrieve(query, top_k=top_k, candidate_k=candidate_k)

    print("\n" + "=" * 100)
    print(f"QUERY: {query}")
    print("=" * 100)

    if not hits:
        print("No results found.")
        return

    for hit in hits:
        meta = hit["metadata"]
        print(f"\nRank: {hit['rank']}")
        print(f"Distance: {hit['distance']:.4f}")
        print(f"Rerank score: {hit['score']:.4f}")
        print(f"Source: {meta.get('source_file', '')}")
        print(f"Source type: {meta.get('source_type', '')}")
        print(f"Title: {meta.get('title', '')}")
        print(f"Chunk ID: {meta.get('chunk_id', '')}")
        print("Text:")
        print(hit["text"])
        print("-" * 100)


def run_test_queries(top_k: int = DEFAULT_TOP_K) -> None:
    queries = [
        "What do students say about University House Tempe?",
        "Which apartments have the worst management?",
        "What apartments do students recommend near ASU?",
    ]

    for q in queries:
        print_results(q, top_k=top_k)


def export_results_csv(query: str, top_k: int = DEFAULT_TOP_K, candidate_k: int = CANDIDATE_POOL, output_path: Optional[Path] = None) -> None:
    hits = retrieve(query, top_k=top_k, candidate_k=candidate_k)
    rows: List[Dict[str, Any]] = []

    for hit in hits:
        meta = hit["metadata"]
        rows.append(
            {
                "query": query,
                "rank": hit["rank"],
                "distance": hit["distance"],
                "rerank_score": hit["score"],
                "source_file": meta.get("source_file", ""),
                "source_type": meta.get("source_type", ""),
                "title": meta.get("title", ""),
                "chunk_id": hit["id"],
                "chunk_index": meta.get("chunk_index", ""),
                "text": hit["text"],
            }
        )

    df = pd.DataFrame(rows)
    if output_path is None:
        output_path = Path("retrieval_results.csv")
    df.to_csv(output_path, index=False)
    print(f"Saved retrieval results to {output_path}")


# ----------------------------
# CLI
# ----------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build and query a ChromaDB vector store for ASU housing.")
    parser.add_argument("mode", choices=["build", "query", "test"], help="build = embed chunks, query = one query, test = sample queries")
    parser.add_argument("--query", type=str, default=None, help="Query text for query mode.")
    parser.add_argument("--top_k", type=int, default=DEFAULT_TOP_K, help="Number of chunks to return.")
    parser.add_argument("--candidate_k", type=int, default=CANDIDATE_POOL, help="Number of initial candidates to rerank.")
    parser.add_argument("--export_csv", action="store_true", help="Save retrieved results to CSV in query mode.")
    args = parser.parse_args()

    if args.mode == "build":
        build_vector_store()

    elif args.mode == "query":
        if not args.query:
            raise ValueError("Provide --query when using query mode.")
        print_results(args.query, top_k=args.top_k, candidate_k=args.candidate_k)
        if args.export_csv:
            export_results_csv(args.query, top_k=args.top_k, candidate_k=args.candidate_k)

    elif args.mode == "test":
        run_test_queries(top_k=args.top_k)


if __name__ == "__main__":
    main()