# User Flow: RAG Document Q&A App

## 1. Entry Point
1. User runs `docker compose up` in the project root.
2. Services start: Postgres, MinIO, FastAPI backend, React frontend.
3. User opens browser to `http://localhost:3000`.

## 2. Pages

| # | Page | Route | Purpose |
|---|------|-------|---------|
| 1 | **Upload Page** | `/` | Upload 1–3 PDF documents |
| 2 | **Documents Page** | `/documents` | View all uploaded documents and delete any |
| 3 | **Chat Page** | `/chat` | Start a new multi-turn conversation |
| 4 | **Chat Page (Existing)** | `/chat/{conversation_id}` | Continue a previous conversation |

## 2.1 Chat Page Layout
- **Sidebar (left):** List of past conversations, **New Chat** button
- **Main area (right):** Chat thread with question/answer bubbles, input box at bottom

## 3. Navigation Bar
- App logo / name: "DocuAsk"
- Links: **Upload** | **Documents** | **Chat**
- Active page highlighted
- Simple, clean Tailwind styling

## 4. Upload Page (`/`)
- Header: "Upload Documents"
- Subtitle: "Upload up to 3 PDFs and ask questions about them."
- Primary action: **Upload PDFs** button / drag-and-drop area.
- Link to navigate to **Documents** or **Chat** after upload.

## 5. Upload Flow
```
[ Select 1–3 PDF files ]
         │
         ▼
[ Validate file type and count ]
         │
         ▼
[ Click Upload ]
         │
         ▼
[ Backend extracts text ]
[ Splits into chunks ]
[ Generates embeddings ]
[ Stores in pgvector ]
         │
         ▼
[ Show success: "3 documents indexed, 42 chunks stored" ]
         │
         ▼
[ Enable Ask Question input ]
```

### 5.1 Error Paths
- **Too many files:** Show "Please select a maximum of 3 PDFs."
- **Wrong file type:** Show "Only PDF files are supported."
- **Upload/parse failure:** Show "Failed to process files. Please try again."

### 5.2 Upload Processing Model
Upload is **synchronous** for simplicity. The user sees a loading/progress indicator while the backend extracts text, chunks, embeds, and stores in pgvector. For typical PDFs (1-10 pages), this takes a few seconds. The response returns only after all documents are fully indexed.

### 5.3 No Documents Uploaded State
If the user navigates to `/chat` before uploading any documents:
- Show an empty state message: **"No documents uploaded yet. Upload PDFs first to start asking questions."**
- Include a prominent **Upload Documents** button linking to `/`.
- The question input is disabled until at least one document is indexed.

## 6. Question Flow (Multi-Turn with SSE)
```
[ Type question in active conversation ]
         │
         ▼
[ Click Ask / Press Enter ]
         │
         ▼
[ Create conversation if first question ]
[ Save user message to database ]
         │
         ▼
[ Open SSE connection ]
[ Backend loads recent conversation history ]
[ Backend embeds current question ]
[ Searches pgvector for top-K chunks ]
[ Streams answer from Groq LLM ]
         │
         ▼
[ Render tokens as they arrive ]
[ Finalize assistant message ]
[ Save assistant message + citations to database ]
         │
         ▼
[ Display answer with document-level citations ]
```

### 6.1 Example Interaction (Multi-Turn)
**User uploads:** `annual_report.pdf`, `strategy_doc.pdf`

**Turn 1 — User asks:**
> What was the revenue in 2023?

**Assistant streams:**
> The revenue in 2023 was $12.4 million...

**Sources shown:**
- `annual_report.pdf` — page 3, chunk 2 — score: 0.94

**Turn 2 — User asks:**
> How does that compare to 2022?

**Assistant streams (with prior context):**
> Compared to 2022 revenue of $10.5 million, 2023 saw an 18% increase [annual_report.pdf, page 3, chunk 2].

**Sources shown:**
- `annual_report.pdf` — page 3, chunk 2 — score: 0.91

## 7. Streaming UX
- User sees answer appear token-by-token (like ChatGPT)
- Spinner/stop button while streaming
- Citations appear after answer completes (via `event: sources` SSE event)
- Input is disabled while streaming to prevent duplicate requests

