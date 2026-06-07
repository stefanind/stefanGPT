import json
import re
import sys
from datetime import datetime
from pathlib import Path
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
SFT_DIR = ROOT / "sft_data"
DATA_DIR = ROOT / "data"

SYSTEM_PROMPT = (
    "Answer in Stefan's reasoning and communication style. "
    "Be analytical, direct, reflective, practical, and curious."
)

RANDOM_SEED = 44
VAL_SIZE = 0.2


def clean_section(text: str) -> str:
    text = re.sub(
        r"^\s*([-*_])\1{2,}\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )
    text = text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def extract_section(text: str, header: str) -> str:
    pattern = rf"## {re.escape(header)}\s*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, flags=re.DOTALL)
    return clean_section(match.group(1)) if match else ""


def parse_md_file(path: Path):
    text = path.read_text(encoding="utf-8")
    chunks = re.split(r"(?=^# Example\s+\d+)", text, flags=re.MULTILINE)

    examples = []

    for chunk in chunks:
        if not chunk.strip().startswith("# Example"):
            continue

        category = extract_section(chunk, "Category") or path.stem
        question = extract_section(chunk, "Question")
        answer = extract_section(chunk, "Final Answer")

        if not question or not answer:
            print(f"Skipping incomplete example in {path.name}")
            continue

        examples.append({
            "category": category,
            "source_file": path.name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ],
        })

    return examples


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/build_sft_jsonl.py v001")

    version = sys.argv[1]

    if not re.fullmatch(r"v\d{3}", version):
        raise SystemExit("Version must look like v001, v002, v003, etc.")

    out_dir = DATA_DIR / version
    out_dir.mkdir(parents=True, exist_ok=False)

    all_examples = []
    source_counts = {}

    for md_path in sorted(SFT_DIR.glob("*.md")):
        examples = parse_md_file(md_path)
        all_examples.extend(examples)
        source_counts[md_path.name] = len(examples)

    if len(all_examples) < 2:
        raise SystemExit("Need at least 2 examples to create train/val split.")

    train, val = train_test_split(
        all_examples,
        test_size=VAL_SIZE,
        random_state=RANDOM_SEED,
        shuffle=True,
    )

    train_file = out_dir / "stefan_train.jsonl"
    val_file = out_dir / "stefan_val.jsonl"
    manifest_file = out_dir / "dataset_manifest.json"

    write_jsonl(train_file, train)
    write_jsonl(val_file, val)

    manifest = {
        "version": version,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_dir": str(SFT_DIR.relative_to(ROOT)),
        "output_dir": str(out_dir.relative_to(ROOT)),
        "train_file": str(train_file.relative_to(ROOT)),
        "val_file": str(val_file.relative_to(ROOT)),
        "total_examples": len(all_examples),
        "train_examples": len(train),
        "val_examples": len(val),
        "validation_size": VAL_SIZE,
        "random_seed": RANDOM_SEED,
        "source_counts": source_counts,
        "system_prompt": SYSTEM_PROMPT,
        "notes": "",
    }

    manifest_file.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Created dataset version: {version}")
    print(f"Total examples: {len(all_examples)}")
    print(f"Train examples: {len(train)}")
    print(f"Val examples: {len(val)}")
    print(f"Wrote: {train_file}")
    print(f"Wrote: {val_file}")
    print(f"Wrote: {manifest_file}")

    print("\nSource counts:")
    for source, count in source_counts.items():
        print(f"  {source}: {count}")


if __name__ == "__main__":
    main()