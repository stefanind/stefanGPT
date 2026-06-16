This repository is a personal AI system designed to represent how I think, communicate, and work.

The goal is to finetune an open model and combine it with RAG so it can reflect my reasoning style, project experience, technical background, and professional judgment.

My hope is that recruiters and collaborators can interact with the system directly to better understand who I am, what I have built, and how I approach problems. Instead of relying only on a resume or making assumptions, they can ask the AI questions and receive answers grounded in specific facts about my work while still reflecting my voice and perspective.  


## Where this project is at  

v001 is currently deployed and operational on my github pages. Try it out: https://stefanind.github.io/

For v002:  
Will concurrently add new data to improve where it lacks.  
I have to add more recruiter-facing data, such as info about my projects, my takes on them, and behavioral-style interview questions and answers.  

Also, incorporating staging vs production, versioning with MLFlow, and CI/CD.  

Later on I will add more robust evaluation.


## v001 specs

150 sft examples:  worldview, personal, scenario, ai, career, books  

eval set: 50 samples focused on targetting the sft data  

RAG: Super basic. Split files by char count. Chunks only have source + chunk_id + text. Retrieval is pure embedding similarity over top_k. Not aligned w/ eval and production.  

## v002 specs  

SFT examples: added another 150 to hit 300. Based on past eval, needed to have more recruiter-facing questions and project-based questions.  

Eval set: improved questions to target the new data. Added required points and failure modes.

RAG: Chunks include headings now and by markdown sections. New retrieval gets more candidates and applies a small lexical boost to keywords to ensure short factual questions get the right content. Now is called during run_eval.py.

Added CI/CD via Github Actions for CI and RunPod Serverless for CD.

MLFlow: Logs training and eval.  

Changed from 0.2 val set to 0.1 because training data is precious and hard to make.

## quick install and run commands

Note: this assumes running on an instance that has CUDA and torch already

git clone https://github.com/stefanind/stefanGPT

pip install --upgrade pip  
pip install -r requirements.txt  

---

create data:  
python scripts/build_sft_jsonl.py (put version here)  

validate data:  
python scripts/validate_jsonl.py (put version here)  

training:  
python scripts/train_qlora.py configs/qwen_lora_v002.json  

training runs are tracked with MLflow; see docs/mlflow_training.md  

evaluation:  
python scripts/run_eval.py outputs/v002-qwen-stefan-lora evals/results_v002.jsonl evals/scores_v002.csv  

command for VERIFYING CUDA + TORCH, if needed  
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"  