### 7.1 Streaming Error Recovery
If the SSE connection drops or the backend returns an `event: error`:
1. Stop the streaming animation.
2. Show an inline error message below the partial answer: **"Something went wrong. The LLM service may be temporarily unavailable."**
3. Display a **Retry** button that re-sends the same question to the same conversation.
4. The partial answer (if any tokens were received) is preserved so the user can see what was generated before the failure.
5. If the retry also fails, suggest the user check their network or try again later.

## 8. Citation Display
Each citation card shows:
- Document name
- Page number (if extracted)
- Chunk index
- Relevance score
- Truncated chunk content (expandable)

## 9. Document List & Delete Flow

### 9.1 Documents Page Flow
```
[ User navigates to /documents ]
         │
         ▼
[ Fetch list of uploaded documents ]
         │
         ▼
[ Display cards/table: name, size, status, date ]
         │
         ▼
[ User clicks Delete on a document ]
         │
         ▼
[ Show confirmation dialog ]
         │
         ▼
[ Backend deletes file from MinIO ]
[ Backend deletes document row (cascades chunks) ]
         │
         ▼
[ Refresh document list ]
[ Show success toast ]
```

### 9.2 Document Card
- Document name
- File size
- Status badge (`uploaded`, `processing`, `indexed`, `error`)
- Upload date
- **Delete** button with confirmation

## 10. Conversation Deletion Flow
```
[ User hovers over a conversation in the sidebar ]
         │
         ▼
[ Delete icon appears next to conversation title ]
         │
         ▼
[ User clicks Delete ]
         │
         ▼
[ Show confirmation: "Delete this conversation?" ]
         │
         ▼
[ Backend deletes conversation (cascades messages) ]
         │
         ▼
[ Remove from sidebar list ]
[ If deleted conversation was active, redirect to /chat (new chat) ]
[ Show success toast: "Conversation deleted" ]
```

## 11. Navigation & Conversation Management
- **Upload More** navigates to Upload page to add more PDFs.
- **New Chat** button starts a fresh conversation (`/chat`).
- Previous conversations remain accessible via sidebar (`/chat/{id}`).
- Deleting a document removes it from MinIO and pgvector; related chat history can either be preserved with stale citations or deleted (decide based on UX preference).
- For this scope, re-uploading does not automatically replace existing documents.

## 12. End-to-End Flow Diagram
```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│   User      │────►│  React UI   │────►│  FastAPI        │
│             │     │             │     │  Backend        │
└─────────────┘     └─────────────┘     └────────┬────────┘
      ▲                    ▲                     │
      │                    │                     │
      │                    │                     ▼
      │                    │            ┌─────────────────┐
      │                    │            │  MinIO          │
      │                    │            │  (PDF storage)  │
      │                    │            └────────┬────────┘
      │                    │                     │
      │                    │                     ▼
      │                    │            ┌─────────────────┐
      │                    │            │  PDF Parser     │
      │                    │            │  Chunker        │
      │                    │            │  Embeddings     │
      │                    │            └────────┬────────┘
      │                    │                     │
      │                    │                     ▼
      │                    │            ┌─────────────────┐
      │                    │            │  PostgreSQL     │
      │                    │            │  + pgvector     │
      │                    │            └────────┬────────┘
      │                    │                     │
      │                    │                     ▼
      │                    │            ┌─────────────────┐
      │                    └────────────│  Groq LLM       │
      │                                 └─────────────────┘
      │
      └───────────────────────────────────── Answer + Citations
```

## 13. States Summary
| Screen | State | Action |
|--------|-------|--------|
| Upload Page | Empty | Select PDFs |
| Upload Page | Validating | Check file count/type |
| Upload Page | Processing | Store in MinIO, extract, chunk, embed, store in pgvector |
| Upload Page | Success | Show success, enable navigation to Documents / Chat |
| Documents Page | Loading | Fetch document list |
| Documents Page | Loaded | Show documents with delete action |
| Documents Page | Deleting | Confirm and remove document |
| Chat Page | No Documents | Show "Upload documents first" with link to Upload |
| Chat Page | Idle | Wait for question |
| Chat Page | Streaming | Open SSE, stream tokens from LLM |
| Chat Page | Answered | Show answer + document-level citations |
| Chat Page | Stream Error | Show error with Retry button |
| Chat Page | New Chat | Create new conversation |
| Chat Page | History Loaded | Show previous messages |
| Chat Page | Deleting Conversation | Confirm and remove conversation from sidebar |
