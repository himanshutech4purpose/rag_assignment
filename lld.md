# Low-Level Design (LLD): RAG Document Q&A App

## 1. Project Structure
```
.
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entrypoint + lifespan
│   │   ├── config.py            # Pydantic settings / env vars
│   │   ├── database.py          # asyncpg pool setup
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── documents.py     # /api/upload, /api/documents
│   │   │   └── conversations.py # /api/conversations/*
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── pdf_parser.py    # Extract text from PDF
│   │   │   ├── chunker.py       # Split text into chunks
│   │   │   ├── embeddings.py    # HuggingFace embedding model
│   │   │   ├── vector_store.py  # pgvector CRUD + search
│   │   │   ├── storage.py       # MinIO client for PDF files
│   │   │   └── llm.py           # Groq LLM client + prompt + streaming
│   │   └── models/
│   │       ├── __init__.py
│   │       └── schemas.py       # Pydantic request/response models
│   ├── init.sql                 # DB schema initialization
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── UploadPage.jsx
│   │   │   ├── DocumentsPage.jsx
│   │   │   └── ChatPage.jsx
│   │   ├── components/
│   │   │   ├── Upload.jsx
│   │   │   ├── Chat.jsx
│   │   │   ├── Citation.jsx
│   │   │   ├── Documents.jsx
│   │   │   ├── Sidebar.jsx      # Conversation list + New Chat
│   │   │   └── Navbar.jsx
│   │   ├── api.js               # Axios + SSE fetch wrapper
│   │   └── index.css
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── plan.md
├── hld.md
├── lld.md
└── user-flow.md
```

## 2. Environment Variables
```bash
# .env.example
GROQ_API_KEY=your_groq_api_key_here
LLM_MODEL=llama3-8b-8192

DATABASE_URL=postgresql://postgres:postgres@db:5432/ragdb

MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=documents
MINIO_USE_SSL=false

EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHUNK_SIZE=500
CHUNK_OVERLAP=100
TOP_K=5
```

## 3. Database Schema

### 3.1 Extensions
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3.2 Table: `documents`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `UUID PRIMARY KEY DEFAULT gen_random_uuid()` | Unique document ID |
| `name` | `VARCHAR(255)` | Original PDF filename |
| `size_bytes` | `INTEGER` | File size |
| `minio_object` | `VARCHAR(255)` | Object name in MinIO bucket |
| `status` | `VARCHAR(50)` | `uploaded` / `processing` / `indexed` / `error` |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | Upload time |

### 3.3 Table: `document_chunks`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PRIMARY KEY` | Unique chunk ID |
| `document_id` | `UUID REFERENCES documents(id) ON DELETE CASCADE` | Parent document |
| `document_name` | `VARCHAR(255)` | Denormalized filename for citations |
| `page_number` | `INTEGER` | Page number in PDF (if available) |
| `chunk_index` | `INTEGER` | Chunk sequence in document |
| `content` | `TEXT` | Raw text chunk |
| `embedding` | `vector(384)` | Embedding from all-MiniLM-L6-v2 |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | Ingestion time |

### 3.4 Indexes
```sql
-- HNSW is preferred over IVFFlat: works with any row count, no training step required
CREATE INDEX idx_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
```

### 3.5 Database Initialization (`backend/init.sql`)

The schema is created automatically on backend startup via the `lifespan` handler (see 5.2 `database.py`). The `init.sql` file uses `IF NOT EXISTS` / `IF NOT EXISTS` guards so it is safe to run on every startup.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    size_bytes INTEGER NOT NULL,
    minio_object VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'uploaded',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id SERIAL PRIMARY KEY,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    document_name VARCHAR(255) NOT NULL,
    page_number INTEGER,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    sources JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id
    ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
    ON messages(conversation_id);
```

## 4. API Specification

### 4.1 Health Check
```
GET /api/health
Response: { "status": "ok" }
```

### 4.2 Upload Documents
```
POST /api/upload
Content-Type: multipart/form-data
Body: files[] (max 3 PDFs)

Response 200:
{
  "documents": [
    {
      "id": "uuid-1",
      "name": "report.pdf",
      "status": "indexed",
      "chunks_inserted": 28
    },
    {
      "id": "uuid-2",
      "name": "summary.pdf",
      "status": "indexed",
      "chunks_inserted": 14
    }
  ]
}
```

### 4.3 List Documents
```
GET /api/documents

