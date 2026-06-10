from __future__ import annotations

import csv
import html
import json
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")
CHUNKS_JSONL = OUT_DIR / "chunks.jsonl"
CHUNK_STATS_CSV = OUT_DIR / "chunk_stats.csv"
CHUNK_PREVIEW_TXT = OUT_DIR / "chunk_preview.txt"

MAX_TOKENS = 450
MIN_TOKENS = 120
OVERLAP_TOKENS = 60
RANDOM_PREVIEW_COUNT = 5


@dataclass
class Chunk:
    chunk_id: str
    source_file: str
    title: str
    chunk_index: int
    text: str
    char_count: int
    word_count: int
    token_estimate: int


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def approx_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def read_document(path: Path) -> str:
    return normalize_text(path.read_text(encoding="utf-8", errors="ignore"))


def split_header_and_body(text: str, fallback_title: str) -> Tuple[str, str]:
    lines = text.splitlines()
    title = fallback_title

    body_start = 0
    for i, line in enumerate(lines[:20]):
        s = line.strip()
        if s.startswith("TITLE:"):
            title = s.replace("TITLE:", "").strip()
        elif s.startswith("SOURCE_URL:") or s.startswith("SOURCE:") or s.startswith("DOC_TYPE:"):
            continue
        elif s == "":
            body_start = i + 1
            break

    body = "\n".join(lines[body_start:]).strip()

    # Remove any leftover metadata lines from the body
    body_lines = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("TITLE:") or s.startswith("SOURCE:") or s.startswith("SOURCE_URL:") or s.startswith("DOC_TYPE:"):
            continue
        body_lines.append(line)

    body = normalize_text("\n".join(body_lines))
    return title, body


def is_reddit_document(path: Path, text: str) -> bool:
    name = path.name.lower()
    head = "\n".join(text.splitlines()[:15]).lower()
    return "reddit" in name or "source: reddit" in head or "subreddit" in head


def remove_reddit_ui_lines(text: str) -> str:
    ui_patterns = [
        r"^upvote$",
        r"^downvote$",
        r"^reply$",
        r"^share$",
        r"^award$",
        r"^promoted$",
        r"^go to comments$",
        r"^join the conversation$",
        r"^sort by:.*$",
        r"^search comments$",
        r"^expand comment search$",
        r"^comments section$",
        r"^collapse video player$",
        r"^clickable image which will reveal the video player:.*$",
        r"^the file is too long and its contents have been truncated\.$",
    ]

    cleaned = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            cleaned.append("")
            continue

        if any(re.match(p, s, flags=re.IGNORECASE) for p in ui_patterns):
            continue

        # Remove ad / platform noise
        if "promoted" in s.lower():
            continue
        if s.startswith("u/") and "avatar" in s.lower():
            continue

        cleaned.append(line)

    return normalize_text("\n".join(cleaned))


def extract_comment_blocks(text: str) -> List[str]:
    """
    Split Reddit text into comment-sized blocks using user markers.
    """
    text = remove_reddit_ui_lines(text)
    lines = text.splitlines()

    markers = (
        "user:",
        "u/",
        "[deleted]",
        "comment:",
        "comments",
        "post",
        "discussion",
        "apartment:",
    )

    blocks = []
    current = []

    def flush():
        nonlocal current
        block = normalize_text("\n".join(current))
        if block:
            blocks.append(block)
        current = []

    for line in lines:
        s = line.strip()

        if s == "---":
            flush()
            continue

        if s.lower().startswith(markers):
            flush()
            current.append(line)
            continue

        current.append(line)

    flush()
    return [b for b in blocks if b.strip()]


def merge_small_blocks(blocks: List[str], min_tokens: int, max_tokens: int) -> List[str]:
    """
    Merge small blocks with neighbors until they are meaningful.
    """
    if not blocks:
        return []

    merged: List[str] = []
    buffer = ""

    def push_buffer():
        nonlocal buffer
        txt = normalize_text(buffer)
        if txt:
            merged.append(txt)
        buffer = ""

    for block in blocks:
        tok = approx_tokens(block)

        if not buffer:
            buffer = block
            continue

        candidate = normalize_text(buffer + "\n\n" + block)
        if approx_tokens(candidate) <= max_tokens:
            buffer = candidate
        else:
            # If buffer is too small, keep merging until useful
            if approx_tokens(buffer) < min_tokens and tok < min_tokens:
                buffer = candidate
            else:
                push_buffer()
                buffer = block

    push_buffer()

    # Second pass: merge any leftover tiny chunks with following chunk
    final_chunks: List[str] = []
    i = 0
    while i < len(merged):
        current = merged[i]
        if approx_tokens(current) < min_tokens and i + 1 < len(merged):
            combined = normalize_text(current + "\n\n" + merged[i + 1])
            if approx_tokens(combined) <= max_tokens:
                final_chunks.append(combined)
                i += 2
                continue
        final_chunks.append(current)
        i += 1

    return [c for c in final_chunks if c.strip()]


def chunk_by_tokens(text: str, max_tokens: int, overlap_tokens: int) -> List[str]:
    words = text.split()
    if not words:
        return []

    max_words = max(1, int(max_tokens * 0.75))
    overlap_words = max(0, int(overlap_tokens * 0.75))

    chunks = []
    start = 0
    while start < len(words):
        end = min(len(words), start + max_words)
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
        start = max(0, end - overlap_words)

    return chunks


