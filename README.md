This repository is the beginning of a personal AI system designed to represent how I think, communicate, and work.

The goal is to finetune an open model and combine it with RAG so it can reflect my reasoning style, project experience, technical background, and professional judgment.

My hope is that recruiters and collaborators can interact with the system directly to better understand who I am, what I have built, and how I approach problems. Instead of relying only on a resume or making assumptions, they can ask the AI questions and receive answers grounded in specific facts about my work while still reflecting my voice and perspective.  


## Where this project is at  

Currently testing by building the app interface for my github.io pages so someone can talk to my AI twin.


## quick install and run commands

Note: this assumes running on an instance that has CUDA and torch already

git clone https://github.com/stefanind/stefanGPT

pip install --upgrade pip  
pip install -r requirements.txt  

training:  
python scripts/train_qlora.py configs/qwen_lora_v001.json  

evaluation:  
python scripts/run_eval.py outputs/v001-qwen-stefan-lora evals/results_v001.jsonl evals/scores_v001.csv  

command for VERIFYING CUDA + TORCH, if needed  
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"  

