# Project Plan: RAG Document Q&A App

## 1. Goal
Build a RAG-based document question-answering system that accepts 1–3 PDFs, answers natural-language questions with citations, and runs with a single command.

## 2. Tech Stack
- **Backend:** Python + FastAPI
- **Frontend:** React + Tailwind CSS
- **Vector Database:** PostgreSQL + pgvector
- **Object Storage:** MinIO
- **LLM:** Groq API (mixtral-8x7b / llama3-8b) via `langchain-groq`
- **Streaming:** Server-Sent Events (SSE) for token-by-token answers
- **Embeddings:** HuggingFace `sentence-transformers/all-MiniLM-L6-v2`
- **Deployment:** Docker Compose (single-command run)

## 3. Deliverables
| File | Purpose |
|------|---------|
| `plan.md` | This document: scope, phases, milestones |
| `hld.md` | High-level architecture and component design |
| `lld.md` | Low-level design: APIs, DB schema, code modules |
| `user-flow.md` | End-to-end user interaction flow |
| `README.md` | Setup instructions, approach, limitations |
| `backend/` | FastAPI source code |
| `frontend/` | React source code |
| `docker-compose.yml` | One-command orchestration |
| `.env.example` | Required environment variables |

## 4. Scope
### In Scope
- Upload 1–3 PDF documents and store originals in MinIO
- Chunk, embed, and store documents in pgvector
- List all uploaded documents
- Delete documents (removes file from MinIO + chunks from pgvector)
- Ask natural-language questions in multi-turn conversations
- Retrieve relevant chunks with similarity search
- Stream answers using SSE for better UX
- Generate answers using Groq LLM with citations (document name + chunk metadata)
- Simple, clean, elegant web UI
- Docker Compose single-command setup

### Out of Scope (Future Improvements)
- User authentication / multi-tenancy
- Advanced citation highlighting in source PDFs (e.g., PDF viewer with highlights)
- OCR for scanned/image-based PDFs
- Document re-indexing or version replacement
- Production-grade monitoring/logging
- Redis caching for frequent queries

## 5. Phases

### Phase 1: Project Setup (30 min)
- Initialize backend and frontend folders
- Set up `docker-compose.yml` (FastAPI, React dev server, Postgres)
- Create `.env.example` and `.gitignore`
- Verify all services start with `docker compose up`

### Phase 2: Backend Core (2–2.5 hrs)
- Database initialization (`init.sql` with all tables: documents, chunks, conversations, messages)
- MinIO integration for PDF storage (`storage.py`)
- PDF text extraction (`pypdf`)
- Document chunking with overlap
- Embedding generation via HuggingFace sentence-transformers
- pgvector storage and HNSW-indexed similarity search
- Groq LLM integration with citation prompt and SSE streaming
- Conversation CRUD and message history management
- REST API endpoints: upload, list/delete documents, conversations CRUD, ask/stream

### Phase 3: Frontend UI (1.5–2 hrs)
- Page routing (Upload, Documents, Chat)
- Upload component for 1–3 PDFs
- Documents listing page with delete action
- Chat/question interface
- Display answer with clear document-level citations
- Loading, empty, and error states
- Elegant Tailwind styling

### Phase 4: Integration & Testing (1 hr)
- End-to-end test with sample PDFs
- Verify citations appear
- Fix Docker networking / CORS issues
- Document limitations

### Phase 5: Documentation (30 min)
- Finalize `README.md`, `hld.md`, `lld.md`, `user-flow.md`
- Push to public GitHub repo

## 6. Milestones
| # | Milestone | Target Time |
|---|-----------|-------------|
| 1 | Docker Compose starts all services | 30 min |
| 2 | PDF upload stores file in MinIO and chunks in pgvector | 2 hrs |
| 3 | Document list and delete works | 3 hrs |
| 4 | Q&A returns cited answers | 4 hrs |
| 5 | Multi-turn chat + SSE streaming | 5 hrs |
| 6 | UI is functional, elegant, and multi-page | 5.5 hrs |
| 7 | Docs complete and repo ready | 6 hrs |

## 7. Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Groq API rate limits | Use small model (llama3-8b), cache where possible |
| Large PDFs cause slow ingestion | Limit file size, chunk with overlap, async processing |
| pgvector extension setup | Use official `pgvector/pgvector:pg16` Docker image |
| MinIO bucket setup | Auto-create bucket on backend startup |
| CORS issues | Configure FastAPI CORS middleware for localhost:3000 |

## 8. Definition of Done
- `docker compose up` starts backend, frontend, MinIO, and database
- User can upload 1–3 PDFs (stored in MinIO, indexed in pgvector)
- User can view all uploaded documents
- User can delete a document (MinIO + pgvector cleanup)
- User can have multi-turn conversations with context-aware answers
- Answers stream via SSE with document-level citations
- UI is simple, elegant, and easy to navigate
- Code is clean, commented, and committed to GitHub
- README explains setup, approach, and limitations
