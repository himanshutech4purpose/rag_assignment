# Low-Level Design (LLD): RAG Document Q&A App

## 1. Project Structure

```
.
├── backend/
│   ├── alembic/
│   │   ├── env.py                        # Async Alembic runner
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 20260617_initial_schema.py  # Tables, indexes, extensions
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # App factory, lifespan, middleware
│   │   ├── config.py                     # Pydantic Settings (env vars)
│   │   ├── database.py                   # asyncpg pool + Alembic runner
│   │   ├── dependencies.py               # FastAPI Depends providers
│   │   ├── exceptions.py                 # Domain exceptions + global handlers
│   │   ├── logging_config.py             # Structured logging setup
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   └── models.py                 # Internal dataclasses (Chunk, Message, …)
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                   # SQLAlchemy declarative base
│   │   │   └── tables.py                 # SQLAlchemy ORM table models
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── api.py                    # Pydantic request/response schemas
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── chunk_repo.py             # document_chunks SQL + RRF fusion
│   │   │   ├── conversation_repo.py      # conversations + messages SQL
│   │   │   └── document_repo.py          # documents SQL
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── health.py                 # GET /api/health
│   │   │   ├── documents.py              # /api/upload, /api/documents/*
│   │   │   └── conversations.py          # /api/conversations/*
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── ingestion/                # Upload → parse → chunk → embed → store
│   │       │   ├── __init__.py
│   │       │   ├── ingestion.py
│   │       │   ├── chunker.py            # Character-based text splitter
│   │       │   ├── embeddings.py         # SentenceTransformer wrapper (async)
│   │       │   ├── pdf_parser.py         # pypdf text + image extractor
│   │       │   └── storage.py            # MinIO wrapper (async)
│   │       ├── retrieval/                # Hybrid search + RRF + reranking
│   │       │   ├── __init__.py
│   │       │   ├── retrieval.py
│   │       │   └── reranker.py           # CrossEncoder wrapper (async)
│   │       ├── conversation_service.py   # Title gen, history, message persistence
│   │       └── llm.py                    # Groq / OpenAI via LangChain
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── api.js                        # Axios + fetch/SSE helpers
│       ├── components/
│       │   ├── Chat.jsx                  # Streaming chat UI
│       │   ├── Upload.jsx                # PDF upload + chunk preview
│       │   ├── Citation.jsx              # Source citation card
│       │   ├── Documents.jsx             # Document list with delete
│       │   ├── Sidebar.jsx               # Conversation list + New Chat
│       │   └── Navbar.jsx
│       └── pages/
│           ├── UploadPage.jsx
│           ├── DocumentsPage.jsx
│           ├── ChatPage.jsx
│           └── SettingsPage.jsx          # LLM/chunking settings (localStorage)
├── docker-compose.yml
├── .env.example
└── README.md
```

## 2. Environment Variables

See [.env.example](.env.example) for the full list with defaults. Required variables:

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key (or set `OPENAI_API_KEY` and switch provider) |
| `DATABASE_URL` | Yes | asyncpg-compatible PostgreSQL URL |
| `MINIO_ENDPOINT` | Yes | `host:port` of MinIO server |
| `MINIO_ACCESS_KEY` | Yes | MinIO access key |
| `MINIO_SECRET_KEY` | Yes | MinIO secret key |

Key optional variables with their defaults:

```bash
LLM_MODEL=llama-3.1-8b-instant
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
CHUNK_SIZE=500
CHUNK_OVERLAP=100
TOP_K=5
SEMANTIC_TOP_K=20
LEXICAL_TOP_K=20
RERANK_TOP_K=5
RRF_K=60
HISTORY_LIMIT=10
MAX_UPLOAD_FILE_SIZE=10485760   # 10 MB
MAX_UPLOAD_FILES=3
CORS_ORIGINS=http://localhost:3000
```

## 3. Database Schema

Managed by Alembic; see `backend/alembic/versions/20260617_initial_schema.py`.

