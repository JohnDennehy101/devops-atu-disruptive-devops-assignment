#!/bin/bash
apt-get update
apt-get install -y python3-pip python3-venv git-lfs

mkdir -p /app
cd /app

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install fastapi uvicorn transformers accelerate bitsandbytes torch huggingface_hub scipy

if [ -f /app/llm.env ]; then
  sed -i "s/'//g" /app/llm.env
  export $(grep -v '^#' /app/llm.env | xargs)
fi

cat <<'EOF' > /app/main.py
from fastapi import FastAPI, Body, Header, HTTPException
from huggingface_hub import snapshot_download
import torch
import sys
import logging
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, BitsAndBytesConfig
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("llm-service")

app = FastAPI()
model_cache = {}

logger.info("Checking environment variables...")
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger.error("FATAL: API_KEY environment variable is missing!")
    raise ValueError("API_KEY environment variable is required")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/generate-test")
async def generate(
    payload: dict = Body(...), 
    x_api_key: str = Header(None)
):
    if x_api_key != API_KEY:
        logger.warning(f"Unauthorized access attempt with key: {x_api_key}")
        raise HTTPException(status_code=403, detail="Unauthorised")

    default_model = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-Coder-7B-Instruct")
    model_id = payload.get("model_id", default_model)
    diff = payload.get("diff", "")
    
    if model_id not in model_cache:
        logger.info(f"Attempting to load model: {model_id}")
        path = snapshot_download(repo_id=model_id)
        
        logger.info("Configuring 4-bit quantization")
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True
        )
        
        logger.info("Loading tokenizer and model")
        tokenizer = AutoTokenizer.from_pretrained(path)
        model = AutoModelForCausalLM.from_pretrained(
            path, 
            quantization_config=quantization_config,
            device_map="auto"
        )
        model_cache[model_id] = pipeline("text-generation", model=model, tokenizer=tokenizer)
        logger.info(f"Model {model_id} loaded successfully.")
    
    pipe = model_cache[model_id]
    prompt = f"### Instruction:\nAnalyze the git diff and write a Playwright test.\n\n### Diff:\n{diff}\n\n### Response:\n"
    
    logger.info("Generating response")
    output = pipe(prompt, max_new_tokens=500, temperature=0.1)
    return {"generated_code": output[0]['generated_text']}
EOF

cat <<EOF > /etc/systemd/system/llm.service
[Unit]
Description=FastAPI LLM Service
After=network.target

[Service]
User=root
WorkingDirectory=/app
EnvironmentFile=/app/llm.env
Environment="PYTHONUNBUFFERED=1"
Environment="PYTHONPATH=/app"
Environment="LD_LIBRARY_PATH=/usr/local/cuda/lib64"
ExecStart=/app/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable llm
systemctl start llm