import os
import queue
import threading
import itertools
from concurrent.futures import Future

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI()

model = SentenceTransformer("all-MiniLM-L6-v2")

N_WORKERS = int(os.environ.get("EMBED_WORKERS", "2"))

_queue = queue.PriorityQueue()
_counter = itertools.count()

PRIORITY_SEARCH = 0
PRIORITY_INDEX = 1


class EmbedRequest(BaseModel):
    text: str


class BatchEmbedRequest(BaseModel):
    texts: list[str]


def _worker():
    while True:
        priority, seq, texts, future = _queue.get()
        try:
            vectors = model.encode(texts)
            future.set_result(vectors.tolist())
        except Exception as e:
            future.set_exception(e)
        finally:
            _queue.task_done()


for _ in range(N_WORKERS):
    t = threading.Thread(target=_worker, daemon=True)
    t.start()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/embed")
def embed(req: EmbedRequest):
    future = Future()
    _queue.put((PRIORITY_SEARCH, next(_counter), [req.text], future))
    vector = future.result(timeout=10)
    return {"vector": vector[0]}


@app.post("/embed/batch")
def embed_batch(req: BatchEmbedRequest):
    future = Future()
    _queue.put((PRIORITY_INDEX, next(_counter), req.texts, future))
    vectors = future.result(timeout=300)
    return {"vectors": vectors}