### `documents`
| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK DEFAULT gen_random_uuid()` | |
| `name` | `VARCHAR(255) NOT NULL` | Original filename |
| `size_bytes` | `INTEGER NOT NULL` | |
| `minio_object` | `VARCHAR(255) NOT NULL` | `{uuid}_{filename}` |
| `status` | `VARCHAR(50) NOT NULL DEFAULT 'uploaded'` | `processing` → `indexed` |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | |

### `document_chunks`
| Column | Type | Notes |
|---|---|---|
| `id` | `SERIAL PK` | |
| `document_id` | `UUID REFERENCES documents(id) ON DELETE CASCADE` | |
| `document_name` | `VARCHAR(255) NOT NULL` | Denormalized for citations |
| `page_number` | `INTEGER` | Nullable |
| `chunk_index` | `INTEGER NOT NULL` | Global sequence across document |
| `content` | `TEXT NOT NULL` | Raw chunk text |
| `embedding` | `vector(384)` | all-MiniLM-L6-v2 output |
| `search_vector` | `tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED` | For lexical search |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | |

Indexes:
- `HNSW` on `embedding vector_cosine_ops` — ANN cosine search
- `GIN` on `search_vector` — full-text search
- B-tree on `document_id` — cascade delete support

### `conversations`
| Column | Type | Notes |
|---|---|---|
| `id` | `UUID PK DEFAULT gen_random_uuid()` | |
| `title` | `VARCHAR(255)` | Auto-generated from first question |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | |
| `updated_at` | `TIMESTAMP DEFAULT NOW()` | Bumped on each new message |

### `messages`
| Column | Type | Notes |
|---|---|---|
| `id` | `SERIAL PK` | |
| `conversation_id` | `UUID REFERENCES conversations(id) ON DELETE CASCADE` | |
| `role` | `VARCHAR(20) NOT NULL` | `user` or `assistant` |
| `content` | `TEXT NOT NULL` | |
| `sources` | `JSONB` | Null for user messages |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | |

Index: B-tree on `conversation_id`.

## 4. API Specification

### Health
```
GET /api/health
→ 200: { "status": "ok" }
```

### Documents
```
POST /api/upload?chunk_size=500&chunk_overlap=100
Content-Type: multipart/form-data
Body: files[] (max 3 PDFs, each ≤ 10MB)
→ 200: { "documents": [{ "id", "name", "status", "chunks_inserted", "images_ignored" }] }
→ 400: { "error": "ValidationError", "detail": "..." }

GET /api/documents
→ 200: { "documents": [{ "id", "name", "size_bytes", "status", "created_at" }] }

GET /api/documents/{id}/chunks
→ 200: [{ "id", "document_name", "page_number", "chunk_index", "content" }]
→ 400: invalid UUID format

DELETE /api/documents/{id}
→ 200: { "message": "Document deleted successfully" }
→ 404: { "error": "NotFoundError", "detail": "..." }
```

### Conversations
```
POST /api/conversations
Body: { "title": "optional" }
→ 201: { "id", "title", "created_at", "updated_at" }

GET /api/conversations
→ 200: { "conversations": [...] }  # ordered by updated_at DESC

GET /api/conversations/{id}
→ 200: { "id", "title", "created_at", "updated_at", "messages": [...] }
→ 404: { "error": "NotFoundError", "detail": "..." }

DELETE /api/conversations/{id}
→ 200: { "message": "Conversation deleted successfully" }
→ 404: not found

POST /api/conversations/{id}/ask
Body: {
  "question": "string",
  "provider": "groq" | "openai",   # default: "groq"
  "model": "string | null",         # default: env LLM_MODEL
  "api_key": "string | null",       # default: env key
  "system_prompt": "string | null",
  "max_tokens": 1..8192 | null,
  "history_limit": 1..50 | null
}
→ 200: { "answer": "string", "sources": [{ "document_name", "page_number", "chunk_index", "content", "score" }] }
→ 400: no documents uploaded / empty question
→ 503: LLM unavailable

POST /api/conversations/{id}/ask/stream
Body: same as /ask
→ 200: text/event-stream

SSE event format:
  data: <token>\n\n          # one per LLM token
  event: sources
  data: [{...}]\n\n          # after all tokens
  data: [DONE]\n\n           # end of stream

  event: error
  data: {"error": "..."}\n\n # on LLM failure
```

## 5. Service Layer

### `IngestionService` (`services/ingestion/ingestion.py`)
```
ingest(filename, content, chunk_size?, chunk_overlap?):
  1. Generate UUID document_id
  2. Upload to MinIO: object_name = f"{document_id}_{filename}"
  3. DB transaction:
     a. INSERT documents (status="processing")
     b. extract_text(content) → pages, images_ignored   [asyncio.to_thread]
     c. split_text(page.text) → chunks                  [sync]
     d. embeddings.embed([c.content for c in chunks])   [asyncio.to_thread]
     e. chunk_repo.insert_many(conn, chunks)
     f. UPDATE documents SET status="indexed"
  4. Return DocumentUploadResult

On exception:
  - Transaction rolls back (atomically undoes a–f)
  - MinIO object deleted (cleanup; cleanup errors are logged, not re-raised)
  - Original exception re-raised

