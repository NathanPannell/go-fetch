# Go Fetch

A scalable semantic search API. Users upload documents (PDFs), which are processed asynchronously and indexed as vector embeddings for semantic search.

## Stack

- Python, Flask, JWT auth (flask-jwt-extended)
- MongoDB (Atlas local) — document and user storage, vector search index
- Redis + Celery — async task queue for document ingestion
- MinIO — object storage for uploaded files
- sentence-transformers + PyTorch — embedding generation
- PyMuPDF — PDF text extraction
- Docker Compose — all services containerized

## Build and run

```bash
cp .env.example .env
make dev      # start all services in background
make test     # run integration tests in isolated Docker stack
make profile  # run profiling: Locust load + cProfile/tracemalloc output to profile/results/
```

## Key directories

- `routes/` — Flask blueprints: auth, documents, search, health
- `tasks.py` — Celery task definitions (document processing pipeline)
- `clients.py` — MongoDB, MinIO, Redis client init and vector index setup
- `config.py` — env-driven config
- `brainstorm\project_spec.pdf` — Summary of requirements, read this prior to creating most gh issues.

## Conventions

- Standard Python/Flask conventions
- Keep route handlers thin; business logic in tasks or helpers
- No emoji in code, commits, or docs
- Use `.github/ISSUE_TEMPLATE/feature_request.md` for all new issues (Summary, Scope, Out of scope, Acceptance criteria)

## Planned work

- **Logging**: structured logging across the Flask app and Celery workers
- **Redis cache**: cache frequent search results or embeddings to reduce latency