Response 200:
{
  "documents": [
    {
      "id": "uuid-1",
      "name": "report.pdf",
      "size_bytes": 102400,
      "status": "indexed",
      "created_at": "2026-06-14T10:00:00Z"
    }
  ]
}
```

### 4.4 Delete Document
```
DELETE /api/documents/{document_id}

Response 200:
{
  "message": "Document deleted successfully"
}
```

### 4.5 Create Conversation
```
POST /api/conversations
Content-Type: application/json
Body (optional):
{
  "title": "Revenue questions"
}

Response 201:
{
  "id": "conv-uuid-1",
  "title": "Revenue questions",
  "created_at": "2026-06-14T10:00:00Z",
  "updated_at": "2026-06-14T10:00:00Z"
}
```

### 4.6 List Conversations
```
GET /api/conversations

Response 200:
{
  "conversations": [
    {
      "id": "conv-uuid-1",
      "title": "Revenue questions",
      "created_at": "2026-06-14T10:00:00Z",
      "updated_at": "2026-06-14T10:30:00Z"
    }
  ]
}
```

### 4.7 Get Conversation with Messages
```
GET /api/conversations/{conversation_id}

Response 200:
{
  "id": "conv-uuid-1",
  "title": "Revenue questions",
  "created_at": "2026-06-14T10:00:00Z",
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "What was the revenue in 2023?",
      "sources": null,
      "created_at": "2026-06-14T10:05:00Z"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "The revenue in 2023 was $12.4 million...",
      "sources": [
        {
          "document_name": "annual_report.pdf",
          "page_number": 3,
          "chunk_index": 2,
          "content": "...",
          "score": 0.94
        }
      ],
      "created_at": "2026-06-14T10:05:02Z"
    }
  ]
}

Response 404:
{
  "error": "Conversation not found"
}
```

### 4.8 Delete Conversation
```
DELETE /api/conversations/{conversation_id}

Response 200:
{
  "message": "Conversation deleted successfully"
}

Response 404:
{
  "error": "Conversation not found"
}
```

### 4.9 Ask Question (within Conversation)
```
POST /api/conversations/{conversation_id}/ask
Content-Type: application/json
Body:
{
  "question": "What is the main conclusion?"
}

Response 200:
{
  "answer": "The main conclusion is... [report.pdf, chunk 3]",
  "sources": [
    {
      "document_name": "report.pdf",
      "page_number": 2,
      "chunk_index": 3,
      "content": "...",
      "score": 0.92
    }
  ]
}

Response 400:
{
  "error": "Question cannot be empty"
}

Response 404:
{
  "error": "Conversation not found"
}
```

### 4.10 Ask Question with SSE Streaming
```
POST /api/conversations/{conversation_id}/ask/stream
Content-Type: application/json
Body:
{
  "question": "What is the main conclusion?"
}

Response: text/event-stream

Stream events:
  data: The           # token
  data: main          # token
  data: conclusion    # token
  ...
  event: sources
  data: [{"document_name": "report.pdf", "page_number": 2, ...}]
  data: [DONE]

Error event (if LLM fails mid-stream):
  event: error
  data: {"error": "LLM service unavailable"}
```

## 5. Backend Modules

### 5.1 `config.py`
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    groq_api_key: str
    database_url: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_name: str = "documents"
    minio_use_ssl: bool = False
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "llama3-8b-8192"
    chunk_size: int = 500
    chunk_overlap: int = 100
    top_k: int = 5

settings = Settings()
```

### 5.2 `database.py`

> **Why asyncpg?** FastAPI is async-native. Using synchronous `psycopg2` would block
> the event loop during DB calls, breaking SSE streaming. `asyncpg` provides true
> async Postgres access that works naturally with `async def` endpoints.

```python
import asyncpg
from app.config import settings

pool: asyncpg.Pool | None = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(settings.database_url)
    async with pool.acquire() as conn:
        with open("init.sql") as f:
            await conn.execute(f.read())

async def close_db():
    global pool
    if pool:
        await pool.close()

def get_pool() -> asyncpg.Pool:
    return pool
```

