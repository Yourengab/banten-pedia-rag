# BantenPedia RAG

RAG-powered AI assistant for knowledge about Balinese banten (offerings).

## Stack
- **Backend**: FastAPI + Python
- **Database**: Supabase PostgreSQL + pgvector
- **Embedding**: Gemini Embedding 2 (768 dims)
- **LLM**: Gemini
- **Tool Protocol**: MCP (Model Context Protocol)

## Project Structure

```
app/
├── config.py              # Centralised configuration
├── main.py                # FastAPI app (chat, ingest, documents, search)
├── mcp_server.py          # MCP server with all tools
│
├── agent/
│   ├── agent.py           # AI agent with grounded generation
│   └── prompts.py         # System prompt + context construction
│
├── database/
│   └── supabase.py        # Supabase client
│
├── ingestion/
│   ├── pipeline.py        # Orchestrates full ingestion
│   ├── extractor.py       # PDF, TXT, MD, DOCX text extraction
│   ├── cleaner.py         # Text cleaning (preserves cultural terms)
│   ├── chunker.py         # Paragraph-based chunking with overlap
│   ├── embedder.py        # Batched Gemini embedding generation
│   └── uploader.py        # Supabase upload with versioning
│
├── tools/
│   ├── banten.py          # search_banten(), get_banten(), get_components()
│   └── knowledge.py       # search_knowledge() with hybrid + RAG
│
├── mcp_client/
│   └── client.py          # Async MCP client wrapper
│
└── evaluation/
    ├── dataset.py         # Sample Q&A evaluation dataset
    └── evaluator.py       # RAG metrics: precision, recall, faithfulness

sql/
└── schema.sql             # Supabase tables + pgvector RPC functions

scripts/
├── ingest_documents.py    # Batch ingestion script
├── merge_script.py        # Dataset merger for web_viz
└── test_one.py            # Single-file test runner

web_viz/                   # Web visualization UI & data
```

## Setup

```bash
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY
```

Run the schema in Supabase SQL Editor:
```sql
-- sql/schema.sql
```

Install dependencies:
```bash
pip install -r requirements.txt
pip install pypdf python-docx   # for PDF/DOCX ingestion
```

## Ingestion

```bash
# Test with first PDF
python scripts/ingest_documents.py --test

# Process all PDFs
python scripts/ingest_documents.py

# Merge datasets into web_viz/data.json
python scripts/merge_script.py
```

## Running

```bash
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness check |
| POST | `/chat` | Ask the AI agent |
| POST | `/search` | Direct RAG search (debug) |
| POST | `/ingest` | Upload & ingest a document |
| GET | `/documents` | List documents |
| GET | `/documents/{id}` | Get document + chunk count |
| DELETE | `/documents/{id}` | Deactivate document |

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_knowledge()` | RAG search with hybrid + multi-query expansion |
| `search_banten()` | Search structured banten database |
| `get_banten()` | Get single banten detail |
| `get_components()` | Get banten components |

## Evaluation

```bash
python -m app.evaluation.evaluator              # Full suite
python -m app.evaluation.evaluator --json       # JSON output
python -m app.evaluation.evaluator --query "Apa itu Canang Sari?"
```
