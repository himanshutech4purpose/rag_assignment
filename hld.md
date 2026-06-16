# High-Level Design (HLD): RAG Document Q&A App

## 1. System Overview

A production-quality RAG (Retrieval-Augmented Generation) application. Users upload PDF documents, ask questions, and receive AI-generated answers with citations pointing back to the exact source document, page, and chunk.

```
┌─────────────────┐   HTTP / SSE   ┌──────────────────────────────────────────────┐
│   React UI      │ ◄────────────► │                FastAPI Backend               │
│  (Tailwind)     │                │                                              │
└─────────────────┘                │  ┌──────────┐  ┌───────────┐  ┌──────────┐  │
                                   │  │Ingestion │  │Retrieval  │  │   LLM    │  │
                                   │  │Service   │  │Service    │  │ Service  │  │
                                   │  └────┬─────┘  └─────┬─────┘  └────┬─────┘  │
                                   └───────┼──────────────┼─────────────┼────────┘
                                           │              │             │
                        ┌──────────────────┼──────┐       │     ┌───────▼─────────┐
                        │   PostgreSQL 16  │      │       │     │  Groq / OpenAI  │
                        │   + pgvector     │      │       │     │    (LangChain)  │
                        │                  ▼      │       │     └─────────────────┘
                        │  documents  document_  │       │
                        │  table      chunks     │◄──────┘
                        │  conversa-  (vector +  │
                        │  tions      tsvector)  │
                        │  messages              │
                        └─────────────────┬──────┘
                                          │
                               ┌──────────▼────────┐
                               │      MinIO        │
                               │  (PDF storage)    │
                               └───────────────────┘
```

## 2. Components

### 2.1 Frontend (React + Tailwind CSS)
- **Upload Page:** Drag-and-drop or file picker for 1–3 PDFs, chunk preview after upload
- **Chat Page:** Multi-turn SSE-streamed Q&A, source citations per message, conversation list sidebar
- **Documents Page:** Table of uploaded documents with delete action
- **Settings Page:** LLM provider/model/API key, system prompt, max tokens, history limit, chunk parameters — all persisted in `localStorage`

### 2.2 Backend (FastAPI)
Singleton services wired at startup via `app.state`:

| Service | Responsibility |
|---|---|
| `IngestionService` | PDF → parse → chunk → embed → store in DB + MinIO |
| `RetrievalService` | Hybrid search (semantic + lexical) → RRF → rerank → top-K chunks |
| `ConversationService` | Title generation, history management, message persistence |
| `LLMService` | Groq / OpenAI via LangChain, supports sync and streaming |
| `EmbeddingService` | SentenceTransformer (`all-MiniLM-L6-v2`), CPU-only, lazy-loaded |
| `RerankerService` | CrossEncoder (`ms-marco-MiniLM-L-6-v2`), lazy-loaded |
| `StorageService` | MinIO bucket management, upload/delete |

### 2.3 Database (PostgreSQL 16 + pgvector)

Four tables managed by Alembic migrations:

| Table | Purpose |
|---|---|
| `documents` | PDF metadata (name, size, MinIO reference, status) |
| `document_chunks` | Text chunks with `vector(384)` embeddings + `tsvector` for full-text search |
| `conversations` | Multi-turn chat sessions |
| `messages` | Individual messages (user + assistant) with optional `JSONB` sources |

Key indexes:
- `HNSW` on `embedding` for fast cosine ANN search
- `GIN` on `search_vector` (generated `tsvector`) for full-text search
- B-tree on `document_id`, `conversation_id` for cascade deletes

### 2.4 Object Storage (MinIO)
Stores original PDF bytes. Object names are `{uuid}_{filename}`. Linked to `documents.minio_object`. Cleaned up atomically with DB delete.

### 2.5 LLM Providers
- **Groq** (default): `llama-3.1-8b-instant`, fast inference
- **OpenAI** (optional): `gpt-4o-mini`, `gpt-4o`
- Provider, model, and API key can be overridden per-request from frontend Settings

