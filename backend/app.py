import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from peft import PeftModel
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


# ---------------------------------------------------------------------
# Project paths and configurable settings
# ---------------------------------------------------------------------

# ROOT points to the root of your repo.
# If this file is backend/app.py, then parents[1] is the project root.
ROOT = Path(__file__).resolve().parents[1]

# Base model from Hugging Face.
# You can override this when launching the server with:
# MODEL_NAME="..." uvicorn backend.app:app --host 0.0.0.0 --port 8000
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")

# Folder containing your trained LoRA adapter.
# Default:
# outputs/v001-qwen-stefan-lora/
#
# This folder should contain files like:
# adapter_model.safetensors
# adapter_config.json
ADAPTER_DIR = Path(
    os.getenv(
        "ADAPTER_DIR",
        str(ROOT / "outputs" / "v001-qwen-stefan-lora"),
    )
)

# The system prompt controls the model's general behavior.
# This is prepended to every chat request.
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    (
        "Answer in Stefan's reasoning and communication style. "
        "Be analytical, direct, reflective, practical, and curious. "
        "Do not invent personal facts. If you are unsure, say so."
    ),
)

# Default generation length.
# The frontend can override this per request if needed.
DEFAULT_MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "350"))


# ---------------------------------------------------------------------
# Global model objects
# ---------------------------------------------------------------------

# These start as None and get loaded once when the API starts.
# We keep them global so the model does NOT reload on every request.
model = None
tokenizer = None


# ---------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------

class ChatRequest(BaseModel):
    """
    Expected JSON body for POST /chat.

    Example:
    {
      "message": "What kind of AI work is Stefan interested in?",
      "max_new_tokens": 300,
      "temperature": 0.7,
      "top_p": 0.9
    }
    """

    # User message from the website/frontend.
    message: str = Field(..., min_length=1)

    # Optional max generation length.
    # If omitted, DEFAULT_MAX_NEW_TOKENS is used.
    max_new_tokens: Optional[int] = Field(default=None, ge=1, le=1000)

    # Sampling temperature.
    # Higher = more creative/random.
    # Lower = more deterministic.
    # 0 means deterministic greedy generation.
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Nucleus sampling parameter.
    # top_p=0.9 means sample from the smallest set of tokens
    # whose cumulative probability is at least 90%.
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    """
    JSON response returned by POST /chat.
    """

    answer: str
    model_name: str
    adapter_dir: str


# ---------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------

def load_model_once():
    """
    Load the base Qwen model and your LoRA adapter.

    This function is called once when the FastAPI app starts.

    Important:
    - The base model is loaded from Hugging Face.
    - The LoRA adapter is loaded from ADAPTER_DIR.
    - PEFT attaches the LoRA adapter onto the base model.
    """

    global model, tokenizer

    # Avoid reloading if the function somehow gets called twice.
    if model is not None and tokenizer is not None:
        return

    # Make sure the LoRA adapter folder exists.
    if not ADAPTER_DIR.exists():
        raise FileNotFoundError(f"Missing LoRA adapter directory: {ADAPTER_DIR}")

    print(f"Loading tokenizer from: {ADAPTER_DIR}")

    # Load tokenizer.
    # We load from the adapter directory because you saved the tokenizer there
    # during training.
    tokenizer = AutoTokenizer.from_pretrained(
        ADAPTER_DIR,
        trust_remote_code=True,
    )

    # Some tokenizers do not have a pad token.
    # For causal language models, using EOS as PAD is common.
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"Loading base model: {MODEL_NAME}")

    # QLoRA-style 4-bit loading.
    # This keeps VRAM usage much lower than loading the model in full precision.
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    # Load the base Qwen model.
    # device_map="auto" places layers on the available GPU automatically.
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    print(f"Loading LoRA adapter from: {ADAPTER_DIR}")

    # Attach your trained LoRA adapter to the base model.
    #
    # Conceptually:
    # Qwen base model + Stefan LoRA adapter = Digital Stefan model
    model = PeftModel.from_pretrained(
        base_model,
        ADAPTER_DIR,
    )

    # Put model in inference mode.
    # This disables training-specific behavior like dropout.
    model.eval()

    print("Model loaded successfully.")


# ---------------------------------------------------------------------
# FastAPI lifecycle
# ---------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI startup/shutdown lifecycle.

    The model is loaded when the server starts, before requests come in.
    This avoids reloading the model for every chat message.
    """

    load_model_once()
    yield


# Create the FastAPI application.
app = FastAPI(
    title="Digital Stefan API",
    description="Qwen + Stefan LoRA chatbot backend",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------
# CORS settings
# ---------------------------------------------------------------------

# CORS controls which websites are allowed to call this backend.
#
# During testing, "*" is convenient.
# For production, you should restrict it to your GitHub Pages domain.
#
# Example:
# ALLOWED_ORIGINS="https://stefanind.github.io"
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------

@app.get("/health")
def health():
    """
    Simple health check endpoint.

    Useful for testing whether the server is running and whether the model loaded.

    Example:
    curl http://localhost:8000/health
    """

    return {
        "status": "ok",
        "model_loaded": model is not None,
        "model_name": MODEL_NAME,
        "adapter_dir": str(ADAPTER_DIR),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Main chat endpoint.

    This receives a user message, formats it using Qwen's chat template,
    generates an answer, and returns that answer as JSON.
    """

    # If the model failed to load during startup, return a 503 error.
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model is not loaded yet.")

    # Clean the user's input.
    message = req.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # The chat prompt uses the same structure as training/eval:
    # system message + user message.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    # Convert messages into Qwen's expected chat format.
    #
    # add_generation_prompt=True means:
    # "format the prompt so the next thing the model should produce
    # is the assistant response."
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    # Tokenize the prompt and move tensors to the same device as the model.
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
    ).to(model.device)

    # Use request-specific max_new_tokens if provided,
    # otherwise use the default from environment/config.
    max_new_tokens = req.max_new_tokens or DEFAULT_MAX_NEW_TOKENS

    # If temperature is 0, use deterministic generation.
    # If temperature > 0, use sampling.
    do_sample = req.temperature > 0

    # Base generation settings.
    generation_kwargs = {
        "max_new_tokens": max_new_tokens,
        "repetition_penalty": 1.05,
        "pad_token_id": tokenizer.eos_token_id,
    }

    # Sampling mode.
    if do_sample:
        generation_kwargs.update(
            {
                "do_sample": True,
                "temperature": req.temperature,
                "top_p": req.top_p,
            }
        )

    # Deterministic mode.
    else:
        generation_kwargs.update(
            {
                "do_sample": False,
            }
        )

    try:
        # Disable gradient tracking during inference.
        # This saves memory and compute.
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                **generation_kwargs,
            )

        # The output contains:
        # prompt tokens + newly generated tokens.
        #
        # We only want the newly generated assistant answer.
        generated_ids = output_ids[0][inputs["input_ids"].shape[-1]:]

        # Convert token IDs back into text.
        answer = tokenizer.decode(
            generated_ids,
            skip_special_tokens=True,
        ).strip()

    except RuntimeError as e:
        # Return a readable API error if generation fails.
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

    return ChatResponse(
        answer=answer,
        model_name=MODEL_NAME,
        adapter_dir=str(ADAPTER_DIR),
    )