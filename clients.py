import pymongo
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel
from minio import Minio
from sentence_transformers import SentenceTransformer
from config import (
    MONGO_URI,
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
)

# --- MongoDB ---
mongo_client = MongoClient(MONGO_URI)
db = (
    mongo_client.get_database()
    if mongo_client.get_database().name
    else mongo_client["flaskdb"]
)

users_collection = db["Users"]
documents_collection = db["Documents"]
document_chunks_collection = db["DocumentChunks"]


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
                }
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
if not minio_client.bucket_exists(minio_pdf_bucket_name):
    minio_client.make_bucket(minio_pdf_bucket_name)

# --- Embeddings ---
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
