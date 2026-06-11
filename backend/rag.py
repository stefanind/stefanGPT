import json
import re
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[1]
RAG_INDEX_DIR = ROOT / "rag_index"

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

RAG_INSTRUCTIONS = (
    "Use the retrieved context when it is relevant. "
    "Do not invent personal facts that are not supported by the context. "
    "If the retrieved context does not answer the question, say what you can answer from general reasoning."
)

STOPWORDS = {
    "about",
    "does",
    "from",
    "have",
    "how",
    "is",
    "know",
    "stefan",
    "tell",
    "the",
    "what",
}

_embedder = None
_index = None
_chunks = None


def load_rag_once():
    global _embedder, _index, _chunks

    if _embedder is not None and _index is not None and _chunks is not None:
        return

    index_path = RAG_INDEX_DIR / "index.faiss"
    chunks_path = RAG_INDEX_DIR / "chunks.json"

    if not index_path.exists() or not chunks_path.exists():
        raise FileNotFoundError(
            f"Missing RAG index files. Expected {index_path} and {chunks_path}"
        )

    _embedder = SentenceTransformer(EMBED_MODEL_NAME)
    _index = faiss.read_index(str(index_path))

    with chunks_path.open("r", encoding="utf-8") as f:
        _chunks = json.load(f)


def query_terms(text: str):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in STOPWORDS
    }


def lexical_overlap(query: str, chunk: dict) -> float:
    terms = query_terms(query)
    if not terms:
        return 0.0

    haystack = " ".join(
        [
            chunk.get("source", ""),
            chunk.get("heading", ""),
            chunk.get("text", ""),
        ]
    ).lower()

    return sum(1 for term in terms if term in haystack) / len(terms)


def retrieve_context(query: str, top_k: int = 4) -> str:
    load_rag_once()

    query_embedding = _embedder.encode(
        [query],
        normalize_embeddings=True,
    )

    query_embedding = np.asarray(query_embedding, dtype="float32")

    candidate_k = min(len(_chunks), max(top_k * 4, top_k))
    scores, indices = _index.search(query_embedding, candidate_k)

    candidates = []

    for rank, idx in enumerate(indices[0]):
        if idx < 0:
            continue

        chunk = _chunks[idx]
        score = float(scores[0][rank])
        rank_score = score + (0.15 * lexical_overlap(query, chunk))
        candidates.append((rank_score, score, chunk))

    candidates.sort(reverse=True, key=lambda item: item[0])

    retrieved = []

    for _, score, chunk in candidates[:top_k]:

        source = chunk["source"]
        heading = chunk.get("heading")
        if heading:
            source = f"{source} > {heading}"

        retrieved.append(
            f"[Source: {source} | chunk {chunk['chunk_id']} | score {score:.3f}]\n"
            f"{chunk['text']}"
        )

    return "\n\n---\n\n".join(retrieved)


def build_rag_messages(message: str, system_prompt: str, top_k: int = 4):
    message = message.strip()
    retrieved_context = retrieve_context(message, top_k=top_k)

    return [
        {
            "role": "system",
            "content": f"{system_prompt}\n\n{RAG_INSTRUCTIONS}",
        },
        {
            "role": "user",
            "content": (
                "Retrieved context:\n"
                f"{retrieved_context}\n\n"
                "User question:\n"
                f"{message}"
            ),
        },
    ]
