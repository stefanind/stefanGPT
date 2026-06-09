import json
import re
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[1]
RAG_DIR = ROOT / "rag_knowledge"
OUT_DIR = ROOT / "rag_index"

EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


def clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int, overlap: int):
    text = clean_text(text)

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def main():
    if not RAG_DIR.exists():
        raise FileNotFoundError(f"Missing rag_knowledge directory: {RAG_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    docs = []

    for md_path in sorted(RAG_DIR.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)

        for i, chunk in enumerate(chunks):
            docs.append({
                "source": md_path.name,
                "chunk_id": i,
                "text": chunk,
            })

    if not docs:
        raise SystemExit("No RAG chunks found.")

    print(f"Loaded {len(docs)} chunks from {RAG_DIR}")

    model = SentenceTransformer(EMBED_MODEL_NAME)

    texts = [doc["text"] for doc in docs]

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, str(OUT_DIR / "index.faiss"))

    (OUT_DIR / "chunks.json").write_text(
        json.dumps(docs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    manifest = {
        "embedding_model": EMBED_MODEL_NAME,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "num_chunks": len(docs),
        "source_dir": str(RAG_DIR.relative_to(ROOT)),
    }

    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote RAG index to: {OUT_DIR}")


if __name__ == "__main__":
    main()