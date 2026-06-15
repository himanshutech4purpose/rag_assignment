# Plan: Hybrid Search (Semantic + Lexical BM25) + Reranker, and LLM Provider/Model Settings UI

## Goal
Upgrade the RAG Q&A pipeline so that retrieval uses **semantic search + lexical BM25 search**, fused with **Reciprocal Rank Fusion (RRF)**, then re-ranked by a cross-encoder reranker returning the **top 5** chunks. Also expose a UI settings panel where the user can choose **OpenAI or Groq**, enter/select an API key, and pick one of two models per provider.

## Current State
- **Backend:** FastAPI + PostgreSQL + pgvector + asyncpg + langchain-groq.
- **Search:** Pure cosine similarity on `document_chunks.embedding` (384-dim, all-MiniLM-L6-v2).
- **LLM:** Groq only (`GROQ_API_KEY`, `LLM_MODEL` from `.env`).
- **Frontend:** React + Vite + Tailwind + react-router-dom. No settings UI; backend URL is hardcoded in `src/api.js`.

---

## Part A: Hybrid Search + Reranker

### Approach Options

| Option | Lexical Search | Reranker | Notes |
|--------|----------------|----------|-------|
| **A (Recommended)** | PostgreSQL `tsvector`/`tsquery` + `ts_rank_cd` (practical BM25-like lexical scoring) | Local `sentence-transformers` cross-encoder | No extra network/API dependencies; leverages existing Postgres; fast enough for current scale. |
| B | In-memory `rank-bm25` over all chunks fetched per query | Local cross-encoder | True BM25 scoring, but loads more data and adds a Python dependency. |
| C | PostgreSQL FTS | Cohere / Jina AI rerank API | Best external quality but requires another API key and network call. |

**Recommended Option A** is described below.

### Backend Changes

1. **Database (`backend/init.sql`)**
   - Add a generated `tsvector` column on `document_chunks`:
     ```sql
     ALTER TABLE document_chunks
     ADD COLUMN IF NOT EXISTS search_vector tsvector
     GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
     CREATE INDEX IF NOT EXISTS idx_chunks_search_vector
     ON document_chunks USING GIN (search_vector);
     ```
   - Existing documents need re-indexing or re-upload; for existing rows the generated column will populate automatically.

2. **Configuration (`backend/app/config.py`)**
   - Add:
     ```python
     reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
     semantic_top_k: int = 20
     lexical_top_k: int = 20
     rerank_top_k: int = 5
     rrf_k: int = 60
     ```
   - Map environment variables accordingly in `.env.example`.

3. **Reranker service (`backend/app/services/reranker.py`)**
   - Load a `SentenceTransformer` cross-encoder once as a singleton.
   - Provide `rerank(query: str, chunks: list[Chunk], top_k: int) -> list[ScoredChunk]`.
   - Score pairs `(query, chunk.content)` and return sorted results.

4. **Vector store service (`backend/app/services/vector_store.py`)**
   - Keep existing `semantic_search(query_embedding, top_k)`.
   - Add `lexical_search(query_text, top_k)` using Postgres FTS:
     ```sql
     SELECT document_name, page_number, chunk_index, content,
            ts_rank_cd(search_vector, plainto_tsquery('english', $1)) AS score
     FROM document_chunks
     WHERE search_vector @@ plainto_tsquery('english', $1)
     ORDER BY score DESC
     LIMIT $2;
     ```
   - Add `hybrid_search(query_text, query_embedding, top_k)`:
     1. Fetch `semantic_top_k` results from `semantic_search`.
     2. Fetch `lexical_top_k` results from `lexical_search`.
     3. Fuse the two lists with **RRF**:
        ```
        rrf_score(doc) = sum over each list of 1 / (k + rank_in_list)
        ```
        Use `rrf_k = 60`.
     4. De-duplicate by `(document_name, page_number, chunk_index)`.
     5. Return top candidates (e.g. top 15) for the reranker.

5. **LLM service (`backend/app/services/llm.py`)**
   - Generalize to support both Groq and OpenAI:
     - Groq: keep `langchain-groq.ChatGroq`.
     - OpenAI: add `langchain-openai.ChatOpenAI`.
   - Create `get_llm(provider: str, model: str, api_key: str | None)` that picks the right client and falls back to `.env` credentials when `api_key` is not provided.

6. **Schemas (`backend/app/models/schemas.py`)**
   - Extend `AskRequest`:
     ```python
     class AskRequest(BaseModel):
         question: str
         provider: Literal["groq", "openai"] = "groq"
         model: str | None = None
         api_key: str | None = None
     ```

