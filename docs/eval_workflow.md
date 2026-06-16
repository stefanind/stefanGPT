# Qualitative Eval Workflow

Eval is a human review step. It records evidence for your judgment; it does not automatically pass or fail a model.

## Run Eval

After training a model:

```powershell
python scripts\run_eval.py outputs\v002-qwen-stefan-lora evals\results_v002.jsonl evals\scores_v002.csv
```

This writes:

- `evals/results_v002.jsonl`: generated answers
- `evals/scores_v002.csv`: manual score sheet to fill in
- `evals/summary_v002.json`: qualitative review template

If MLflow is enabled, the eval run also logs the eval questions, generated answers, score sheet, summary template, generation settings, and linked training run ID when `run_metadata.json` exists in the adapter folder.

## Review

Fill in `scores_v002.csv`, then update `summary_v002.json`:

```json
{
  "decision": "promote_to_staging",
  "summary": "Better recruiter-facing project answers; still slightly verbose.",
  "notes": "Watch for hallucinated personal details in career questions."
}
```

Use your own qualitative judgment. Promotion still happens separately by changing `deployment/staging_model.json` or `deployment/production_model.json` in a PR.
