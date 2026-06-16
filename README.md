# DocuAsk — RAG Document Q&A

A production-quality RAG (Retrieval-Augmented Generation) application. Upload PDF documents, ask questions, and get AI-generated answers with citations that trace back to the exact source document, page, and chunk.

## Features

- Upload 1–3 PDF documents per request (stored in MinIO object storage)
- Hybrid search: semantic (pgvector cosine) + lexical (PostgreSQL full-text) fused with Reciprocal Rank Fusion (RRF)
- Cross-encoder reranking for final result quality
- Multi-turn conversations with configurable history context
- Streamed answers via Server-Sent Events (SSE)
- Document-level citations (document name, page, chunk index, relevance score)
- Configurable LLM provider (Groq or OpenAI), model, system prompt, max tokens
- Schema migrations via Alembic (run automatically on startup)
- React + Tailwind CSS UI

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.11, FastAPI, Uvicorn |
| Dependency management | `pyproject.toml` (setuptools) |
| Database | PostgreSQL 16 + pgvector |
| Migrations | Alembic + SQLAlchemy (asyncio) |
| Object storage | MinIO |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM | Groq (`langchain-groq`) or OpenAI (`langchain-openai`) |
| Frontend | React 18, Tailwind CSS, Vite |
| Deployment | Docker Compose |

## Prerequisites

- Docker + Docker Compose
- A Groq API key — [get one here](https://console.groq.com/keys)

## Quick Start

```bash
# 1. Copy env file and set your API key
cp .env.example .env
# Edit .env and set GROQ_API_KEY=<your key>

# 2. Start all services (DB, MinIO, backend, frontend)
docker compose up --build

# 3. Open the app
open http://localhost:3000
```

On first boot the backend automatically runs Alembic migrations (creates tables, indexes, and extensions).

## Service URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 |
| PostgreSQL | localhost:5432 |

## API Reference

### Health
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |

### Documents
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload 1–3 PDFs (multipart). Query params: `chunk_size`, `chunk_overlap` |
| `GET` | `/api/documents` | List all documents |
| `DELETE` | `/api/documents/{id}` | Delete document and its chunks |
| `GET` | `/api/documents/{id}/chunks` | List chunks for a document |

### Conversations
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/conversations` | Create a conversation |
| `GET` | `/api/conversations` | List conversations (newest first) |
| `GET` | `/api/conversations/{id}` | Get conversation with full message history |
| `DELETE` | `/api/conversations/{id}` | Delete conversation and messages |
| `POST` | `/api/conversations/{id}/ask` | Ask a question (non-streaming) |
| `POST` | `/api/conversations/{id}/ask/stream` | Ask a question (SSE streaming) |

## Project Structure

```
.
├── backend/
│   ├── alembic/                  # Migration scripts
│   │   └── versions/             # One file per migration revision
│   ├── app/
│   │   ├── models/
│   │   │   ├── domain.py         # Internal dataclasses (Chunk, Message, …)
│   │   │   └── schemas.py        # Pydantic request/response models
│   │   ├── repositories/         # SQL data-access (document, chunk, conversation)
│   │   ├── routers/              # FastAPI route handlers
│   │   ├── services/             # Business logic
│   │   │   ├── ingestion.py      # Upload → parse → chunk → embed → store pipeline
│   │   │   ├── retrieval.py      # Hybrid search + RRF + reranking
│   │   │   ├── conversation_service.py
│   │   │   ├── embeddings.py     # SentenceTransformer wrapper
│   │   │   ├── reranker.py       # CrossEncoder wrapper
│   │   │   ├── llm.py            # Groq / OpenAI via LangChain
│   │   │   ├── storage.py        # MinIO wrapper
│   │   │   ├── chunker.py        # Character-based text splitter
│   │   │   └── pdf_parser.py     # pypdf text extractor
│   │   ├── config.py             # Pydantic Settings (env vars)
│   │   ├── database.py           # asyncpg pool + Alembic runner
│   │   ├── dependencies.py       # FastAPI dependency providers
│   │   ├── exceptions.py         # Domain exceptions + global handlers
│   │   ├── logging_config.py     # Structured logging setup
│   │   └── main.py               # App factory + lifespan
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── api.js                # Axios + SSE fetch helpers
│       ├── components/
│       │   ├── Chat.jsx          # Streaming chat UI
│       │   ├── Upload.jsx        # PDF upload + chunk preview
│       │   └── Citation.jsx      # Source citation card
│       └── pages/
│           └── SettingsPage.jsx  # LLM / chunking settings
├── docker-compose.yml
├── .env.example
└── README.md
```

## Settings (browser localStorage)

The Settings page stores preferences in `localStorage`. They apply to the next request — no page reload required.

| Setting | Default | Description |
|---|---|---|
| LLM Provider | `groq` | `groq` or `openai` |
| Model | `llama-3.1-8b-instant` | Provider-specific model name |
| API Key | *(empty)* | Falls back to backend env var when blank |
| System Prompt | RAG template | Must contain `{context}`, `{history}`, `{question}` |
| Max Tokens | `4096` | Maximum tokens per LLM response |
| Chat History Context | `10` | Recent messages sent as conversation history |
| Chunk Size | `1000` chars | Applied on next upload; existing chunks unaffected |
| Chunk Overlap | `200` chars | Applied on next upload; must be < Chunk Size |

## Retrieval Pipeline

```
User question
  │
  ├─ Embed → semantic_search (pgvector cosine, top-20)
  └─ lexical_search (PostgreSQL ts_rank_cd, top-20)
          │
          └─ RRF fusion (k=60)
                  │
                  └─ CrossEncoder rerank → top-5 → LLM
```

Configuration knobs (via `.env`): `SEMANTIC_TOP_K`, `LEXICAL_TOP_K`, `RERANK_TOP_K`, `RRF_K`, `TOP_K`.

## Database Migrations

Migrations run automatically at startup. To create a new migration after schema changes:

```bash
cd backend
alembic revision -m "describe your change"
# Edit the generated file in alembic/versions/, then:
alembic upgrade head
```

To run or roll back manually:

```bash
alembic upgrade head      # apply all pending migrations
alembic downgrade -1      # roll back one revision
```

## Environment Variables

See [.env.example](.env.example) for the full list. The minimum required variable is `GROQ_API_KEY`.

## Known Limitations

- No user authentication — single shared document corpus
- Image-only PDFs (scanned documents without text layer) return zero chunks; OCR is not supported
- Uploading the same filename again creates a second document entry (no deduplication)
- `chunk_overlap` must be strictly less than `chunk_size`

## License

MIT