### 5.3 `storage.py`
```python
from minio import Minio
from app.config import settings

client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_use_ssl
)

def ensure_bucket():
    if not client.bucket_exists(settings.minio_bucket_name):
        client.make_bucket(settings.minio_bucket_name)

def upload_file(object_name: str, data: bytes, length: int):
    from io import BytesIO
    client.put_object(settings.minio_bucket_name, object_name, BytesIO(data), length)

def delete_file(object_name: str):
    client.remove_object(settings.minio_bucket_name, object_name)
```

### 5.4 `pdf_parser.py`
```python
import io
from pypdf import PdfReader

def extract_text(file_bytes: bytes) -> list[dict]:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        pages.append({"page_number": i, "text": text})
    return pages
```

### 5.5 `chunker.py`
```python
def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks
```

### 5.6 `embeddings.py`
```python
from sentence_transformers import SentenceTransformer

_model = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model

def embed(texts: list[str]) -> list[list[float]]:
    return get_model().encode(texts).tolist()
```

### 5.7 `vector_store.py`
```python
import asyncpg

async def insert_chunks(pool: asyncpg.Pool, chunks: list[dict]):
    sql = """
        INSERT INTO document_chunks
            (document_id, document_name, page_number, chunk_index, content, embedding)
        VALUES ($1, $2, $3, $4, $5, $6)
    """
    async with pool.acquire() as conn:
        await conn.executemany(sql, [
            (c["document_id"], c["document_name"], c["page_number"],
             c["chunk_index"], c["content"], c["embedding"])
            for c in chunks
        ])

async def search_chunks(pool: asyncpg.Pool, query_embedding: list[float], top_k: int):
    sql = """
        SELECT document_name, page_number, chunk_index, content,
               1 - (embedding <=> $1::vector) AS score
        FROM document_chunks
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """
    async with pool.acquire() as conn:
        return await conn.fetch(sql, query_embedding, top_k)
```

### 5.8 `llm.py`
```python
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate

prompt = PromptTemplate.from_template("""
You are a helpful assistant. Use ONLY the following context to answer the question.
Cite the source document name and chunk index for each fact you use.

Context:
{context}

Question: {question}

Answer:
""")

llm = ChatGroq(
    api_key=settings.groq_api_key,
    model_name=settings.llm_model,
    temperature=0.1
)

def answer_question(question: str, chunks: list[dict]) -> str:
    context = "\n\n".join(
        f"[{c['document_name']} - chunk {c['chunk_index']}]\n{c['content']}" for c in chunks
    )
    chain = prompt | llm
    return chain.invoke({"context": context, "question": question}).content
```

### 5.9 `main.py`
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db, close_db
from app.routers import documents, conversations
from app.services.storage import ensure_bucket

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    ensure_bucket()
    yield
    await close_db()

