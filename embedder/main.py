import logging
import os
import queue
import threading
from concurrent.futures import Future
from contextlib import asynccontextmanager

import onnxruntime as ort
from fastembed import TextEmbedding
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

log = logging.getLogger("embedder")
logging.basicConfig(level=logging.INFO)

N_SEARCH_WORKERS = int(os.environ.get("EMBED_SEARCH_WORKERS", "2"))
N_INDEX_WORKERS = int(os.environ.get("EMBED_INDEX_WORKERS", "2"))

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

model: TextEmbedding | None = None
search_queue: queue.Queue = queue.Queue()  # latency-sensitive, single queries
batch_queue: queue.Queue = queue.Queue()  # throughput-oriented, PDF chunks


def _worker(q: queue.Queue) -> None:
    while True:
        texts, future = q.get()
        try:
            vectors = [v.tolist() for v in model.embed(texts)]
            future.set_result(vectors)
        except Exception as e:
            future.set_exception(e)
        finally:
            q.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    available = ort.get_available_providers()
    if "CUDAExecutionProvider" in available:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    else:
        providers = ["CPUExecutionProvider"]
    log.info("embedder providers selected: %s", providers)
    model = TextEmbedding(model_name=MODEL_NAME, providers=providers)
    # warm-up: forces model download + ORT session init before healthcheck passes
    list(model.embed(["warmup"]))
    log.info("embedder model loaded: %s", MODEL_NAME)
    for _ in range(N_SEARCH_WORKERS):
        threading.Thread(target=_worker, args=(search_queue,), daemon=True).start()
    for _ in range(N_INDEX_WORKERS):
        threading.Thread(target=_worker, args=(batch_queue,), daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)


class EmbedRequest(BaseModel):
    text: str


class EmbedBatchRequest(BaseModel):
    texts: list[str]


@app.get("/health")
def health():
    if model is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "reason": "model not loaded"},
        )
    return {"status": "ok"}


@app.post("/embed")
def embed(req: EmbedRequest):
    future: Future = Future()
    search_queue.put(([req.text], future))
    vectors = future.result(timeout=10)
    return {"vector": vectors[0]}


@app.post("/embed/batch")
def embed_batch(req: EmbedBatchRequest):
    future: Future = Future()
    batch_queue.put((req.texts, future))
    vectors = future.result(timeout=300)
    return {"vectors": vectors}
