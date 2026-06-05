# CUDA SGEMM Project

## Summary
The CUDA SGEMM project implements and benchmarks progressively optimized single-precision matrix multiplication kernels to understand how GPU kernels become efficient.

## Key Facts
- Project type: CUDA systems / performance engineering project
- Main task: SGEMM, or single-precision general matrix multiplication
- Benchmark shape: M=N=K=4096, FP32
- Benchmark GPU: NVIDIA GeForce RTX 4070
- Baseline: cuBLAS using CUBLAS_DEFAULT_MATH
- cuBLAS benchmark in the README: 6.23215 ms and 22,053.2 GFLOPs
- Best custom kernel listed in the README: vec kernel at 14.1554 ms, 9,709.29 GFLOPs, and 44.0% of cuBLAS throughput
- Kernels listed in the benchmark table include naive, coalesced, shared, 1d, 2d, and vec
- Project status: unfinished
- Future work listed in the README includes bank-conflict handling with swizzling/padding, autotuning, warp tiling, and additional profiling

## My Role
- Implemented CUDA/C++ matrix multiplication kernels
- Built a benchmark setup to compare custom kernels against cuBLAS
- Measured runtime, throughput, and speedup across different kernel implementations
- Used the project to understand GPU memory access, kernel efficiency, and matrix multiplication optimization
- Continued iterating on more advanced CUDA optimization techniques

## Technologies
- CUDA
- C++
- CMake
- cuBLAS
- NVIDIA CUDA Toolkit
- Python
- Shell scripts

## Safe Answer Guidance
The bot can say this project involved implementing and benchmarking CUDA SGEMM kernels against cuBLAS to learn GPU performance engineering. Do not claim the custom kernels beat cuBLAS. The README shows the best custom kernel is still below cuBLAS performance. Do not claim the project is finished or production-grade.
