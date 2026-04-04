# Go Fetch: Scalable Semantic Search

A REST API for uploading and semantically searching documents. PDFs are ingested asynchronously, chunked, embedded, and indexed for vector search.

## Stack

- Flask, JWT auth
- MongoDB (Atlas local) — document storage and vector search index
- Redis + Celery — async document processing queue
- MinIO — object storage for uploaded files
- sentence-transformers — embedding generation
- PyMuPDF — PDF text extraction

## Getting Started

Copy the environment file and start all services:

```bash
cp .env.example .env
make dev
```

The API will be available at `http://localhost:8080`.

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/auth/register` | Register a user |
| POST | `/auth/login` | Login, returns JWT |
| POST | `/documents` | Upload a document (PDF) |
| GET | `/documents` | List uploaded documents |
| GET | `/search` | Semantic search over indexed documents |

## Testing

```bash
make test
```

Runs the integration test suite in an isolated Docker Compose stack.
