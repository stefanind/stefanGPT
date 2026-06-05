# Research Optimization Priors Project

## Summary
The research-optimization-priors project is independent research on whether teacher-derived or data-derived prior signals can help small language models learn or optimize more effectively.

## Key Facts
- Project type: independent machine learning research / language model optimization project
- Main research question: what kinds of prior signals can help a small language model learn or optimize more effectively?
- The project began as an exploration of OpenAI's Parameter Golf challenge
- The repository continues to use the Parameter Golf-style train_gpt.py baseline, tokenizer workflow, and FineWeb data pipeline as a controlled experimental substrate
- The project is not an official OpenAI project and is not affiliated with or endorsed by OpenAI
- Baseline model setup includes 9 transformer layers, width 512, 8 attention heads, 4 KV heads, 1024-token SentencePiece vocabulary, tied embeddings, Muon for matrix parameters, Adam for embeddings/scalars, and a 10-minute comparison cap
- Experiments 1-5 focus on data priors
- Experiments 7-9 focus on teacher weight priors
- Experiments 6 and 10-15 focus on teacher directional transforms, hidden geometry, embedding-anchor geometry, and logits
- Example interventions include bigram prior logit injection, KL regularization, weight/subspace initialization, relational KD, activation embedding KL, big-teacher transformation KD, and classic logit distillation
- Later diagnostic work examines teacher norm flow and tries to understand whether large transformation signals come from directional changes, residual stream scale growth, skip connections, attention updates, or MLP updates

## My Role
- Designed and implemented research experiments around optimization priors for small language models
- Modified the baseline GPT training script to test one intervention at a time
- Built data-prior experiments using token statistics such as bigram priors
- Built teacher-assisted experiments involving hidden-state geometry, relational KD, transformation matching, and logit distillation
- Added diagnostic work to interpret teacher signal scale and norm flow
- Used controlled comparisons against a baseline training script to evaluate whether each added signal helped

## Technologies
- Python
- PyTorch
- NumPy
- datasets
- Hugging Face Hub
- tiktoken
- SentencePiece
- FineWeb
- Muon optimizer
- Adam optimizer
- Distributed training / DDP

## Safe Answer Guidance
The bot can say this project explores data-derived and teacher-derived optimization priors for small transformer language models. Do not claim the project proves a general solution for faster LLM training. Do not claim affiliation with OpenAI. Be careful to describe the work as experimental research unless stronger results are documented elsewhere.
