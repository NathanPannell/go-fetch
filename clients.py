import pymongo
import redis as redis_lib
import requests as http_requests
from pymongo import MongoClient
from minio.error import S3Error
from pymongo.operations import SearchIndexModel
from minio import Minio
from config import (
    MONGO_URI,
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    REDIS_URL,
    EMBEDDER_URL,
)

# --- MongoDB ---
mongo_client = MongoClient(MONGO_URI, maxPoolSize=30)
db = (
    mongo_client.get_database()
    if mongo_client.get_database().name
    else mongo_client["flaskdb"]
)

users_collection = db["Users"]
documents_collection = db["Documents"]
document_chunks_collection = db["DocumentChunks"]


def init_db_indexes():
    users_collection.create_index("username", unique=True)
    documents_collection.create_index("owner_id")


def init_vector_search_index():
    if "DocumentChunks" not in db.list_collection_names():
        db.create_collection("DocumentChunks")

    existing_indices = list(document_chunks_collection.list_search_indexes())
    if any(idx.get("name") == "vector_index" for idx in existing_indices):
        return

    model_def = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "vector_embedding",
                    "numDimensions": 384,
                    "similarity": "cosine",
                },
                {
                    "type": "filter",
                    "path": "owner_id",
                },
            ]
        },
        name="vector_index",
        type="vectorSearch",
    )
    document_chunks_collection.create_search_index(model=model_def)


# --- MinIO ---
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)
minio_pdf_bucket_name = "uploaded-pdfs"

try:
    minio_client.make_bucket(minio_pdf_bucket_name)
except S3Error:
    # bucket already created by replica api
    pass

# --- Redis cache (separate from Celery broker connection) ---
redis_client = redis_lib.from_url(REDIS_URL, decode_responses=True)

# --- Embeddings (via sidecar) ---


def embed_text(text):
    resp = http_requests.post(
        f"{EMBEDDER_URL}/embed", json={"text": text}, timeout=10
    )
    resp.raise_for_status()
    return resp.json()["vector"]


def embed_batch(texts):
    resp = http_requests.post(
        f"{EMBEDDER_URL}/embed/batch", json={"texts": texts}, timeout=120
    )
    resp.raise_for_status()
    return resp.json()["vectors"]