7. **Conversation router (`backend/app/routers/conversations.py`)**
   - In the streaming endpoint, read `provider`, `model`, `api_key` from the request.
   - Call `hybrid_search` instead of pure vector search.
   - Pass top-5 reranked chunks to the LLM.
   - Pass provider/model/api_key to `get_llm`.

8. **Dependencies (`backend/requirements.txt`)**
   - Add `langchain-openai` for OpenAI support.
   - Cross-encoder is already available via `sentence-transformers`; no extra package needed.

### Frontend Changes (Search-related)

- No direct search UI changes; results remain invisible to the user except through better answer quality and citations.

---

## Part B: Settings UI for LLM Provider / API Key / Model

### Design

Add a dedicated **Settings** page reachable from the navbar.

Controls:
1. **Provider** toggle: `Groq` | `OpenAI`.
2. **API Key** input (password field): optional; if blank, backend uses the value from `.env` (`GROQ_API_KEY` or `OPENAI_API_KEY`).
3. **Model** dropdown: two options per provider.
   - Groq defaults: `llama-3.1-8b-instant`, `mixtral-8x7b-32768`.
   - OpenAI defaults: `gpt-4o-mini`, `gpt-4o`.
   - Defaults can be overridden via `.env` (`DEFAULT_GROQ_MODEL`, `DEFAULT_OPENAI_MODEL`).
4. **Save** button persists choices to `localStorage`.

### Frontend Files

1. **`src/App.jsx`**
   - Add route: `<Route path="/settings" element={<SettingsPage />} />`.

2. **`src/pages/SettingsPage.jsx`** (new)
   - Form with provider, key, model selection.
   - Load/save from `localStorage`:
     ```js
     localStorage.setItem('llm_provider', provider);
     localStorage.setItem('llm_api_key', apiKey);
     localStorage.setItem('llm_model', model);
     ```

3. **`src/components/Navbar.jsx`**
   - Add a `Settings` nav link.

4. **`src/api.js`**
   - Extend `streamQuestion` to include provider/model/api_key in the POST body:
     ```js
     body: JSON.stringify({ question, provider, model, api_key: apiKey })
     ```

5. **`src/components/Chat.jsx`**
   - On submit, read settings from `localStorage` and pass them to `streamQuestion`.

### Backend Environment (`.env.example`)

Add OpenAI variables and new defaults:
```bash
# Existing
GROQ_API_KEY=...
LLM_MODEL=llama-3.1-8b-instant

# New
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
GROQ_MODEL_A=llama-3.1-8b-instant
GROQ_MODEL_B=mixtral-8x7b-32768
OPENAI_MODEL_A=gpt-4o-mini
OPENAI_MODEL_B=gpt-4o
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
SEMANTIC_TOP_K=20
LEXICAL_TOP_K=20
RERANK_TOP_K=5
RRF_K=60
```

---

## Implementation Phases

### Phase 1: Database + Backend Retrieval
1. Update `backend/init.sql` to add `search_vector` tsvector column and GIN index.
2. Implement `lexical_search` in `backend/app/services/vector_store.py`.
3. Implement RRF fusion in `hybrid_search`.

### Phase 2: Reranker
1. Add `backend/app/services/reranker.py` with cross-encoder singleton.
2. Wire `hybrid_search` → reranker → top 5 in `conversations.py`.

### Phase 3: Multi-Provider LLM
1. Add `langchain-openai` to requirements.
2. Refactor `backend/app/services/llm.py` to support Groq and OpenAI with request overrides.
3. Update `AskRequest` schema.

### Phase 4: Frontend Settings
1. Add `/settings` route and `SettingsPage`.
2. Add Settings nav link.
3. Persist/load settings from `localStorage`.
4. Send provider/model/api_key with every question.

### Phase 5: Env + Docs
1. Update `.env.example` and `backend/app/config.py`.
2. Update `README.md`, `hld.md`, and `lld.md` with the new retrieval and settings flows.

---

## Open Questions / Decisions for User

1. **BM25 implementation:** Use native Postgres full-text search (recommended, no new deps) or the `rank-bm25` Python package (true BM25 but heavier)?
2. **Reranker model:** Use local `cross-encoder/ms-marco-MiniLM-L-6-v2` (recommended), or a different model such as `BAAI/bge-reranker-base`?
3. **Model list:** Which two Groq and two OpenAI models should be offered by default in the settings dropdown?
4. **API key handling:** Should the frontend store the API key in `localStorage` (convenient but persisted in browser), or should it send it per-request without storing? Sending per-request only (memory-only) is more secure but resets on reload.
