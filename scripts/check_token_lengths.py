import json
import sys
from pathlib import Path
from transformers import AutoTokenizer

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
MAX_LENGTH = 2048


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/check_token_lengths.py v001")

    version = sys.argv[1]
    files = [
        Path("data") / version / "stefan_train.jsonl",
        Path("data") / version / "stefan_val.jsonl",
    ]

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
    )

    lengths = []
    too_long = []

    for path in files:
        with path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                ex = json.loads(line)

                text = tokenizer.apply_chat_template(
                    ex["messages"],
                    tokenize=False,
                    add_generation_prompt=False,
                )

                token_ids = tokenizer(
                    text,
                    add_special_tokens=False,
                )["input_ids"]

                n_tokens = len(token_ids)
                lengths.append(n_tokens)

                if n_tokens > MAX_LENGTH:
                    question = ex["messages"][1]["content"][:100]
                    too_long.append((path.name, line_num, n_tokens, question))

    print(f"Checked version: {version}")
    print(f"Total examples: {len(lengths)}")
    print(f"Max tokens: {max(lengths)}")
    print(f"Avg tokens: {sum(lengths) // len(lengths)}")

    lengths_sorted = sorted(lengths)
    p95 = lengths_sorted[int(0.95 * len(lengths_sorted)) - 1]
    print(f"95th percentile tokens: {p95}")

    if too_long:
        print("\nExamples over max_length:")
        for file_name, line_num, n_tokens, question in too_long[:20]:
            print(f"- {file_name}, line {line_num}: {n_tokens} tokens | {question}")
        raise SystemExit(1)

    print("All examples fit ✅")


if __name__ == "__main__":
    main()