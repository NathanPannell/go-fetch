import os
import io
import fitz  # PyMuPDF
from celery import Celery
from minio import Minio
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer

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

# Initialize SentenceTransformer (lazy load could be better but this works for top-level if worker only does this)
model = SentenceTransformer('all-MiniLM-L6-v2')

def semantic_chunking(text, chunk_size=500, overlap=50):
    """Simple word-based chunking with overlap."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks

@app.task
def process_document(document_id, owner_id, filename):
    try:
        # 1. Fetch from MinIO
        response = minio_client.get_object(bucket_name, document_id)
        pdf_bytes = response.read()
        response.close()
        response.release_conn()

        # 2. Parse with PyMuPDF
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(pdf_document)
        
        full_text = ""
        for page_num in range(page_count):
            page = pdf_document.load_page(page_num)
            full_text += page.get_text() + "\n"
            
        pdf_document.close()

        # 3. Chunking
        chunks = semantic_chunking(full_text)
        
        # 4. Vectorize and Store
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
            
        if chunk_records:
            document_chunks_collection.insert_many(chunk_records)
            
        # 5. Update Document Status
        documents_collection.update_one(
            {"document_id": document_id},
            {"$set": {"status": "ready", "page_count": page_count}}
        )

    except Exception as e:
        print(f"Error processing document {document_id}: {e}")
        documents_collection.update_one(
            {"document_id": document_id},
            {"$set": {"status": "failed"}}
        )
