"""

running example:
python scripts/train_qlora.py configs/qwen_lora_smoke_v001.json

runs the script using the specified json from configs/

"""

import json
import os
import subprocess
import sys
import torch
from contextlib import nullcontext
from pathlib import Path

from datasets import load_dataset
from peft import LoraConfig
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)
from trl import SFTConfig, SFTTrainer


ROOT = Path(__file__).resolve().parents[1]

# Default MLflow experiment unless MLFLOW_EXPERIMENT_NAME is set.
DEFAULT_EXPERIMENT_NAME = "stefanGPT-sft"


def is_mlflow_enabled() -> bool:
    # Allow quick local runs without MLflow by setting MLFLOW_ENABLED=false.
    value = os.getenv("MLFLOW_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_json(path: Path) -> dict:
    # Used for metadata files that should be logged alongside the run.
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def git_value(*args: str) -> str:
    # Capture Git metadata for model lineage; keep training usable outside Git.
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"

    return result.stdout.strip() or "unknown"


def git_is_dirty() -> bool:
    # Records whether uncommitted changes existed when training started.
    return bool(git_value("status", "--porcelain"))


def flatten_params(prefix: str, data: dict) -> dict:
    # MLflow params must be scalar-ish, so nested values become JSON strings.
    params = {}

    for key, value in data.items():
        name = f"{prefix}.{key}" if prefix else key

        if isinstance(value, (str, int, float, bool)) or value is None:
            params[name] = value
        else:
            params[name] = json.dumps(value, sort_keys=True)

    return params


def numeric_metrics(metrics: dict) -> dict:
    # MLflow metrics must be numeric.
    return {
        key: value
        for key, value in metrics.items()
        if isinstance(value, (int, float))
    }


def log_final_adapter_artifacts(mlflow, out_dir: Path) -> None:
    # Log only final adapter/tokenizer files, not intermediate checkpoint dirs.
    for path in sorted(out_dir.iterdir()):
        if path.is_file():
            mlflow.log_artifact(str(path), artifact_path="adapter")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/train_qlora.py configs/qwen_lora_smoke_v001.json")

    config_path = ROOT / sys.argv[1]
    config = load_config(config_path)

    version = config["version"]
    model_name = config["model_name"]
    run_name = f'{version}-{config["run_name"]}'

    # Capture Git state before training writes new output files.
    git_sha = git_value("rev-parse", "HEAD")
    git_branch = git_value("branch", "--show-current")
    git_dirty = git_is_dirty()

    train_file = ROOT / "data" / version / "stefan_train.jsonl"
    val_file = ROOT / "data" / version / "stefan_val.jsonl"

    # These artifacts tie a model back to the exact data and RAG context used.
    dataset_manifest_file = ROOT / "data" / version / "dataset_manifest.json"
    rag_manifest_file = ROOT / "rag_index" / "manifest.json"

    if not train_file.exists():
        raise FileNotFoundError(f"Missing train file: {train_file}")

    if not val_file.exists():
        raise FileNotFoundError(f"Missing validation file: {val_file}")

    if not dataset_manifest_file.exists():
        raise FileNotFoundError(f"Missing dataset manifest: {dataset_manifest_file}")

    dataset_manifest = load_json(dataset_manifest_file)

    out_dir = ROOT / "outputs" / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    config_copy_path = out_dir / "training_config.json"
    config_copy_path.write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )

    mlflow = None
    active_run_context = nullcontext()

    # Start an MLflow run when enabled; otherwise the rest of training is unchanged.
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

        experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", DEFAULT_EXPERIMENT_NAME)
        mlflow.set_experiment(experiment_name)
        active_run_context = mlflow.start_run(run_name=run_name)

    dataset = load_dataset(
        "json",
        data_files={
            "train": str(train_file),
            "validation": str(val_file),
        },
    )

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def format_chat(example):
        return {
            "text": tokenizer.apply_chat_template(
                example["messages"],
                tokenize=False,
                add_generation_prompt=False,
            )
        }

    dataset = dataset.map(
        format_chat,
        remove_columns=dataset["train"].column_names,
    )

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    model.config.use_cache = False

    lora_config = LoraConfig(
        r=config["lora_r"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=config["lora_dropout"],
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        task_type="CAUSAL_LM",
    )

    sft_kwargs = {
        "output_dir": str(out_dir),
        "logging_steps": config["logging_steps"],
        "eval_steps": config["eval_steps"],
        "save_steps": config["save_steps"],
        "per_device_train_batch_size": config["per_device_train_batch_size"],
        "per_device_eval_batch_size": config["per_device_eval_batch_size"],
        "gradient_accumulation_steps": config["gradient_accumulation_steps"],
        "learning_rate": config["learning_rate"],
        "warmup_steps": config["warmup_steps"],
        "max_seq_length": config["max_length"],
        "bf16": config["bf16"],
        "dataset_text_field": "text",
        "packing": config["packing"],
        "eval_strategy": "steps",
        "save_strategy": "steps",
        # Let Trainer stream step metrics into the active MLflow run.
        "report_to": ["mlflow"] if mlflow is not None else "none",
        "run_name": run_name,
    }

    if config["max_steps"] is not None:
        sft_kwargs["max_steps"] = config["max_steps"]
    else:
        sft_kwargs["num_train_epochs"] = config["num_train_epochs"]

    with active_run_context as active_run:
        if mlflow is not None:
            # Tags make the run searchable by code version, data version, and output.
            mlflow.set_tags({
                "project": "stefanGPT",
                "stage": "sft-training",
                "git_sha": git_sha,
                "git_branch": git_branch,
                "git_dirty": str(git_dirty).lower(),
                "dataset_version": version,
                "base_model": model_name,
                "adapter_output_dir": str(out_dir.relative_to(ROOT)),
            })

            # Params/artifacts preserve the config and dataset evidence for this run.
            mlflow.log_params(flatten_params("config", config))
            mlflow.log_params(flatten_params("dataset", dataset_manifest))
            mlflow.log_artifact(str(config_copy_path), artifact_path="config")
            mlflow.log_artifact(str(dataset_manifest_file), artifact_path="data")

            if rag_manifest_file.exists():
                mlflow.log_artifact(str(rag_manifest_file), artifact_path="rag")

        training_args = SFTConfig(**sft_kwargs)

        trainer = SFTTrainer(
            model=model,
            args=training_args,
            train_dataset=dataset["train"],
            eval_dataset=dataset["validation"],
            peft_config=lora_config,
        )

        train_result = trainer.train()
        train_metrics = train_result.metrics

        # Save Hugging Face metrics locally as well as to MLflow.
        trainer.log_metrics("train", train_metrics)
        trainer.save_metrics("train", train_metrics)

        eval_metrics = trainer.evaluate()
        trainer.log_metrics("eval", eval_metrics)
        trainer.save_metrics("eval", eval_metrics)

        # Persist the deployable LoRA adapter and tokenizer files.
        trainer.save_model(str(out_dir))
        trainer.save_state()
        tokenizer.save_pretrained(str(out_dir))

        # Local metadata lets an output folder point back to its MLflow run.
        run_metadata = {
            "mlflow_run_id": active_run.info.run_id if active_run is not None else None,
            "mlflow_tracking_uri": mlflow.get_tracking_uri() if mlflow is not None else None,
            "run_name": run_name,
            "git_sha": git_sha,
            "git_branch": git_branch,
            "git_dirty": git_dirty,
            "dataset_version": version,
            "dataset_manifest": str(dataset_manifest_file.relative_to(ROOT)),
            "base_model": model_name,
            "adapter_output_dir": str(out_dir.relative_to(ROOT)),
        }

        run_metadata_path = out_dir / "run_metadata.json"
        run_metadata_path.write_text(
            json.dumps(run_metadata, indent=2),
            encoding="utf-8",
        )

        if mlflow is not None:
            # Explicitly log final aggregate metrics and deployable artifacts.
            mlflow.log_metrics(numeric_metrics(train_metrics))
            mlflow.log_metrics(numeric_metrics(eval_metrics))
            mlflow.log_artifact(str(run_metadata_path), artifact_path="metadata")
            log_final_adapter_artifacts(mlflow, out_dir)

    print(f"Saved LoRA adapter to: {out_dir}")


if __name__ == "__main__":
    main()
