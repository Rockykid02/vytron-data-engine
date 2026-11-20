# Vytron Data Engine

Standalone, local-first document ingestion and knowledge retrieval MVP. Designed to connect to Vytron's AI server later through HTTP.

## Included
- Responsive dark-blue admin dashboard.
- PDF, EPUB and TXT upload and text extraction.
- Lightweight Shona-language heuristic (not a production classifier).
- Small same-domain website crawler that checks `robots.txt`.
- Human approval queue: all ingested documents start as `pending`.
- SQLite FTS5 search over approved documents.
- JSON API for later Vytron integration.
- Optional admin API-key protection.

## Not included yet
This is not a model trainer and does not generate AI answers. It provides searchable source excerpts to a future Vytron model. Semantic vector search, OCR, background workers, production authentication and fine-tuning are future upgrades.

## Run locally
Python 3.10+ required.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

On iPhone, the dashboard is responsive, but running the Python service is easiest in a computer or cloud development environment.

## Secure it
For any shared deployment, set a long random `ADMIN_API_KEY` in the server environment. Enter the same key in the dashboard. Do not commit `.env`, publish the key in frontend code, or expose this admin service publicly without HTTPS and proper authentication. The dashboard stores the key in that browser's localStorage; use only on a trusted device.

## API
- `GET /api/health` public health check
- `GET /api/stats`
- `GET /api/documents?status=pending`
- `GET /api/documents/{id}`
- `POST /api/upload` multipart field `file`
- `POST /api/crawl` JSON: `{"url":"https://example.org","max_pages":5}`
- `POST /api/documents/{id}/approve`
- `POST /api/documents/{id}/reject`
- `DELETE /api/documents/{id}`
- `POST /api/search` JSON: `{"query":"Shona proverb","limit":5}`
- `GET /api/jobs`

Protected endpoints accept `X-API-Key` if `ADMIN_API_KEY` is set.

## Future Vytron connection
Vytron's backend can call `POST /api/search` with the user's question. The service returns approved source excerpts, titles and URLs. The Vytron model can use those passages as context and cite the sources in its answer. Keep this service private or behind authenticated HTTPS.

## Responsible collection
Only ingest material you own, have permission to use, or that is licensed for the intended use. Publicly accessible does not mean public domain or automatically permitted for AI training. Respect copyright, privacy, site terms, robots.txt and rate limits. Every item requires human approval before search.

## Production roadmap
1. Real authentication, roles, audit logs, HTTPS and rate limiting.
2. Background job queue and crawl scheduling.
3. OCR for scanned documents.
4. Better Shona language identification reviewed by native speakers.
5. Embeddings + Qdrant semantic search and chunking.
6. RAG answer orchestration with source citations.
7. Dataset export and separate evaluated fine-tuning pipeline.
8. Backups, monitoring, malware scanning and retention controls.