def chunk_reddit_document(text: str, max_tokens: int, min_tokens: int, overlap_tokens: int) -> List[str]:
    blocks = extract_comment_blocks(text)

    # Merge short comment blocks so they are not tiny fragments
    blocks = merge_small_blocks(blocks, min_tokens=min_tokens, max_tokens=max_tokens)

    final_chunks: List[str] = []
    for block in blocks:
        tok = approx_tokens(block)
        if tok <= max_tokens:
            final_chunks.append(block)
        else:
            final_chunks.extend(chunk_by_tokens(block, max_tokens, overlap_tokens))

    return [c for c in final_chunks if c.strip()]


def split_paragraph_blocks(text: str) -> List[str]:
    blocks = re.split(r"\n\s*\n+", text)
    return [normalize_text(b) for b in blocks if normalize_text(b)]


def chunk_nonreddit_document(text: str, max_tokens: int, min_tokens: int, overlap_tokens: int) -> List[str]:
    blocks = split_paragraph_blocks(text)

    chunks: List[str] = []
    current: List[str] = []
    current_tokens = 0

    def flush_current():
        nonlocal current, current_tokens
        if current:
            chunks.append(normalize_text("\n\n".join(current)))
        current = []
        current_tokens = 0

    for block in blocks:
        tok = approx_tokens(block)

        if tok > max_tokens:
            flush_current()
            chunks.extend(chunk_by_tokens(block, max_tokens, overlap_tokens))
            continue

        if current and current_tokens + tok > max_tokens:
            flush_current()

        current.append(block)
        current_tokens += tok

    flush_current()

    # Remove tiny chunks by merging with the next one
    final_chunks: List[str] = []
    i = 0
    while i < len(chunks):
        current = chunks[i]
        if approx_tokens(current) < min_tokens and i + 1 < len(chunks):
            combined = normalize_text(current + "\n\n" + chunks[i + 1])
            if approx_tokens(combined) <= max_tokens:
                final_chunks.append(combined)
                i += 2
                continue
        final_chunks.append(current)
        i += 1

    return [c for c in final_chunks if c.strip()]


def build_chunks_for_document(path: Path) -> List[str]:
    raw = read_document(path)
    title, body = split_header_and_body(raw, path.stem)

    if not body.strip():
        return []

    if is_reddit_document(path, raw):
        return chunk_reddit_document(body, MAX_TOKENS, MIN_TOKENS, OVERLAP_TOKENS)

    return chunk_nonreddit_document(body, MAX_TOKENS, MIN_TOKENS, OVERLAP_TOKENS)


def make_chunk_objects(path: Path, chunks: List[str]) -> List[Chunk]:
    raw = read_document(path)
    title, _ = split_header_and_body(raw, path.stem)

    objs: List[Chunk] = []
    for idx, chunk_text in enumerate(chunks):
        chunk_text = normalize_text(chunk_text)
        if not chunk_text:
            continue

        objs.append(
            Chunk(
                chunk_id=f"{path.stem}__{idx:04d}",
                source_file=str(path.relative_to(RAW_DIR)).replace("\\", "/"),
                title=title,
                chunk_index=idx,
                text=chunk_text,
                char_count=len(chunk_text),
                word_count=len(chunk_text.split()),
                token_estimate=approx_tokens(chunk_text),
            )
        )
    return objs


def save_jsonl(chunks: List[Chunk], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.__dict__, ensure_ascii=False) + "\n")


def save_csv(chunks: List[Chunk], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "chunk_id",
                "source_file",
                "title",
                "chunk_index",
                "char_count",
                "word_count",
                "token_estimate",
            ],
        )
        writer.writeheader()
        for chunk in chunks:
            writer.writerow(
                {
                    "chunk_id": chunk.chunk_id,
                    "source_file": chunk.source_file,
                    "title": chunk.title,
                    "chunk_index": chunk.chunk_index,
                    "char_count": chunk.char_count,
                    "word_count": chunk.word_count,
                    "token_estimate": chunk.token_estimate,
                }
            )


def print_preview(chunks: List[Chunk], count: int = 5) -> None:
    sample = random.sample(chunks, k=min(count, len(chunks)))

    print("\n" + "=" * 80)
    print(f"RANDOM CHUNK PREVIEW ({len(sample)} chunks)")
    print("=" * 80)

    preview = []
    for i, chunk in enumerate(sample, start=1):
        block = (
            f"\n--- SAMPLE {i} ---\n"
            f"chunk_id: {chunk.chunk_id}\n"
            f"source_file: {chunk.source_file}\n"
            f"title: {chunk.title}\n"
            f"tokens_est: {chunk.token_estimate}\n"
            f"text:\n{chunk.text}\n"
        )
        print(block)
        preview.append(block)

    CHUNK_PREVIEW_TXT.write_text("\n".join(preview), encoding="utf-8")


def main() -> None:
    ensure_dirs()

    all_chunks: List[Chunk] = []
    doc_count = 0

    for path in sorted(RAW_DIR.rglob("*.txt")):
        doc_count += 1
        chunks = build_chunks_for_document(path)
        objs = make_chunk_objects(path, chunks)
        all_chunks.extend(objs)
        print(f"{path.name}: {len(objs)} chunks")

    if not all_chunks:
        print("No chunks created. Check your input files.")
        return

    save_jsonl(all_chunks, CHUNKS_JSONL)
    save_csv(all_chunks, CHUNK_STATS_CSV)
    print_preview(all_chunks, RANDOM_PREVIEW_COUNT)

    print("\n" + "=" * 80)
    print("CHUNKING SUMMARY")
    print("=" * 80)
    print(f"Documents processed: {doc_count}")
    print(f"Total chunks: {len(all_chunks)}")
    print(f"JSONL saved to: {CHUNKS_JSONL}")
    print(f"CSV saved to: {CHUNK_STATS_CSV}")
    print(f"Preview saved to: {CHUNK_PREVIEW_TXT}")


if __name__ == "__main__":
    main()