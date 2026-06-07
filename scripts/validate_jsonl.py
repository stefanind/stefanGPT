import json
import sys
from pathlib import Path

REQUIRED_ROLES = ["system", "user", "assistant"]


def validate_file(path: Path) -> None:
    errors = []
    answer_lengths = []

    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            try:
                ex = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {line_num}: invalid JSON: {e}")
                continue

            messages = ex.get("messages")

            if not isinstance(messages, list):
                errors.append(f"Line {line_num}: missing or invalid 'messages'")
                continue

            if len(messages) != 3:
                errors.append(f"Line {line_num}: expected 3 messages, got {len(messages)}")
                continue

            roles = [m.get("role") for m in messages]
            if roles != REQUIRED_ROLES:
                errors.append(f"Line {line_num}: expected roles {REQUIRED_ROLES}, got {roles}")
                continue

            for msg in messages:
                content = msg.get("content")
                if not isinstance(content, str) or not content.strip():
                    errors.append(f"Line {line_num}: empty content in {msg.get('role')} message")

            answer = messages[2]["content"]
            answer_lengths.append(len(answer))

            if "---" in answer:
                errors.append(f"Line {line_num}: assistant answer contains markdown separator '---'")

    print(f"\nChecked {path}")
    print(f"Examples: {len(answer_lengths)}")

    if answer_lengths:
        print(f"Avg answer chars: {sum(answer_lengths) // len(answer_lengths)}")
        print(f"Max answer chars: {max(answer_lengths)}")

    if errors:
        print("\nErrors:")
        for err in errors[:20]:
            print(f"- {err}")
        if len(errors) > 20:
            print(f"...and {len(errors) - 20} more")
        raise SystemExit(1)

    print("Valid ✅")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/validate_jsonl.py v001")

    version = sys.argv[1]
    version_dir = Path("data") / version

    files = [
        version_dir / "stefan_train.jsonl",
        version_dir / "stefan_val.jsonl",
    ]

    for path in files:
        if not path.exists():
            raise FileNotFoundError(f"Missing file: {path}")
        validate_file(path)


if __name__ == "__main__":
    main()