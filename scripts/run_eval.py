"""

running example:
python scripts/run_eval.py outputs/v001-qwen-stefan-lora evals/results_v001.jsonl evals/scores_v001.csv

run the scripts using the adapter from outputs/... and then stores the results in evals/results...
it also stores the metadata from the eval questions into evals/scores... 
and then I am supposed to fill it out manually with how close it is to my style.

"""

import csv
import json
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


ROOT = Path(__file__).resolve().parents[1]

SYSTEM_PROMPT = (
    "Answer in Stefan's reasoning and communication style. "
    "Be analytical, direct, reflective, practical, and curious."
)


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_score_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "category",
        "question",
        "answer",
        "sounds_like_me",
        "reasoning_style",
        "usefulness",
        "too_verbose",
        "too_generic",
        "hallucinated_personal_facts",
        "notes",
    ]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow({
                "id": row.get("id", ""),
                "category": row.get("category", ""),
                "question": row.get("question", ""),
                "answer": row.get("answer", ""),
                "sounds_like_me": "",
                "reasoning_style": "",
                "usefulness": "",
                "too_verbose": "",
                "too_generic": "",
                "hallucinated_personal_facts": "",
                "notes": "",
            })


def main():
    if len(sys.argv) != 4:
        raise SystemExit(
            "Usage: python scripts/run_eval.py "
            "outputs/v001-qwen-stefan-lora-full "
            "evals/results_v001_full.jsonl "
            "evals/scores_v001_full.csv"
        )

    adapter_dir = ROOT / sys.argv[1]
    output_file = ROOT / sys.argv[2]
    score_file = ROOT / sys.argv[3]

    eval_file = ROOT / "evals" / "eval_questions.jsonl"
    model_name = "Qwen/Qwen2.5-7B-Instruct"

    if not adapter_dir.exists():
        raise FileNotFoundError(f"Missing adapter dir: {adapter_dir}")

    if not eval_file.exists():
        raise FileNotFoundError(f"Missing eval file: {eval_file}")

    eval_questions = load_jsonl(eval_file)

    tokenizer = AutoTokenizer.from_pretrained(
        adapter_dir,
        trust_remote_code=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    base_model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    model = PeftModel.from_pretrained(
        base_model,
        adapter_dir,
    )

    model.eval()

    results = []

    for item in eval_questions:
        question = item["question"]

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = tokenizer(
            prompt,
            return_tensors="pt",
        ).to(model.device)

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=500,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                repetition_penalty=1.05,
                pad_token_id=tokenizer.eos_token_id,
            )

        generated_ids = output_ids[0][inputs["input_ids"].shape[-1]:]
        answer = tokenizer.decode(
            generated_ids,
            skip_special_tokens=True,
        ).strip()

        result = {
            "id": item.get("id"),
            "category": item.get("category"),
            "question": question,
            "answer": answer,
            "adapter_dir": str(adapter_dir.relative_to(ROOT)),
        }

        results.append(result)

        print(f"\n[{item.get('id')}] {question}")
        print(answer[:500])
        print("-" * 80)

    write_jsonl(output_file, results)
    write_score_csv(score_file, results)

    print(f"\nSaved eval results to: {output_file}")
    print(f"Saved score sheet to: {score_file}")


if __name__ == "__main__":
    main()