## 3. Data Flow

### 3.1 Ingestion Flow
```
User uploads PDF(s)
  │
  POST /api/upload
  │
  ├─ Validate: content-type == application/pdf, size ≤ 10MB, count ≤ 3
  ├─ Upload raw bytes to MinIO
  ├─ DB transaction:
  │    ├─ Insert document record (status = "processing")
  │    ├─ Extract text pages (pypdf, async thread)
  │    ├─ Split into overlapping chunks (character-based)
  │    ├─ Embed all chunks (SentenceTransformer, async thread)
  │    ├─ INSERT chunks with embeddings (asyncpg executemany)
  │    └─ Update document status = "indexed"
  └─ Return DocumentUploadResult (id, name, chunks_inserted, images_ignored)

On any failure: transaction rolls back, MinIO object is deleted
```

### 3.2 Retrieval Pipeline
```
User question
  │
  ├─ Embed question → vector (SentenceTransformer)
  │
  ├─ semantic_search: pgvector cosine ANN, top-SEMANTIC_TOP_K (default 20)
  └─ lexical_search:  ts_rank_cd full-text, top-LEXICAL_TOP_K (default 20)
          │
          └─ RRF fusion (k=RRF_K, default 60) → merged + scored list
                  │
                  └─ CrossEncoder rerank → top-RERANK_TOP_K (default 5) → LLM
```

### 3.3 Q&A Flow (Streaming)
```
POST /api/conversations/{id}/ask/stream
  │
  ├─ Save user message to DB
  ├─ Run retrieval pipeline → top-K chunks
  ├─ Return StreamingResponse (text/event-stream)
  │
  LLM astream → tokens:
      data: token\n\n    (for each token)
      ...
      event: sources
      data: [{...}]\n\n  (after all tokens)
      data: [DONE]\n\n
  │
  └─ Save assistant message + sources to DB (inside generator, after all tokens sent)
```

### 3.4 Conversation Title
Auto-generated from first 6 words of the first question (max 40 chars, truncated with `…`). Stored and displayed in the sidebar.

## 4. Deployment (Docker Compose)

```
┌─────────────────────────────────────┐
│           Docker Compose            │
│                                     │
│  ┌──────────┐   ┌────────────────┐  │
│  │ frontend │   │    backend     │  │
│  │ :3000    │   │    :8000       │  │
│  └──────────┘   └───────┬────────┘  │
│                         │           │
│              ┌──────────┴────────┐  │
│              │                   │  │
│  ┌───────────▼──┐  ┌─────────────▼┐ │
│  │  db          │  │  minio       │ │
│  │  pg16+vector │  │  :9000/:9001 │ │
│  │  :5432       │  └─────────────┘ │
│  └──────────────┘                  │
└─────────────────────────────────────┘
```

- Backend waits for `db` and `minio` healthchecks before starting
- Alembic migrations run automatically in the FastAPI lifespan handler
- `model_cache` Docker volume persists HuggingFace model downloads (~90MB)

## 5. Security Considerations

- API keys injected via environment variables, never hardcoded
- CORS restricted to frontend origin (`CORS_ORIGINS` env var)
- File upload size limited to 10MB per file; type validated before read
- PDF magic-byte validation in `pdf_parser.py`
- No user authentication (single-user scope; noted as limitation)
- `chunk_overlap` must be < `chunk_size` (validated in chunker)

## 6. Scalability Notes (Future)

- Move embedding + chunking to async worker queue (Celery / ARQ) for large files
- Add Redis caching for frequent identical queries
- Replace MinIO with S3 for production object storage
- Use managed Postgres (RDS/Aurora) with pgvector for horizontal scaling
- Implement user authentication and multi-tenancy
- Add OpenTelemetry instrumentation for distributed tracing
