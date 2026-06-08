FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/.cache/huggingface

ENV MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
ENV ADAPTER_DIR=stefanind/qwen-stefan-lora-v001
ENV MAX_NEW_TOKENS=350

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/

CMD ["python", "-m", "backend.handler"]
