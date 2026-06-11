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


def clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_long_block(text: str, max_chars: int):
    pieces = []
    current = []
    current_len = 0

    for line in text.splitlines():
        extra_len = len(line) + (1 if current else 0)

        if current and current_len + extra_len > max_chars:
            pieces.append("\n".join(current).strip())
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += extra_len

    if current:
        pieces.append("\n".join(current).strip())

    return pieces


def split_text(text: str, max_chars: int):
    chunks = []
    current = ""

    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""

            chunks.extend(split_long_block(paragraph, max_chars))
            continue

        candidate = paragraph if not current else f"{current}\n\n{paragraph}"

        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return chunks


def chunk_markdown(text: str, max_chars: int):
    text = clean_text(text)
    chunks = []
    headings = []
    section_lines = []

    def flush_section():
        nonempty = [line for line in section_lines if line.strip()]
        if not nonempty:
            return

        if len(nonempty) == 1 and nonempty[0].startswith("#"):
            return

        heading = " > ".join(headings)
        section_text = "\n".join(section_lines).strip()

        for chunk in split_text(section_text, max_chars):
            chunks.append({
                "heading": heading,
                "text": chunk,
            })

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)

        if match:
            flush_section()
            level = len(match.group(1))
            title = match.group(2).strip()
            headings = headings[:level - 1] + [title]
            section_lines = [line]
        else:
            section_lines.append(line)

    flush_section()

    return chunks


def main():
    if not RAG_DIR.exists():
        raise FileNotFoundError(f"Missing rag_knowledge directory: {RAG_DIR}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    docs = []

    for md_path in sorted(RAG_DIR.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        chunks = chunk_markdown(text, CHUNK_SIZE)

        for i, chunk in enumerate(chunks):
            docs.append({
                "source": md_path.name,
                "chunk_id": i,
                "heading": chunk["heading"],
                "text": chunk["text"],
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
        "chunking": "markdown_sections",
        "chunk_max_chars": CHUNK_SIZE,
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
