# GPT Project

## Summary
The GPT project is a from scratch educational language modeling project that began as a GPT-2 implementation and was extended with modern transformer architecture and training system features.

## Key Facts
- Project type: LLM architecture / training systems project
- Original foundation: GPT-2 implementation inspired by Andrej Karpathy's Neural Networks: Zero to Hero material
- Legacy dense baseline: validation loss of 3.1155 at step 19,072
- Legacy dense baseline: best HellaSwag accuracy of 0.2934 at step 17,500
- The legacy baseline did not include MoE, SwiGLU, RMSNorm, KV cache, or GQA/MQA
- Current architecture additions include Mixture of Experts, KV cache, GQA/MQA, RMSNorm, and SwiGLU
- Training/system additions include between-shard shuffling, PyTorch profiler experiments, torch.compile profiling, fused bias + GELU kernel work, FSDP for educational purposes, and RoPE
- Training code supports DDP, gradient accumulation, bfloat16 autocast, TF32 matmul precision, AdamW, validation loss logging, checkpointing, sampling, and HellaSwag evaluation
- Data paths in the code support tinyshakespeare for small experiments and FineWeb10B for larger training runs

## My Role
- Built and extended a GPT-style transformer implementation
- Implemented modern transformer components such as MoE, KV cache, GQA/MQA, RMSNorm, SwiGLU, and RoPE
- Wrote training/evaluation infrastructure for distributed training, gradient accumulation, validation, checkpointing, sampling, and HellaSwag evaluation
- Profiled GPU utilization and compared underutilized, fully utilized, and torch.compile-optimized A100 training runs
- Added educational systems work around kernel fusion and fused bias + GELU

## Technologies
- Python
- PyTorch
- CUDA
- C++
- tiktoken
- DDP / torch.distributed
- torch.profiler
- HellaSwag
- FineWeb10B
- tinyshakespeare

## Safe Answer Guidance
The bot can say this project demonstrates from-scratch LLM implementation, transformer architecture, distributed training, inference optimization, and GPU profiling. Do not claim the upgraded architecture completed a full successful training run unless that is documented elsewhere. Clearly distinguish the documented legacy dense baseline results from the newer architecture additions. Do not claim the model is state-of-the-art.
