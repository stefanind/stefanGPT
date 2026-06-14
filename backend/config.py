import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEPLOYMENT_ENV = os.getenv("DEPLOYMENT_ENV", "production")
DEPLOYMENT_MANIFEST_PATH = ROOT / "deployment" / f"{DEPLOYMENT_ENV}_model.json"

if not DEPLOYMENT_MANIFEST_PATH.exists():
    raise FileNotFoundError(
        f"Missing deployment manifest for DEPLOYMENT_ENV={DEPLOYMENT_ENV!r}: "
        f"{DEPLOYMENT_MANIFEST_PATH}"
    )

with DEPLOYMENT_MANIFEST_PATH.open("r", encoding="utf-8") as f:
    DEPLOYMENT_MANIFEST = json.load(f)

MODEL_NAME = DEPLOYMENT_MANIFEST["base_model"]
ADAPTER_DIR = DEPLOYMENT_MANIFEST["adapter_uri"]

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    (
        "Answer in Stefan's reasoning and communication style. "
        "Be analytical, direct, reflective, practical, and curious. "
        "Do not invent personal facts. If you are unsure, say so."
    ),
)

DEFAULT_MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "350"))
