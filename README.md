# DocuAsk — RAG Document Q&A App

A web-based RAG (Retrieval-Augmented Generation) application that lets users upload PDF documents, ask questions about them, and receive AI-generated answers with citations pointing back to the source documents and sections.

## Features

- Upload 1–3 PDF documents (stored in MinIO)
- Chunk, embed, and index documents in PostgreSQL + pgvector
- List and delete uploaded documents
- Multi-turn conversations with context-aware answers
- Streamed answers via Server-Sent Events (SSE)
- Document-level citations (document name, page number, chunk index, relevance score)
- Clean React + Tailwind CSS UI

## Tech Stack

- **Backend:** Python + FastAPI
- **Frontend:** React + Tailwind CSS
- **Vector Database:** PostgreSQL + pgvector
- **Object Storage:** MinIO
- **LLM:** Groq API (`langchain-groq`)
- **Embeddings:** HuggingFace `sentence-transformers/all-MiniLM-L6-v2`
- **Deployment:** Docker Compose

## Prerequisites

- Docker + Docker Compose
- A Groq API key ([get one here](https://console.groq.com/keys))

## Setup

1. Copy the example environment file and add your Groq API key:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set `GROQ_API_KEY=your_groq_api_key_here`.

2. Start all services:

   ```bash
   docker compose up --build
   ```

3. Open the app at [http://localhost:3000](http://localhost:3000).

4. Upload PDFs, then navigate to **Chat** to ask questions.

## Services

| Service    | URL                     |
|------------|-------------------------|
| Frontend   | http://localhost:3000   |
| Backend    | http://localhost:8000   |
| MinIO API  | http://localhost:9000   |
| MinIO Console | http://localhost:9001 |
| Postgres   | localhost:5432          |

## API Endpoints

- `GET /api/health` — health check
- `POST /api/upload` — upload PDFs
- `GET /api/documents` — list documents
- `DELETE /api/documents/{id}` — delete a document
- `POST /api/conversations` — create conversation
- `GET /api/conversations` — list conversations
- `GET /api/conversations/{id}` — get conversation with messages
- `DELETE /api/conversations/{id}` — delete conversation
- `POST /api/conversations/{id}/ask` — ask question (non-streaming)
- `POST /api/conversations/{id}/ask/stream` — ask question with SSE streaming

## Project Structure

```
.
├── backend/          # FastAPI application
├── frontend/         # React application
├── docker-compose.yml
├── .env.example
└── README.md
```

## Limitations

- No user authentication / single-session app
- No OCR for scanned/image-based PDFs
- Document re-upload does not replace existing documents
- Requires an active Groq API key

## License

MIT
# rag_assignment
