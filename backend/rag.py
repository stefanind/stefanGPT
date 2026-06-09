import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[1]
RAG_INDEX_DIR = ROOT / "rag_index"

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

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


def retrieve_context(query: str, top_k: int = 4) -> str:
    load_rag_once()

    query_embedding = _embedder.encode(
        [query],
        normalize_embeddings=True,
    )

    query_embedding = np.asarray(query_embedding, dtype="float32")

    scores, indices = _index.search(query_embedding, top_k)

    retrieved = []

    for rank, idx in enumerate(indices[0]):
        if idx < 0:
            continue

        chunk = _chunks[idx]
        score = float(scores[0][rank])

        retrieved.append(
            f"[Source: {chunk['source']} | chunk {chunk['chunk_id']} | score {score:.3f}]\n"
            f"{chunk['text']}"
        )

    return "\n\n---\n\n".join(retrieved)