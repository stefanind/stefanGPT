"""

running example:
python scripts/train_qlora.py configs/qwen_lora_smoke_v001.json

runs the script using the specified json from configs/

"""

import json
import sys
import torch
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


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/train_qlora.py configs/qwen_lora_smoke_v001.json")

    config_path = ROOT / sys.argv[1]
    config = load_config(config_path)

    version = config["version"]
    model_name = config["model_name"]

    train_file = ROOT / "data" / version / "stefan_train.jsonl"
    val_file = ROOT / "data" / version / "stefan_val.jsonl"

    if not train_file.exists():
        raise FileNotFoundError(f"Missing train file: {train_file}")

    if not val_file.exists():
        raise FileNotFoundError(f"Missing validation file: {val_file}")

    out_dir = ROOT / "outputs" / f'{version}-{config["run_name"]}'
    out_dir.mkdir(parents=True, exist_ok=True)

    config_copy_path = out_dir / "training_config.json"
    config_copy_path.write_text(
        json.dumps(config, indent=2),
        encoding="utf-8",
    )

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
        "report_to": "none",
    }

    if config["max_steps"] is not None:
        sft_kwargs["max_steps"] = config["max_steps"]
    else:
        sft_kwargs["num_train_epochs"] = config["num_train_epochs"]

    training_args = SFTConfig(**sft_kwargs)

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        peft_config=lora_config,
    )

    trainer.train()
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    print(f"Saved LoRA adapter to: {out_dir}")


if __name__ == "__main__":
    main()