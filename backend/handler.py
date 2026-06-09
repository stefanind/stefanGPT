import os
from pathlib import Path

import runpod
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from backend.rag import retrieve_context

ROOT = Path(__file__).resolve().parents[1]

MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
ADAPTER_DIR = os.getenv("ADAPTER_DIR", "stefanind/qwen-stefan-lora-v001")

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    (
        "Answer in Stefan's reasoning and communication style. "
        "Be analytical, direct, reflective, practical, and curious. "
        "Do not invent personal facts. If you are unsure, say so."
    ),
)

DEFAULT_MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "350"))

model = None
tokenizer = None


def load_model_once():
    global model, tokenizer

    if model is not None and tokenizer is not None:
        return

    print(f"Loading tokenizer from: {ADAPTER_DIR}")
    tokenizer = AutoTokenizer.from_pretrained(
        ADAPTER_DIR,
        trust_remote_code=True,
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"Loading base model: {MODEL_NAME}")

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

    print(f"Loading LoRA adapter from: {ADAPTER_DIR}")
    model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
    model.eval()

    print("Model loaded successfully.")


def generate_answer(
    message: str,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> str:
    load_model_once()

    retrieved_context = retrieve_context(message, top_k=4)

    messages = [
        {
            "role": "system",
            "content": (
                SYSTEM_PROMPT
                + "\n\nUse the retrieved context when it is relevant. "
                + "Do not invent personal facts that are not supported by the context. "
                + "If the retrieved context does not answer the question, say what you can answer from general reasoning."
            ),
        },
        {
            "role": "user",
            "content": (
                "Retrieved context:\n"
                f"{retrieved_context}\n\n"
                "User question:\n"
                f"{message.strip()}"
            ),
        },
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    do_sample = temperature > 0

    generation_kwargs = {
        "max_new_tokens": max_new_tokens,
        "repetition_penalty": 1.05,
        "pad_token_id": tokenizer.eos_token_id,
        "do_sample": do_sample,
    }

    if do_sample:
        generation_kwargs.update(
            {
                "temperature": temperature,
                "top_p": top_p,
            }
        )

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            **generation_kwargs,
        )

    generated_ids = output_ids[0][inputs["input_ids"].shape[-1]:]
    answer = tokenizer.decode(
        generated_ids,
        skip_special_tokens=True,
    ).strip()

    return answer


def handler(event):
    """
    RunPod Serverless entrypoint.

    Expected request:
    {
      "input": {
        "message": "What kind of AI work is Stefan interested in?",
        "max_new_tokens": 300,
        "temperature": 0.7,
        "top_p": 0.9
      }
    }
    """

    job_input = event.get("input", {})

    message = job_input.get("message") or job_input.get("prompt")

    if not message or not str(message).strip():
        return {
            "error": "Missing required input field: message"
        }

    max_new_tokens = int(job_input.get("max_new_tokens", DEFAULT_MAX_NEW_TOKENS))
    max_new_tokens = max(1, min(max_new_tokens, 1000))

    temperature = float(job_input.get("temperature", 0.7))
    temperature = max(0.0, min(temperature, 2.0))

    top_p = float(job_input.get("top_p", 0.9))
    top_p = max(0.0, min(top_p, 1.0))

    try:
        answer = generate_answer(
            message=message,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
        )

        return {
            "answer": answer,
            "model_name": MODEL_NAME,
            "adapter_dir": ADAPTER_DIR,
        }

    except Exception as e:
        return {
            "error": str(e)
        }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})