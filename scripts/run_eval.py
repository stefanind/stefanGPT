"""

running example:
python scripts/run_eval.py outputs/v001-qwen-stefan-lora evals/results_v001.jsonl evals/scores_v001.csv

run the scripts using the adapter from outputs/... and then stores the results in evals/results...
it also stores the metadata from the eval questions into evals/scores... 
and then I am supposed to fill it out manually with how close it is to my style.

"""

import csv
import hashlib
import json
import os
import re
import sys
from contextlib import nullcontext
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from backend.rag import build_rag_messages

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
MAX_NEW_TOKENS = 500
TEMPERATURE = 0.7
TOP_P = 0.9
REPETITION_PENALTY = 1.05
DEFAULT_EXPERIMENT_NAME = "stefanGPT-eval"

SYSTEM_PROMPT = (
    "Answer in Stefan's reasoning and communication style. "
    "Be analytical, direct, reflective, practical, and curious. "
    "Do not invent personal facts. If you are unsure, say so."
)


def is_mlflow_enabled() -> bool:
    value = os.getenv("MLFLOW_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def metadata_cell(value):
    if value is None:
        return ""

    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def write_score_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "category",
        "eval_type",
        "difficulty",
        "question",
        "required_points",
        "failure_modes",
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
                "eval_type": row.get("eval_type", ""),
                "difficulty": row.get("difficulty", ""),
                "question": row.get("question", ""),
                "required_points": metadata_cell(row.get("required_points")),
                "failure_modes": metadata_cell(row.get("failure_modes")),
                "answer": row.get("answer", ""),
                "sounds_like_me": "",
                "reasoning_style": "",
                "usefulness": "",
                "too_verbose": "",
                "too_generic": "",
                "hallucinated_personal_facts": "",
                "notes": "",
            })


def infer_model_version(*paths: Path) -> str:
    for path in paths:
        match = re.search(r"v\d{3}", str(path))
        if match:
            return match.group(0)

    return "unknown"


def default_summary_file(score_file: Path) -> Path:
    stem = score_file.stem

    if stem.startswith("scores_"):
        return score_file.with_name(f"summary_{stem.removeprefix('scores_')}.json")

    return score_file.with_name(f"{stem}_summary.json")


def write_eval_summary(
    path: Path,
    model_version: str,
    adapter_dir: Path,
    training_metadata: dict,
    eval_file: Path,
    output_file: Path,
    score_file: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    summary = {
        "model_version": model_version,
        "adapter_dir": str(adapter_dir.relative_to(ROOT)),
        "training_mlflow_run_id": training_metadata.get("mlflow_run_id"),
        "eval_questions": str(eval_file.relative_to(ROOT)),
        "eval_questions_sha256": sha256_file(eval_file),
        "eval_results": str(output_file.relative_to(ROOT)),
        "eval_results_sha256": sha256_file(output_file),
        "score_sheet": str(score_file.relative_to(ROOT)),
        "generation": {
            "max_new_tokens": MAX_NEW_TOKENS,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "repetition_penalty": REPETITION_PENALTY,
        },
        "reviewed_by": "",
        "decision": "pending_review",
        "summary": "",
        "notes": "",
    }

    path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


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
    summary_file = default_summary_file(score_file)

    eval_file = ROOT / "evals" / "eval_questions.jsonl"

    if not adapter_dir.exists():
        raise FileNotFoundError(f"Missing adapter dir: {adapter_dir}")

    if not eval_file.exists():
        raise FileNotFoundError(f"Missing eval file: {eval_file}")

    eval_questions = load_jsonl(eval_file)
    model_version = infer_model_version(adapter_dir, output_file, score_file)
    training_metadata_file = adapter_dir / "run_metadata.json"
    training_metadata = (
        load_json(training_metadata_file)
        if training_metadata_file.exists()
        else {}
    )

    mlflow = None
    active_run_context = nullcontext()

    if is_mlflow_enabled():
        try:
            import mlflow as mlflow_module
        except ImportError as exc:
            raise SystemExit(
                "MLflow logging is enabled, but mlflow is not installed. "
                "Run `pip install -r requirements.txt` or set MLFLOW_ENABLED=false."
            ) from exc

        mlflow = mlflow_module

        tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        experiment_name = os.getenv("MLFLOW_EVAL_EXPERIMENT_NAME", DEFAULT_EXPERIMENT_NAME)
        mlflow.set_experiment(experiment_name)
        active_run_context = mlflow.start_run(run_name=f"{model_version}-qualitative-eval")

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
        MODEL_NAME,
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

    with active_run_context:
        if mlflow is not None:
            tags = {
                "project": "stefanGPT",
                "stage": "qualitative-eval",
                "model_version": model_version,
                "base_model": MODEL_NAME,
                "adapter_dir": str(adapter_dir.relative_to(ROOT)),
            }

            training_run_id = training_metadata.get("mlflow_run_id")
            if training_run_id:
                tags["training_mlflow_run_id"] = training_run_id

            mlflow.set_tags(tags)
            mlflow.log_params({
                "eval.question_count": len(eval_questions),
                "generation.max_new_tokens": MAX_NEW_TOKENS,
                "generation.temperature": TEMPERATURE,
                "generation.top_p": TOP_P,
                "generation.repetition_penalty": REPETITION_PENALTY,
            })
            mlflow.log_artifact(str(eval_file), artifact_path="eval")

            if training_metadata_file.exists():
                mlflow.log_artifact(str(training_metadata_file), artifact_path="metadata")

        for item in eval_questions:
            question = item["question"]

            messages = build_rag_messages(question, SYSTEM_PROMPT, top_k=4)

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
                    max_new_tokens=MAX_NEW_TOKENS,
                    temperature=TEMPERATURE,
                    top_p=TOP_P,
                    do_sample=TEMPERATURE > 0,
                    repetition_penalty=REPETITION_PENALTY,
                    pad_token_id=tokenizer.eos_token_id,
                )

            generated_ids = output_ids[0][inputs["input_ids"].shape[-1]:]
            answer = tokenizer.decode(
                generated_ids,
                skip_special_tokens=True,
            ).strip()

            result = dict(item)
            result.update({
                "answer": answer,
                "adapter_dir": str(adapter_dir.relative_to(ROOT)),
                "model_version": model_version,
            })

            results.append(result)

            idx = len(results)
            total = len(eval_questions)

            should_print = (
                idx == 1 or
                idx == total or
                idx % 5 == 0
            )

            if should_print:
                print("\n" + "=" * 80)
                print(f"Completed {idx}/{total}: {item.get('id')} - {item.get('category')}")
                print("\nQUESTION:")
                print(question)
                print("\nANSWER:")
                print(answer)
                print("=" * 80)

        write_jsonl(output_file, results)
        write_score_csv(score_file, results)
        write_eval_summary(
            summary_file,
            model_version,
            adapter_dir,
            training_metadata,
            eval_file,
            output_file,
            score_file,
        )

        if mlflow is not None:
            mlflow.log_artifact(str(output_file), artifact_path="eval")
            mlflow.log_artifact(str(score_file), artifact_path="eval")
            mlflow.log_artifact(str(summary_file), artifact_path="eval")

    print(f"\nSaved eval results to: {output_file}")
    print(f"Saved score sheet to: {score_file}")
    print(f"Saved eval summary to: {summary_file}")


if __name__ == "__main__":
    main()
