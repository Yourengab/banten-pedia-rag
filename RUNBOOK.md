# BantenPedia RAG — Runbook

Panduan lengkap untuk setup dan menjalankan BantenPedia RAG dari awal sampai jalan.

---

## Prasyarat

Pastikan sudah terinstall:
- Python 3.11+
- Git
- Akun [Supabase](https://supabase.com)
- Akun [Google AI Studio](https://aistudio.google.com) (untuk Gemini API Key)

---

## Langkah 1 — Clone & Setup Virtual Environment

```bash
git clone https://github.com/Yourengab/banten-pedia-rag.git
cd banten-pedia-rag

# Buat virtual environment
python -m venv .venv

# Aktifkan (Mac/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install dependencies tambahan untuk ingestion PDF dan DOCX
pip install pypdf python-docx
```

---

## Langkah 2 — Isi File .env

```bash
cp .env.example .env
```

Buka `.env` dan isi semua variabel:

```env
# Dari Supabase Dashboard → Settings → API
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key

# Dari Google AI Studio → Get API Key
GEMINI_API_KEY=your-gemini-api-key

# Biarkan default (tidak perlu diubah)
GEMINI_MODEL=gemini-2.0-flash
EMBEDDING_MODEL=gemini-embedding-2
EMBEDDING_DIMENSION=768
DEFAULT_TOP_K=5
SIMILARITY_THRESHOLD=0.70
CHUNK_SIZE_TOKENS=750
CHUNK_OVERLAP_TOKENS=100
EMBEDDING_BATCH_SIZE=20
```

---

## Langkah 3 — Setup Database Supabase

1. Buka [Supabase Dashboard](https://supabase.com/dashboard)
2. Pilih project kamu
3. Klik **SQL Editor** di sidebar kiri
4. Buka file `sql/schema.sql` dari project ini
5. Copy semua isinya → paste ke SQL Editor → klik **Run**

Ini akan membuat:
- Tabel `documents`
- Tabel `document_chunks` dengan kolom `embedding VECTOR(768)`
- Function `match_document_chunks()` untuk vector search
- Function `match_document_chunks_filtered()` untuk filtered search

> ⚠️ **Pastikan pgvector extension sudah aktif.** Supabase biasanya sudah mengaktifkannya secara default. Kalau belum, jalankan: `CREATE EXTENSION IF NOT EXISTS vector;`

---

## Langkah 4 — Jalankan Server FastAPI

```bash
# Masuk ke folder app
cd app

# Jalankan server
uvicorn main:app --reload
```

Server akan berjalan di: **http://localhost:8000**

Cek liveness:
```bash
curl http://localhost:8000/health
# → {"status":"ok","service":"BantenPedia RAG API"}
```

Buka dokumentasi interaktif: **http://localhost:8000/docs**

---

## Langkah 5 — Upload Dokumen (Ingestion)

### Via API (curl)

```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@/path/to/buku_banten.pdf" \
  -F "title=Buku Banten Bali" \
  -F "source_type=book" \
  -F "description=Dokumentasi lengkap banten Bali"
```

Format file yang didukung: `.pdf`, `.txt`, `.md`, `.docx`

Contoh response sukses:
```json
{
  "document_id": "uuid-xxx",
  "chunks_inserted": 47,
  "version": 1,
  "message": "Document 'Buku Banten Bali' ingested successfully. 47 chunks created (version 1)."
}
```

### Via Python Script (alternatif)

Buat file `ingest_local.py` di folder root:
```python
import sys
sys.path.insert(0, "app")

from ingestion.pipeline import ingest_file

result = ingest_file(
    path="data/buku_banten.pdf",
    title="Buku Banten Bali",
    source_type="book",
    description="Dokumentasi banten Bali",
)
print(f"Selesai: {result.chunks_inserted} chunks (doc: {result.document_id})")
```

Jalankan:
```bash
python ingest_local.py
```

---

## Langkah 6 — Test RAG Search

### Via curl

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Apa itu Canang Sari?", "top_k": 5}'
```

### Dengan Hybrid Search

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Apa komponen Banten Pejati?",
    "top_k": 5,
    "use_hybrid": true,
    "similarity_threshold": 0.65
  }'
```

---

## Langkah 7 — Chat dengan AI Agent

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Apa makna Canang Sari dalam kehidupan sehari-hari?"}'
```

Response:
```json
{
  "answer": "Canang Sari merupakan...",
  "sources": [
    {
      "title": "Buku Banten Bali",
      "source_type": "book",
      "file_url": null,
      "version": 1
    }
  ],
  "search_performed": true,
  "conflict_detected": false
}
```

### Chat dengan opsi lengkap

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Apa komponen Banten Pejati?",
    "top_k": 5,
    "similarity_threshold": 0.70,
    "use_hybrid": true,
    "expand_query": true
  }'
```

---

## Langkah 8 — Jalankan MCP Server (untuk AI Agent eksternal)

```bash
cd app
python mcp_server.py
```

MCP server berjalan via stdio, siap diintegrasikan dengan Claude Desktop, Cursor, atau MCP client lain.

Konfigurasi MCP client (contoh untuk Claude Desktop):
```json
{
  "mcpServers": {
    "bantenpedia": {
      "command": "python",
      "args": ["/absolute/path/to/app/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/app"
      }
    }
  }
}
```

---

## Langkah 9 — Evaluasi RAG

Pastikan sudah ada dokumen yang diingestion terlebih dahulu.

```bash
cd app

# Evaluasi penuh (8 query dari dataset)
python -m evaluation.evaluator

# Output JSON
python -m evaluation.evaluator --json

# Test satu query spesifik
python -m evaluation.evaluator --query "Apa itu Canang Sari?"

# Ubah threshold dan top-k
python -m evaluation.evaluator --threshold 0.65 --top-k 10
```

Contoh output:
```
[eval-001] Query: 'Apa itu Canang Sari?'
  ✅ PASS | retrieved=5 | precision=0.80 | recall=1.00 | top_sim=0.87

============================================================
EVALUATION SUMMARY
============================================================
Total queries   : 8
Passed          : 7 (87%)
Avg Precision   : 0.752
Avg Recall      : 0.875
Avg Top Sim     : 0.831
============================================================
```

---

## Lihat Daftar Dokumen

```bash
# Semua dokumen aktif
curl http://localhost:8000/documents

# Filter berdasarkan source type
curl "http://localhost:8000/documents?source_type=book"

# Termasuk versi lama (tidak aktif)
curl "http://localhost:8000/documents?active_only=false"

# Detail satu dokumen
curl http://localhost:8000/documents/{document_id}
```

---

## Hapus / Nonaktifkan Dokumen

Dokumen tidak dihapus permanen, hanya dinonaktifkan (tidak muncul di search).
Re-ingest dengan title yang sama akan otomatis membuat versi baru.

```bash
curl -X DELETE http://localhost:8000/documents/{document_id}
```

---

## Struktur Direktori Penting

```
banten-pedia-rag/
├── .env                    ← isi ini dulu!
├── .env.example            ← template
├── requirements.txt
│
├── sql/
│   └── schema.sql          ← jalankan ini di Supabase SQL Editor
│
└── app/
    ├── main.py             ← FastAPI server (uvicorn main:app)
    ├── mcp_server.py       ← MCP server (python mcp_server.py)
    ├── config.py           ← semua env var
    │
    ├── ingestion/          ← pipeline upload dokumen
    ├── agent/              ← AI agent + prompts
    ├── tools/              ← search_knowledge, search_banten
    ├── database/           ← supabase client
    └── evaluation/         ← test & metrics
```

---

## Urutan Menjalankan (Ringkasan)

```
1. git clone → pip install
2. cp .env.example .env → isi API keys
3. Jalankan sql/schema.sql di Supabase SQL Editor
4. cd app → uvicorn main:app --reload
5. Upload dokumen via POST /ingest
6. Chat via POST /chat
7. Evaluasi via python -m evaluation.evaluator
```

---

## Troubleshooting

| Error | Solusi |
|-------|--------|
| `SUPABASE_URL atau SUPABASE_KEY belum diatur` | Cek file `.env`, pastikan tidak ada spasi |
| `GEMINI_API_KEY belum diatur di .env` | Tambahkan GEMINI_API_KEY di `.env` |
| `Failed to generate query embedding` | Cek koneksi internet dan validity API key |
| `No usable text extracted` | File mungkin kosong atau hasil scan tanpa OCR |
| `relation "document_chunks" does not exist` | Jalankan `sql/schema.sql` di Supabase dulu |
| `vector extension not found` | Jalankan `CREATE EXTENSION IF NOT EXISTS vector;` di Supabase SQL Editor |
| Import error `pypdf` / `docx` | Jalankan `pip install pypdf python-docx` |
