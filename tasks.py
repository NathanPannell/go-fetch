import cProfile
import tracemalloc
import os

import fitz  # PyMuPDF
from celery import Celery
from config import REDIS_URL, DOCUMENT_CHUNK_SIZE, DOCUMENT_CHUNK_OVERLAP_SIZE
from clients import (
    documents_collection,
    document_chunks_collection,
    minio_client,
    minio_pdf_bucket_name,
    embedding_model,
)
from bson import ObjectId

app = Celery("tasks", broker=REDIS_URL)


# --- Helper Functions ---


def _fetch_pdf(bucket_name, document_id):
    response = minio_client.get_object(bucket_name, document_id)
    pdf_bytes = response.read()
    response.close()
    response.release_conn()
    return pdf_bytes


def _extract_text(pdf_bytes):
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = len(pdf_document)
    full_text = "\n".join(page.get_text() for page in pdf_document)
    pdf_document.close()
    return full_text, page_count


def _get_chunks(text):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + DOCUMENT_CHUNK_SIZE])
        if chunk.strip():
            chunks.append(chunk)
        i += DOCUMENT_CHUNK_SIZE - DOCUMENT_CHUNK_OVERLAP_SIZE
    return chunks


def _get_embeddings(chunks, owner_id, document_id, filename):
    chunk_records = []
    for chunk in chunks:
        embedding = embedding_model.encode(chunk).tolist()
        chunk_records.append(
            {
                "owner_id": owner_id,
                "text": chunk,
                "vector_embedding": embedding,
                "document_id": document_id,
                "filename": filename,
            }
        )
    return chunk_records


def _start_profiling():
    pr = cProfile.Profile()
    tracemalloc.start()
    pr.enable()
    return pr


def _dump_profiling(pr, task_id):
    pr.disable()
    os.makedirs("/profile/results", exist_ok=True)
    pr.dump_stats(f"/profile/results/worker_{task_id}.prof")
    snap = tracemalloc.take_snapshot()
    tracemalloc.stop()
    with open(f"/profile/results/memory_{task_id}.txt", "w") as f:
        for s in snap.statistics("lineno")[:20]:
            f.write(str(s) + "\n")


# --- Tasks ---


@app.task
def process_document(document_id, owner_id, filename):
    doc = documents_collection.find_one({"_id": ObjectId(document_id)})
    if not doc or doc.get("status") != "processing":
        return

    profiling = os.environ.get("PROFILING_ENABLED", "").lower() == "true"
    if profiling:
        pr = _start_profiling()

    try:
        pdf_bytes = _fetch_pdf(minio_pdf_bucket_name, document_id)

        full_text, page_count = _extract_text(pdf_bytes)

        chunks = _get_chunks(full_text)

        chunk_records = _get_embeddings(chunks, owner_id, document_id, filename)
        if chunk_records:
            document_chunks_collection.insert_many(chunk_records)

        documents_collection.update_one(
            {"_id": ObjectId(document_id), "status": "processing"},
            {"$set": {"status": "ready", "page_count": page_count}},
        )

    except Exception as e:
        documents_collection.update_one(
            {"_id": ObjectId(document_id), "status": "processing"},
            {"$set": {"status": "failed", "error_message": str(e)}},
        )

    finally:
        if profiling:
            task_id = process_document.request.id or document_id
            _dump_profiling(pr, task_id)
