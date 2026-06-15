# High-Level Design (HLD): RAG Document Q&A App

## 1. System Overview
A web-based RAG (Retrieval-Augmented Generation) application that lets users upload PDF documents, ask questions about them, and receive AI-generated answers with citations pointing back to the source documents and sections.

```
┌─────────────────┐      HTTP/JSON      ┌──────────────────┐
│   React UI      │ ◄──────────────────► │   FastAPI        │
│  (Tailwind)     │                      │   Backend        │
└─────────────────┘                      └────────┬─────────┘
                                                  │
                                       ┌──────────┼──────────┐
                                       │          │          │
                              ┌────────▼────────┐ │ ┌────────▼────────┐
                              │   PostgreSQL    │ │ │   Groq LLM      │
                              │   + pgvector    │ │ │   (langchain)   │
                              └─────────────────┘ │ └─────────────────┘
                                                  │
                                       ┌──────────▼────────┐
                                       │      MinIO        │
                                       │  (PDF storage)    │
                                       └───────────────────┘
```

## 2. Components

### 2.1 Frontend (React + Tailwind CSS)
- **Purpose:** Simple, elegant UI for managing documents and having multi-turn conversations.
- **Key Pages:**
  - **Upload Page:** Drag-and-drop or file picker for 1–3 PDFs
  - **Documents Page:** List all uploaded documents with delete action
  - **Chat Page:** Multi-turn chat, view answers, and see document-level citations
- **Design:** Clean Tailwind layout, minimal navigation, card-based document list, chat-style messaging, clear typography
- **State Management:** React `useState` / `useEffect`
- **Communication:** REST API + SSE for streaming answers

### 2.2 Backend (FastAPI)
- **Purpose:** Orchestrate file storage, ingestion, retrieval, answer generation, document lifecycle, and conversation history.
- **Modules:**
  - `documents`: PDF parsing, chunking, and document CRUD
  - `storage`: MinIO client for PDF file persistence
  - `embeddings`: HuggingFace sentence-transformer embeddings
  - `vectordb`: pgvector storage and similarity search
  - `conversations`: Multi-turn chat session and message history
  - `llm`: Groq API integration with citation-aware prompts + streaming
  - `api`: FastAPI route definitions

### 2.3 Vector Database (PostgreSQL + pgvector)
- **Purpose:** Store document chunks as vector embeddings.
- **Features Used:**
  - `vector` extension
  - Cosine similarity search (`<=>` operator)
  - Metadata storage: document name, page number, chunk index

### 2.4 LLM (Groq)
- **Purpose:** Generate natural-language answers grounded in retrieved chunks.
- **Model Options:** `llama3-8b-8192` or `mixtral-8x7b-32768`
- **Access:** `langchain-groq` with `GROQ_API_KEY`

### 2.5 Object Storage (MinIO)
- **Purpose:** Store original PDF files and serve them on demand.
- **Bucket:** `documents`
- **Operations:** upload, download, delete, list
- **Metadata Link:** Files are linked to database records via `document_id` / `document_name`

## 3. Data Flow

### 3.1 Ingestion Flow
1. User selects 1–3 PDFs on the **Upload** page and clicks **Upload**.
2. Frontend sends files to `POST /api/upload`.
3. Backend uploads original PDFs to MinIO `documents` bucket.
4. Backend extracts text from each PDF.
5. Text is split into overlapping chunks.
6. Each chunk is embedded using `sentence-transformers/all-MiniLM-L6-v2`.
7. Chunks + embeddings + metadata are stored in pgvector with `document_id` reference.
8. Backend returns success response with document names and IDs.

### 3.2 Question-Answering Flow
1. User types a question in an active conversation and clicks **Ask**.
2. Frontend sends question to `POST /api/conversations/{id}/ask/stream` (SSE).
3. Backend loads recent message history for that conversation.
4. Backend embeds the current question using the same embedding model.
5. pgvector performs similarity search to retrieve top-K chunks.
6. Retrieved chunks + conversation history are passed to the Groq LLM.
7. LLM streams an answer citing document names and chunk references.
8. Backend stores the user message and assistant answer in Postgres.
9. Frontend renders streamed tokens and final citations.

### 3.3 Conversation Flow
1. A new conversation is auto-created when the user asks the first question.
2. Each subsequent question in the same thread includes prior context.
3. User can start a **New Chat** at any time.
4. User can view and select previous conversations from a sidebar.

### 3.4 Data Model Summary

The PostgreSQL database contains four tables:

| Table | Purpose |
|-------|---------|
| `documents` | Uploaded PDF metadata (name, size, status, MinIO reference) |
| `document_chunks` | Text chunks with vector embeddings for similarity search |
| `conversations` | Multi-turn chat sessions |
| `messages` | Individual messages (user + assistant) within conversations |

Key relationships: `document_chunks` cascade-deletes with `documents`; `messages` cascade-deletes with `conversations`.

## 4. Deployment Architecture
- **Docker Compose** orchestrates four services:
  - `db`: `pgvector/pgvector:pg16` with healthcheck (`pg_isready`)
  - `minio`: MinIO object storage on port `9000` (API) and `9001` (console) with healthcheck
  - `backend`: FastAPI app on port `8000`, starts after db and minio are healthy
  - `frontend`: React dev server on port `3000`
- **Service Readiness:** Postgres and MinIO define Docker healthchecks. The backend uses `depends_on: condition: service_healthy` to wait for both before starting. The FastAPI `lifespan` handler runs `init.sql` and creates the MinIO bucket on startup.
- **Networking:** All services share a Docker bridge network.
- **Volumes:** Postgres data, MinIO data, and HuggingFace model cache persisted via Docker volumes.
- **Embedding Model Caching:** The `sentence-transformers/all-MiniLM-L6-v2` model (~90MB) is downloaded on first backend startup. A `model_cache` Docker volume persists `~/.cache` across container restarts to avoid re-downloading.
- **Environment:** API keys and DB/MinIO credentials via `.env` file.

## 5. Security Considerations
- API keys are injected via environment variables, never hardcoded.
- CORS restricted to the frontend origin in development.
- File upload size limited to ~10 MB per PDF.
- No user authentication for this scope (noted as limitation).

## 6. Scalability Notes (Future)
- Move embedding generation to an async worker (Celery/RQ) for large files.
- Add Redis for caching frequent queries.
- Use a managed Postgres/pgvector service in production.
- Implement user sessions and multi-tenancy.
