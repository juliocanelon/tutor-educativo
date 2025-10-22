"""Lightweight retrieval helpers for the tutoring orchestrator."""
from __future__ import annotations

import math
import re
from typing import Dict, List, Tuple


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _tokenise(text: str) -> List[str]:
    return re.findall(r"\w+", text.lower())


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks: List[str] = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(words), step):
        chunk_words = words[start:start + chunk_size]
        chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break
    return chunks


def _score_chunk(chunk: str, query_tokens: List[str]) -> float:
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokenise(chunk)
    if not chunk_tokens:
        return 0.0
    hits = sum(chunk_tokens.count(token) for token in query_tokens)
    if hits == 0:
        return 0.0
    # Inverse length factor to prefer concise passages
    return hits / math.sqrt(len(chunk_tokens))


def build_context(book_text: str, query: str | None = None, max_chars: int = 1800) -> Dict[str, str]:
    """Return a relevant context window and anchor snippet for a query."""
    cleaned_text = _normalise(book_text)
    if not cleaned_text:
        return {"context": "", "anchor": ""}

    query_tokens = _tokenise(query or "")

    if not query_tokens:
        excerpt = cleaned_text[:max_chars]
        return {"context": excerpt, "anchor": excerpt[:300]}

    candidate_chunks = _chunk_text(cleaned_text, chunk_size=220, overlap=40)
    if not candidate_chunks:
        candidate_chunks = [cleaned_text[:max_chars]]

    scored_chunks: List[Tuple[float, str]] = [
        (_score_chunk(chunk, query_tokens), chunk) for chunk in candidate_chunks
    ]

    scored_chunks.sort(key=lambda item: item[0], reverse=True)

    best_chunks = [chunk for score, chunk in scored_chunks if score > 0][:3]
    if not best_chunks:
        excerpt = cleaned_text[:max_chars]
    else:
        excerpt = "\n\n".join(best_chunks)

    excerpt = excerpt[:max_chars]
    anchor = excerpt.split(". ")[:2]
    anchor_text = ". ".join(anchor).strip()

    return {
        "context": excerpt,
        "anchor": anchor_text or excerpt[:300],
    }
