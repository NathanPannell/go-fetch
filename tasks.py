import os
import io
import fitz  # PyMuPDF
from celery import Celery
from minio import Minio
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer


# --- Infrastructure Setup ---

# Get Environment Variables
chunk_size = os.getenv("DOCUMENT_CHUNK_SIZE", 400)
overlap = os.getenv("DOCUMENT_CHUNK_OVERLAP_SIZE", 60)

# Initialize Celery
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
app = Celery('tasks', broker=redis_url)

# Initialize MongoDB
mongo_client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/flaskdb'))
db = mongo_client.get_database() if mongo_client.get_database().name else mongo_client['flaskdb']
documents_collection = db['Documents']
document_chunks_collection = db['DocumentChunks']

# Initialize MinIO
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=False
)
bucket_name = "raw-pdfs"

# Initialize SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')


# --- Helper Functions ---

def fetch_pdf(bucket_name, document_id):
    response = minio_client.get_object(bucket_name, document_id)
    pdf_bytes = response.read()
    response.close()
    response.release_conn()
    return pdf_bytes

def extract_text(pdf_bytes):
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = len(pdf_document)
    full_text = "\n".join(page.get_text() for page in pdf_document)
    pdf_document.close()
    return full_text, page_count

def get_chunks(text):
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

def get_embeddings(chunks):
    chunk_records = []
    for chunk in chunks:
        embedding = model.encode(chunk).tolist()
        chunk_records.append({
            "owner_id": owner_id,
            "text": chunk,
            "vector_embedding": embedding,
            "document_id": document_id,
            "filename": filename
        })
    return chunk_records

# --- Tasks ---
@app.task
def process_document(document_id, owner_id, filename):
    try:
        pdf_bytes = fetch_pdf(bucket_name, document_id)

        full_text, page_count = extract_text(pdf_bytes)

        chunks = get_chunks(full_text)

        chunk_records = get_embeddings(chunks)

        if chunk_records:
            document_chunks_collection.insert_many(chunk_records)

        documents_collection.update_one(
            {"document_id": document_id},
            {"$set": {"status": "ready", "page_count": page_count}}
        )

    except Exception as e:
        documents_collection.update_one(
            {"document_id": document_id},
            {"$set": {"status": "failed"}}
        )
