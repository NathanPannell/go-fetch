FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY embedder/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY embedder/main.py main.py

ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV TOKENIZERS_PARALLELISM=false

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]

# GPU deployment: swap the base image above to a CUDA 12.x image (e.g.
# nvidia/cuda:12.2.0-cudnn8-runtime-ubuntu22.04), replace `fastembed` with
# `fastembed-gpu` in requirements.txt (the two packages cannot coexist), and
# expose the GPU to the container via `--gpus all` or compose
# `deploy.resources.reservations.devices`. The provider-detection in main.py
# picks up CUDAExecutionProvider automatically when ORT reports it available.
