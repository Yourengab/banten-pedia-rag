# BantenPedia RAG API

Backend API for **BantenPedia** — an AI assistant for knowledge about Balinese _banten_ (offerings). Built with FastAPI, Supabase, and Google Gemini.

## 🚀 Features

### 1. RAG Ingestion Pipeline (`app/ingestion/`)

- **Extraction:** Supports `.pdf`, `.txt`, `.md`, and `.docx`.
- **Cleaning:** Automatic text normalization and noise removal.
- **Chunking:** Token-based semantic chunking with overlap.
- **Embedding:** Generates high-dimensional vectors via `gemini-embedding-2`.
- **Storage:** Persists documents and chunks in Supabase with `pgvector` support.

### 2. Retrieval Engine (`app/tools/knowledge.py`)

- **Semantic Search:** Vector similarity search using cosine distance.
- **Hybrid Search:** Combines vector results with keyword-based (ILIKE) search using Reciprocal Rank Fusion (RRF).
- **Multi-Query Expansion:** Automatically generates alternative query phrasings to improve recall.
- **Metadata Filtering:** Filter by source type (e.g., 'book').
- **Citations:** Returns page numbers and document metadata for grounded answers.

### 3. Agentic Chat (`app/agent/`)

- **Gemini-Powered:** Uses `gemini-1.5-flash` (or latest) for reasoning and response generation.
- **Session Management:** Built-in chat history and session persistence in `app/chat/`.
- **Conflict Detection:** Identifies when retrieved knowledge contradicts user assumptions.

## 🛠 Tech Stack

- **Framework:** FastAPI
- **Database:** Supabase (PostgreSQL + pgvector)
- **LLM/Embeddings:** Google Gemini API
- **Language:** Python 3.10+

## ⚙️ Configuration

Create a `.env` file in the root directory:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
GEMINI_API_KEY=your_gemini_api_key

# Optional Defaults
EMBEDDING_MODEL=gemini-embedding-2
GEMINI_MODEL=gemini-3.5-flash-lite
DEFAULT_TOP_K=5
SIMILARITY_THRESHOLD=0.60
```

## 🏃 Running the Application

1. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

2. **Run the server:**
    ```bash
    cd app
    uvicorn main:app --reload
    ```
    _The API will be available at `http://localhost:8000`. Docs at `/docs`._

## 📍 API Endpoints

| Method | Endpoint     | Description                                |
| :----- | :----------- | :----------------------------------------- |
| `POST` | `/chat`      | Conversational RAG with session history.   |
| `POST` | `/ingest`    | Upload and process new documents.          |
| `POST` | `/search`    | Direct retrieval (vector + hybrid) search. |
| `GET`  | `/documents` | List ingested knowledge sources.           |
| `GET`  | `/health`    | Service liveness check.                    |
