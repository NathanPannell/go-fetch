import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
PEPPER = os.getenv("PEPPER")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DOCUMENT_CHUNK_SIZE = int(os.getenv("DOCUMENT_CHUNK_SIZE", 400))
DOCUMENT_CHUNK_OVERLAP_SIZE = int(os.getenv("DOCUMENT_CHUNK_OVERLAP_SIZE", 60))
EMBEDDER_URL = os.getenv("EMBEDDER_URL", "http://embedder:8001")
EMBEDDING_CACHE_TTL = int(os.getenv("EMBEDDING_CACHE_TTL", 3600))
SEARCH_CACHE_TTL = int(os.getenv("SEARCH_CACHE_TTL", 86400))
