# MLflow Training Tracking

Use MLflow to keep a record of each fine-tuning run before deciding whether a model should move to staging or production.

## Local Tracking

Start the MLflow UI from the repo root:

```powershell
mlflow ui --backend-store-uri .\mlruns
```

In another terminal, train as usual:

```powershell
python scripts\train_qlora.py configs\qwen_lora_smoke_v001.json
```

By default, training logs to the `stefanGPT-sft` experiment. You can override the tracking server or experiment name:

```powershell
$env:MLFLOW_TRACKING_URI="http://127.0.0.1:5000"
$env:MLFLOW_EXPERIMENT_NAME="stefanGPT-sft"
python scripts\train_qlora.py configs\qwen_lora_v001.json
```

## What Gets Logged

Each run logs:

- Git SHA, branch, and dirty-working-tree status
- training config
- dataset manifest
- RAG index manifest, when present
- train and eval metrics
- final adapter/tokenizer files from `outputs/...`
- `run_metadata.json` in the output directory

Training does not deploy a model. Deployment still happens by changing `deployment/staging_model.json` or `deployment/production_model.json` in a PR.

Eval logging is separate; see `docs/eval_workflow.md`.

## Disable Logging

For a one-off local run without MLflow:

```powershell
$env:MLFLOW_ENABLED="false"
python scripts\train_qlora.py configs\qwen_lora_smoke_v001.json
```