app = FastAPI(title="RAG Document Q&A", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
```

## 6. Frontend Modules

### 6.1 Page Structure
| Route | Page | Purpose |
|-------|------|---------|
| `/` | Upload Page | Upload 1–3 PDF documents |
| `/documents` | Documents Page | View all uploaded documents and delete any |
| `/chat` | Chat Page | Ask questions and view cited answers |

### 6.2 `api.js`
```javascript
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';
const api = axios.create({ baseURL: API_BASE });

export const uploadFiles = (files) => {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  return api.post('/upload', formData);
};

export const listDocuments = () => api.get('/documents');
export const deleteDocument = (id) => api.delete(`/documents/${id}`);

export const createConversation = (title) => api.post('/conversations', { title });
export const listConversations = () => api.get('/conversations');
export const getConversation = (id) => api.get(`/conversations/${id}`);
export const deleteConversation = (id) => api.delete(`/conversations/${id}`);

export async function streamQuestion(conversationId, question, { onToken, onSources, onDone, onError }) {
  const response = await fetch(`${API_BASE}/conversations/${conversationId}/ask/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  if (!response.ok) {
    onError(new Error(`HTTP ${response.status}`));
    return;
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (line.startsWith('data: [DONE]')) { onDone(); return; }
      if (line.startsWith('event: sources')) continue;
      if (line.startsWith('data: ')) {
        const payload = line.slice(6);
        if (payload.startsWith('[')) onSources(JSON.parse(payload));
        else onToken(payload);
      }
    }
  }
}
```

### 6.3 `Upload.jsx`
- File input accepting `.pdf`
- Limit to 3 files
- Show upload progress / success / error
- Call `uploadFiles`

### 6.4 `Chat.jsx`
- Input field for question
- Display loading spinner while waiting
- Render answer and list of sources
- Source item shows: document name, page, chunk index, relevance score

### 6.5 `Citation.jsx`
- Small card component for each source
- Displays truncated content with metadata

### 6.6 `Documents.jsx`
- Table or card grid listing uploaded documents
- Columns: name, size, status, upload date
- **Delete** button per row with confirmation dialog
- Navigation link to `/chat`

### 6.7 `Sidebar.jsx`
- List of past conversations (title, last updated)
- **New Chat** button to create a fresh conversation
- Click to navigate to `/chat/{conversation_id}`
- **Delete** button per conversation with confirmation
- Active conversation highlighted

## 7. Docker Compose
```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ragdb
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - miniodata:/data
    ports:
      - "9000:9000"
      - "9001:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ./backend:/app
      - model_cache:/root/.cache

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  pgdata:
  miniodata:
  model_cache:
```

## 8. Error Handling

### 8.1 Standard Error Response
All error responses use a consistent shape:

```python
class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
```

Example: `{"error": "Document not found", "detail": "No document with id abc-123"}`

### 8.2 Error Scenarios

| Scenario | Status | `error` field |
|----------|--------|---------------|
| More than 3 files | `400` | `"Maximum 3 PDF files allowed"` |
| Non-PDF file | `400` | `"Only PDF files are supported"` |
| Empty question | `400` | `"Question cannot be empty"` |
| File too large (>10MB) | `400` | `"File exceeds 10MB limit"` |
| Document not found | `404` | `"Document not found"` |
| Conversation not found | `404` | `"Conversation not found"` |
| No documents indexed | `400` | `"Upload documents before asking questions"` |
| LLM API failure | `503` | `"LLM service temporarily unavailable"` |
| DB connection failure | `500` | `"Internal server error"` |
| MinIO failure | `500` | `"Internal server error"` |

### 8.3 SSE Error Events
If an error occurs mid-stream during SSE, emit an error event before closing:
```
event: error
data: {"error": "LLM service temporarily unavailable"}
```

## 9. Coding Style

### 9.1 No Defensive Coding
This project intentionally avoids over-defensive patterns. Keep the code lean:

- **Do NOT** wrap every function in `try/except`. Let exceptions propagate naturally.
- **Do NOT** add redundant null checks for values that are guaranteed by the schema or DB constraints.
- **Do NOT** add `if x is not None` guards when `x` is a required field.
- **Do NOT** add comments explaining obvious code. Only comment non-obvious *why*, never *what*.
- **DO** use FastAPI's built-in exception handlers -- they automatically return proper HTTP error responses for `HTTPException`, validation errors, and unhandled exceptions.
- **DO** use Pydantic models for validation -- they reject bad input before your code runs.
- **DO** catch errors only where you can meaningfully recover or need to provide a user-friendly message (e.g., catching Groq API errors to return a 503).
- **DO** use `HTTPException` from FastAPI to return error responses with proper status codes.

### 9.2 General Style
- Type hints on all function signatures.
- Async functions for all I/O (DB, MinIO, LLM API).
- Small, focused functions -- each does one thing.
- No global mutable state except the DB pool and embedding model singleton.
- Configuration via Pydantic `BaseSettings` (validated at startup, fails fast on missing env vars).

## 10. Real-Time Communication: WebSocket vs SSE

### 10.1 Decision Matrix
| Factor | SSE | WebSocket |
|--------|-----|-----------|
| Direction | Server → Client only | Bidirectional |
| Use case | Streaming LLM tokens to UI | Full-duplex chat + streaming |
| Complexity | Low (HTTP-based) | Medium (persistent connection) |
| Reconnect | Built-in browser support | Must implement manually |
| Scalability | Easier with load balancers | Harder with load balancers |
| Multi-turn | Still needs REST for sending | Native bidirectional support |

### 10.2 Recommended Approach
**Use SSE for this scope.**
- The primary real-time need is streaming the LLM answer token-by-token.
- Questions are sent via `POST /api/ask` (REST).
- Server responds with `text/event-stream` and streams tokens as they are generated.
- UI renders tokens incrementally in the chat window.

**WebSocket is overkill here** because:
- We don't need continuous bidirectional state (e.g., live collaboration).
- SSE is simpler to implement, debug, and scale.
- If multi-tenancy or real-time typing indicators are added later, WebSocket becomes justified.

### 10.3 SSE Implementation
```python
from fastapi.responses import StreamingResponse

@router.post("/conversations/{conversation_id}/ask/stream")
async def ask_stream(conversation_id: str, request: AskRequest):
    async def event_generator():
        history = get_conversation_history(conversation_id, limit=5)
        chunks = retrieve_chunks(request.question)
        async for token in llm.astream_answer(request.question, chunks, history):
            yield f"data: {token}\n\n"
        sources = json.dumps(format_sources(chunks))
        yield f"event: sources\ndata: {sources}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

### 10.4 Frontend SSE Consumption

> **Note:** `EventSource` only supports GET requests. Since the ask endpoint uses POST
> (to send JSON body), we use `fetch()` with `ReadableStream` instead.

```javascript
async function streamAnswer(conversationId, question, onToken, onSources, onDone, onError) {
  const response = await fetch(`/api/conversations/${conversationId}/ask/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    onError(new Error(`HTTP ${response.status}`));
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();

    for (const line of lines) {
      if (line.startsWith('data: [DONE]')) {
        onDone();
        return;
      } else if (line.startsWith('event: sources')) {
        continue;
      } else if (line.startsWith('data: ')) {
        const payload = line.slice(6);
        if (payload.startsWith('{') || payload.startsWith('[')) {
          onSources(JSON.parse(payload));
        } else {
          onToken(payload);
        }
      }
    }
  }
}
```

## 11. Multi-Turn Conversation Handling

### 11.1 Data Model

#### Table: `conversations`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `UUID PRIMARY KEY DEFAULT gen_random_uuid()` | Conversation ID |
| `title` | `VARCHAR(255)` | Auto-generated title (first question summary) |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | Start time |
| `updated_at` | `TIMESTAMP DEFAULT NOW()` | Last message time |

#### Table: `messages`
| Column | Type | Description |
|--------|------|-------------|
| `id` | `SERIAL PRIMARY KEY` | Message ID |
| `conversation_id` | `UUID REFERENCES conversations(id) ON DELETE CASCADE` | Parent conversation |
| `role` | `VARCHAR(20)` | `user` or `assistant` |
| `content` | `TEXT` | Message text |
| `sources` | `JSONB` | Citation metadata (assistant only) |
| `created_at` | `TIMESTAMP DEFAULT NOW()` | Message time |

### 11.2 API Endpoints for Conversations

See sections 4.5–4.10 for full request/response schemas.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/conversations` | Create new conversation |
| `GET` | `/api/conversations` | List all conversations |
| `GET` | `/api/conversations/{id}` | Get conversation with all messages |
| `DELETE` | `/api/conversations/{id}` | Delete conversation and its messages |
| `POST` | `/api/conversations/{id}/ask` | Ask question (non-streaming) |
| `POST` | `/api/conversations/{id}/ask/stream` | Ask question with SSE streaming |

### 11.3 Context Window Strategy
1. Store every user question and assistant answer in `messages`.
2. On each new question, fetch last **N** message pairs (default 5) from the same conversation.
3. Build prompt:
   ```
   System: You are a helpful assistant. Use only the provided document context.
   
   Previous conversation:
   User: <previous question>
   Assistant: <previous answer>
   ...
   
   Context from documents:
   <retrieved chunks>
   
   User: <current question>
   Assistant:
   ```
4. Trim history if total tokens exceed safe limit (e.g., 70% of model context window).
5. Retrieved chunks always take priority in the prompt; history is summarized or truncated if needed.

### 11.4 UX Flow for Multi-Turn
1. User lands on **Chat Page**.
2. If no active conversation, auto-create one on first question.
3. Each question/answer pair appears as a chat bubble.
4. Sidebar shows conversation history list.
5. User can click **New Chat** to start a fresh conversation.
6. Citations are shown per assistant message.

## 12. UI/UX Notes
- Keep the interface minimal: light background, subtle shadows, rounded cards
- Use a soft primary color (indigo/slate) and clear hover states
- Citations should visually group by document (color badge or icon)
- Empty states with friendly illustrations/messages
- Toast notifications for upload success / deletion confirmation
- Chat interface should feel like a clean, modern messaging app

## 13. Assumptions
- PDFs contain selectable text (no scanned images/OCR).
- Single-user / single-session app for this scope.
- Groq API key is available and has sufficient quota.
- MinIO is available via Docker Compose.
- Development runs on `localhost`.