delete_document(conn, document_id):
  1. Get minio_object name from DB
  2. DELETE document row (cascade deletes chunks)
  3. Delete MinIO object
  (DB delete happens before storage delete: failed DB → no orphan record)
```

### `RetrievalService` (`services/retrieval/retrieval.py`)
```
search(conn, query_text, top_k?):
  1. embed([query_text])[0]                              → query_embedding
  2. chunk_repo.semantic_search(conn, embedding, 20)    → semantic_chunks
  3. chunk_repo.lexical_search(conn, query_text, 20)    → lexical_chunks
  4. chunk_repo.fuse_rrf(semantic, lexical)             → fused (sorted by RRF score)
  5. reranker.rerank(query_text, fused[:40], top_k)    → reranked

RRF formula: score += 1 / (k + rank) for each list
```

### `ConversationService` (`services/conversation_service.py`)
```
add_user_message(conn, conversation_id, question, history_limit?):
  1. Validate question is non-empty
  2. Check conversation exists (raises NotFoundError if not)
  3. INSERT user message
  4. maybe_update_title: if title == "New conversation", generate from question
  5. Fetch last N messages (history_limit or settings.history_limit)
  6. Return history list

generate_title(question):
  - First 6 words, max 40 chars, appends "..." if truncated
```

### `LLMService` (`services/llm.py`)
```python
# Prompt template (default):
"""You are a helpful assistant. Use ONLY the following context...

Context:
{context}          # formatted chunks: [doc - page N, chunk M]\n{content}

Previous conversation:
{history}          # "User: ...\n\nAssistant: ..."

Question: {question}

Answer:"""

answer(question, chunks, history, provider, model, api_key, system_prompt, max_tokens):
  chain = build_prompt(system_prompt) | _get_llm(provider, model, api_key, max_tokens)
  return await asyncio.to_thread(chain.invoke, {...})

stream_answer(...) → AsyncIterator[str]:
  async for chunk in chain.astream({...}):
      yield str(chunk.content)
```

### `EmbeddingService` (`services/ingestion/embeddings.py`)
- Lazy-loads `SentenceTransformer` model on first use
- Uses `asyncio.to_thread` so CPU-bound encoding doesn't block the event loop
- Returns `list[list[float]]` (dim=384)

### `RerankerService` (`services/retrieval/reranker.py`)
- Lazy-loads `CrossEncoder` model
- `rerank(query, chunks, top_k)` → runs `asyncio.to_thread`, returns top-K by cross-encoder score

### `StorageService` (`services/ingestion/storage.py`)
- Wraps `Minio` client with `asyncio.to_thread` for all operations
- `ensure_bucket()`: idempotent bucket creation at startup
- Raises `StorageError` (→ HTTP 500) on any failure

## 6. Repository Layer

### `chunk_repo.py`
```python
# Semantic search (pgvector cosine ANN via HNSW)
SELECT id, document_name, page_number, chunk_index, content,
       1 - (embedding <=> $1::vector) AS score
FROM document_chunks
ORDER BY embedding <=> $1::vector
LIMIT $2

# Lexical search (PostgreSQL full-text)
SELECT id, ..., ts_rank_cd(search_vector, plainto_tsquery('english', $1), 32) AS score
FROM document_chunks
WHERE search_vector @@ plainto_tsquery('english', $1)
ORDER BY score DESC
LIMIT $2

# RRF fusion (pure Python, no DB round-trip)
def fuse_rrf(semantic, lexical) -> list[RetrievedChunk]:
    k = settings.rrf_k
    for rank, chunk in enumerate(semantic, 1): fused[chunk.id].score += 1/(k+rank)
    for rank, chunk in enumerate(lexical, 1):  fused[chunk.id].score += 1/(k+rank)
    return sorted(fused.values(), key=lambda x: x.score, reverse=True)
```

### `conversation_repo.py`
- `recent_messages(conn, conversation_id, limit)`: fetches last N messages by `id DESC`, reverses order for chronological history
- `add_message(conn, ..., sources)`: serializes `sources` as JSON string for `JSONB` column
- `touch(conn, conversation_id)`: `UPDATE SET updated_at = NOW()`

### `document_repo.py`
- `get_object_name(conn, document_id)`: single-column fetch for MinIO cleanup
- `delete(conn, document_id)`: checks `DELETE N` rows; raises `NotFoundError` if 0

## 7. Dependency Injection

All singleton services are stored in `app.state` at startup (in `main.py` lifespan) and retrieved by FastAPI `Depends` functions in `dependencies.py`:

```python
# All services read from app.state — one instance per process lifetime
def get_ingestion_service(request: Request) -> IngestionService:
    return request.app.state.ingestion_service

