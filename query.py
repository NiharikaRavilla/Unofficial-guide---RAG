from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from groq import Groq

from build_vector_store import retrieve  # uses your ChromaDB retriever


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing. Put it in your .env file.")

client = Groq(api_key=GROQ_API_KEY)

MODEL_NAME = "llama-3.3-70b-versatile"
REFUSAL_TEXT = "I don't have enough information in the provided documents."

# Lower distance = better. Tune this after you inspect real retrieval results.
MAX_ACCEPTABLE_DISTANCE = 0.62


def is_opinion_query(question: str) -> bool:
    q = question.lower()
    markers = [
        "what do students say",
        "what do people say",
        "what do students think",
        "what do people think",
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
    return any(m in q for m in markers)


def normalize_name(path_str: str) -> str:
    return Path(path_str).name


def unique_sources(hits: List[Dict[str, Any]]) -> List[str]:
    sources: List[str] = []
    seen = set()
    for hit in hits:
        meta = hit.get("metadata", {})
        source_file = normalize_name(str(meta.get("source_file", "")))
        title = str(meta.get("title", "")).strip()
        label = f"{source_file}" if not title else f"{source_file} ({title})"
        if label not in seen:
            seen.add(label)
            sources.append(label)
    return sources


def build_context(hits: List[Dict[str, Any]]) -> str:
    blocks: List[str] = []
    for i, hit in enumerate(hits, start=1):
        meta = hit.get("metadata", {})
        source_file = normalize_name(str(meta.get("source_file", "")))
        title = str(meta.get("title", "")).strip()
        chunk_id = str(hit.get("id", meta.get("chunk_id", "")))
        distance = float(hit.get("distance", 0.0))

        blocks.append(
            f"[{i}] source_file: {source_file}\n"
            f"title: {title}\n"
            f"chunk_id: {chunk_id}\n"
            f"distance: {distance:.4f}\n"
            f"text:\n{hit.get('text', '').strip()}"
        )
    return "\n\n".join(blocks)


def should_refuse(question: str, hits: List[Dict[str, Any]]) -> bool:
    if not hits:
        return True

    best_distance = min(float(h.get("distance", 1.0)) for h in hits)
    if best_distance > MAX_ACCEPTABLE_DISTANCE:
        return True

    # For opinion-style questions, prefer evidence from Reddit/reviews.
    if is_opinion_query(question):
        review_like = any(
            str(h.get("metadata", {}).get("source_type", "")).lower() in {"reddit", "review"}
            for h in hits
        )
        if not review_like:
            return True

    return False


def ask(question: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Returns:
        {
            "answer": str,
            "sources": [str, ...],
            "retrieved": [hit, ...]
        }
    """
    hits = retrieve(question, top_k=top_k, candidate_k=20)

    # If retrieval is weak, refuse before generation.
    if should_refuse(question, hits):
        return {
            "answer": REFUSAL_TEXT,
            "sources": unique_sources(hits),
            "retrieved": hits,
        }

    context = build_context(hits)

    system_prompt = (
        "You are a grounded assistant for an ASU off-campus housing RAG system.\n"
        "Answer using ONLY the provided documents.\n"
        "Do NOT use outside knowledge.\n"
        "Do NOT guess.\n"
        "If the documents do not contain enough information to answer, reply with exactly:\n"
        f"{REFUSAL_TEXT}\n"
        "Keep the answer concise and factual."
    )

    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Retrieved documents:\n{context}\n\n"
        "Write the best answer you can using only the retrieved documents."
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )

    answer = (response.choices[0].message.content or "").strip()

    # Final safety check: if the model drifted, force refusal.
    if not answer:
        answer = REFUSAL_TEXT

    return {
        "answer": answer,
        "sources": unique_sources(hits),
        "retrieved": hits,
    }