# DB connection: new connection acquired per request, released after response
async def get_db_connection() -> asyncpg.Connection:
    async with get_pool().acquire() as conn:
        yield conn
```

Type aliases for router signatures:
```python
DBConnection = Annotated[asyncpg.Connection, Depends(get_db_connection)]
IngestionDep  = Annotated[IngestionService,  Depends(get_ingestion_service)]
# etc.
```

## 8. Error Handling

### Exception Hierarchy
```
RAGException (base, maps to HTTP error)
  ├── NotFoundError     → 404
  ├── ValidationError   → 400
  ├── LLMServiceError   → 503
  └── StorageError      → 500
```

All `RAGException` subclasses are caught by a global handler in `exceptions.py` and returned as:
```json
{ "error": "NotFoundError", "detail": "Document not found: abc-123" }
```

Unhandled `Exception` → 500 `InternalServerError`.

### HTTP Middleware
`add_request_id_and_logging` in `main.py`:
- Injects `X-Request-ID` UUID header on every response
- Logs method, path, status code, and duration
- Catches middleware-level exceptions (route exceptions are handled before reaching middleware)

### SSE Error Events
If the LLM stream fails:
```
event: error
data: {"error": "LLM service temporarily unavailable"}
```
Unexpected exceptions in the generator also emit an error event and log the traceback.

## 9. SSE Streaming Protocol

### Server-side (backend)
```python
async def event_generator():
    answer_parts = []
    try:
        async for token in llm_service.stream_answer(...):
            answer_parts.append(token)
            yield f"data: {token}\n\n"

        answer = "".join(answer_parts)
        async with conn.transaction():
            await conversation_repo.add_message(conn, conversation_id, "assistant", answer, sources)
            await conversation_repo.touch(conn, conversation_id)

        yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
        yield "data: [DONE]\n\n"
    except LLMServiceError:
        yield 'event: error\ndata: {"error": "LLM service temporarily unavailable"}\n\n'
    except Exception:
        logger.exception(...)
        yield 'event: error\ndata: {"error": "An unexpected error occurred"}\n\n'
```

### Client-side parsing (frontend `api.js`)
Tracks `currentEvent` type from `event:` lines; resets on blank lines:
```javascript
let currentEvent = null;
for (const line of lines) {
    if (line === '')                { currentEvent = null; continue; }
    if (line.startsWith('event: ')) { currentEvent = line.slice(7).trim(); continue; }
    if (line.startsWith('data: ')) {
        const payload = line.slice(6);
        if (payload === '[DONE]')        { onDone(); return; }
        if (currentEvent === 'sources')  { onSources(JSON.parse(payload)); }
        else if (currentEvent === 'error') { onError(...); return; }
        else                             { onToken(payload); }
    }
}
```

This correctly handles LLM tokens that start with `[` (citations, markdown, etc.) without misrouting them to `onSources`.

## 10. Chunking

`chunker.split_text(text, chunk_size, chunk_overlap)`:
- Character-based sliding window (not token-based)
- Step = `chunk_size - chunk_overlap`
- Validation: `chunk_size > 0`, `0 ≤ chunk_overlap < chunk_size`
- Default: size=500, overlap=100 → step=400 chars

Per-page chunking: each PDF page is chunked independently; `chunk_index` is global across the whole document.

## 11. Migration Management

Alembic is configured in `alembic.ini` with an async-capable `env.py`. At app startup, `database.py` runs:

```python
async def _run_migrations():
    connectable = create_async_engine(url, poolclass=NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
```

This applies any pending migrations before the app accepts requests. Safe for multi-instance deployments if migrations are idempotent (all DDL uses `IF NOT EXISTS`).

To create a new migration after schema changes:
```bash
cd backend
alembic revision -m "add_foo_column"
# Edit the generated file, then:
alembic upgrade head
```

## 12. Docker Configuration

- **Backend Dockerfile**: `python:3.11-slim`, installs `pyproject.toml` deps with `pip install -e .`, copies source, runs `uvicorn app.main:app`
- **backend volume mount** (`./backend:/app`): hot-reload in development (uvicorn watches file changes)
- **model_cache volume** (`/root/.cache`): persists HuggingFace/SentenceTransformer model downloads across container restarts
- **Frontend**: standard Vite dev server on port 3000

## 13. Coding Conventions

- Type hints on all function signatures
- Async for all I/O (DB, MinIO, LLM, embedding)
- CPU-bound ML inference wrapped in `asyncio.to_thread`
- No global mutable state except the asyncpg pool (singleton)
- Services lazy-load models on first use, not at import time
- Comments only for non-obvious invariants (not for "what the code does")
- No backwards-compatibility shims — delete unused code
