````markdown
# PRD — RAG Knowledge Retrieval BantenPedia

## 1. Informasi Dokumen

| Item                | Detail                               |
| ------------------- | ------------------------------------ |
| Project             | BantenPedia                          |
| Module              | Retrieval-Augmented Generation (RAG) |
| Versi               | MVP                                  |
| Status              | Development                          |
| Backend             | FastAPI + Python                     |
| Database            | Supabase PostgreSQL                  |
| Vector Store        | pgvector                             |
| Embedding Model     | Gemini Embedding 2                   |
| Embedding Dimension | 768                                  |
| LLM                 | Gemini                               |
| Interface           | MCP Tool                             |
| Tool utama          | `search_knowledge()`                 |

---

# 2. Latar Belakang

BantenPedia merupakan platform digital untuk mendokumentasikan dan mengeksplorasi pengetahuan mengenai banten Bali.

Informasi mengenai banten berasal dari berbagai sumber seperti buku, dokumen, hasil dokumentasi, dan sumber pengetahuan lainnya. Informasi tersebut dapat memiliki istilah lokal, variasi regional, serta konteks budaya yang tidak selalu dapat dijawab dengan mengandalkan pengetahuan bawaan Large Language Model (LLM).

Oleh karena itu, BantenPedia membutuhkan mekanisme Retrieval-Augmented Generation (RAG) agar jawaban AI dapat menggunakan pengetahuan yang tersimpan dalam repository BantenPedia.

RAG bertugas mengambil informasi yang relevan dari sumber pengetahuan sebelum informasi tersebut diberikan kepada LLM sebagai konteks.

---

# 3. Tujuan

## 3.1 Tujuan Utama

Membangun sistem retrieval yang mampu menemukan potongan informasi paling relevan dari knowledge repository BantenPedia berdasarkan pertanyaan pengguna.

## 3.2 Tujuan Khusus

1. Menyimpan dokumen sumber pengetahuan secara terstruktur.
2. Memecah dokumen menjadi potongan informasi (chunk).
3. Mengubah setiap chunk menjadi vector embedding.
4. Menyimpan embedding menggunakan PostgreSQL + pgvector.
5. Melakukan semantic similarity search berdasarkan pertanyaan pengguna.
6. Mengembalikan beberapa sumber paling relevan kepada AI Agent.
7. Menyediakan metadata sumber agar jawaban dapat ditelusuri kembali.
8. Mengurangi kemungkinan LLM menghasilkan informasi budaya yang tidak memiliki sumber.

---

# 4. Prinsip Utama

RAG BantenPedia harus mengikuti prinsip:

> Retrieve first, generate second.

LLM tidak boleh menjadi sumber utama fakta budaya ketika informasi yang relevan tersedia di knowledge repository.

RAG hanya bertugas mengambil informasi.

RAG tidak bertugas:

- menentukan kebenaran budaya secara mandiri;
- membuat fakta baru;
- menggantikan validasi ahli;
- mengubah isi sumber;
- menentukan apakah suatu tradisi benar atau salah.

---

# 5. Scope MVP

## 5.1 Termasuk

- Document storage
- Document metadata
- Text chunking
- Embedding generation
- Vector storage
- Semantic search
- Similarity ranking
- Retrieval melalui MCP
- Pengembalian metadata sumber
- Integrasi dengan AI Agent

## 5.2 Tidak Termasuk MVP

- OCR otomatis
- Automatic fact checking
- Knowledge graph reasoning
- Hybrid search
- Reranking model
- Automatic document validation
- Automatic cultural interpretation
- `compare_banten()`

Fitur tersebut dapat dikembangkan pada fase berikutnya.

---

# 6. Arsitektur

```text
                    USER
                      │
                      ▼
                 Next.js Web
                      │
                      ▼
                FastAPI Agent
                      │
                      ▼
                  AI Agent
                   Gemini
                      │
                      ▼
                 MCP Client
                      │
                      ▼
                MCP Server
                      │
              search_knowledge()
                      │
                      ▼
            Supabase PostgreSQL
                      │
             ┌────────┴────────┐
             ▼                 ▼
        documents       document_chunks
                               │
                               ▼
                         pgvector
                               │
                               ▼
                    Semantic Similarity
```
````

---

# 7. Data Model

## 7.1 Table `documents`

Menyimpan metadata dokumen sumber.

| Field       | Type        | Description       |
| ----------- | ----------- | ----------------- |
| id          | UUID        | Primary key       |
| title       | TEXT        | Judul dokumen     |
| source_type | TEXT        | Jenis sumber      |
| file_url    | TEXT        | Lokasi file       |
| description | TEXT        | Deskripsi dokumen |
| created_at  | TIMESTAMPTZ | Waktu dibuat      |

Contoh:

```json
{
    "id": "uuid",
    "title": "Banten Bali",
    "source_type": "book",
    "file_url": "https://...",
    "description": "Dokumentasi banten Bali"
}
```

---

## 7.2 Table `document_chunks`

Menyimpan potongan teks dan embedding.

| Field       | Type        | Description         |
| ----------- | ----------- | ------------------- |
| id          | UUID        | Primary key         |
| document_id | UUID        | Relasi ke documents |
| content     | TEXT        | Isi chunk           |
| chunk_index | INTEGER     | Urutan chunk        |
| embedding   | VECTOR(768) | Vector embedding    |

Relasi:

```text
documents
    │
    │ 1:N
    ▼
document_chunks
```

---

# 8. Document Ingestion Pipeline

Dokumen yang akan digunakan sebagai knowledge source harus melewati pipeline berikut:

```text
Document
   │
   ▼
Text Extraction
   │
   ▼
Cleaning
   │
   ▼
Chunking
   │
   ▼
Embedding
   │
   ▼
Vector Storage
```

---

# 9. Text Extraction

Sistem mengambil teks dari dokumen sumber.

Sumber dapat berupa:

- PDF
- TXT
- Markdown
- DOCX
- hasil transkripsi OCR

Untuk PDF hasil scan, OCR dilakukan sebelum masuk ke pipeline RAG.

RAG tidak bertanggung jawab terhadap proses OCR.

---

# 10. Text Cleaning

Cleaning dilakukan untuk menghilangkan noise tanpa mengubah makna asli sumber.

### Boleh dilakukan

- Menghapus whitespace berlebihan.
- Menghapus karakter yang tidak diperlukan.
- Menggabungkan baris yang terpotong.
- Membersihkan artefak OCR yang jelas.

### Tidak boleh dilakukan

- Mengubah istilah budaya.
- Mengubah nama banten.
- Mengubah nama lokal.
- Mengubah makna.
- Menerjemahkan istilah Bali secara otomatis.
- Menambahkan informasi yang tidak terdapat pada sumber.

Contoh:

```text
Canang
Sari merupakan salah satu...
```

dapat diperbaiki menjadi:

```text
Canang Sari merupakan salah satu...
```

Tetapi istilah seperti:

```text
banten pejati
sampian
porosan
canang sari
```

harus dipertahankan.

---

# 11. Chunking

Dokumen dibagi menjadi beberapa chunk agar retrieval dapat mengambil bagian yang relevan.

## Prinsip Chunking

Chunk sebaiknya:

- cukup kecil untuk retrieval yang spesifik;
- cukup besar untuk mempertahankan konteks;
- tidak memotong informasi penting;
- mempertahankan hubungan antar paragraf.

Struktur dasar:

```text
Document
 ├── Chunk 0
 ├── Chunk 1
 ├── Chunk 2
 ├── Chunk 3
 └── ...
```

## Rekomendasi MVP

Gunakan chunk berbasis paragraf dengan ukuran target sekitar:

```text
500–1000 token
```

dengan overlap kecil jika diperlukan.

Chunk tidak boleh memisahkan:

- judul dengan isi;
- nama banten dengan deskripsinya;
- komponen dengan penjelasannya;
- makna dengan konteks yang menjelaskannya.

---

# 12. Embedding

Setiap chunk dikonversi menjadi vector embedding menggunakan:

```text
Gemini Embedding 2
```

Dimension:

```text
768
```

Pipeline:

```text
Chunk
  │
  ▼
Gemini Embedding 2
  │
  ▼
768-dimensional vector
  │
  ▼
pgvector
```

Contoh:

```text
"Canang Sari merupakan salah satu..."
                │
                ▼
       [0.021, -0.114, ...]
                │
                ▼
        vector(768)
```

---

# 13. Vector Storage

Embedding disimpan pada:

```text
document_chunks.embedding
```

menggunakan PostgreSQL `pgvector`.

Database:

```text
Supabase PostgreSQL
```

---

# 14. Similarity Search

Ketika pengguna mengajukan pertanyaan:

```text
Apa makna Canang Sari?
```

sistem melakukan:

```text
User Query
    │
    ▼
Query Embedding
    │
    ▼
Vector Similarity Search
    │
    ▼
Top K Chunks
```

Similarity menggunakan cosine distance melalui pgvector.

Function database:

```text
match_document_chunks()
```

Output:

```json
{
    "id": "uuid",
    "document_id": "uuid",
    "content": "...",
    "chunk_index": 4,
    "similarity": 0.87
}
```

---

# 15. Retrieval

MCP Server menyediakan tool:

```text
search_knowledge()
```

Input:

```json
{
    "query": "Apa makna Canang Sari?",
    "top_k": 5
}
```

Output:

```json
[
    {
        "content": "Canang Sari merupakan...",
        "chunk_index": 4,
        "similarity": 0.87,
        "source": {
            "id": "uuid",
            "title": "Buku Banten Bali",
            "source_type": "book"
        }
    }
]
```

---

# 16. Top-K Retrieval

MVP menggunakan:

```text
top_k = 5
```

Artinya sistem mengambil maksimal lima chunk dengan similarity tertinggi.

Namun jumlah tersebut dapat dikonfigurasi.

Contoh:

```text
top_k = 3
top_k = 5
top_k = 10
```

Nilai awal:

```text
5
```

---

# 17. Similarity Threshold

Sistem harus menghindari penggunaan sumber yang terlalu tidak relevan.

Contoh:

```text
similarity >= 0.70
```

dapat digunakan sebagai threshold awal.

Namun nilai threshold harus dievaluasi menggunakan dataset pertanyaan nyata.

Threshold bukan nilai absolut dan dapat berubah berdasarkan hasil evaluasi.

---

# 18. Context Construction

Hasil retrieval diberikan kepada AI Agent sebagai context.

Contoh:

```text
[CONTEXT]

Source: Buku Banten Bali
Chunk: 4

Canang Sari merupakan salah satu bentuk persembahan
yang digunakan dalam kehidupan sehari-hari masyarakat Bali.

[END CONTEXT]
```

LLM kemudian menggunakan context tersebut untuk menghasilkan jawaban.

---

# 19. Grounded Generation

LLM harus menghasilkan jawaban berdasarkan context yang diperoleh.

Aturan:

1. Prioritaskan informasi dari retrieved context.
2. Jangan membuat fakta budaya tanpa dasar.
3. Jangan mengubah makna sumber.
4. Jika informasi tidak tersedia, katakan bahwa informasi belum ditemukan.
5. Jangan menganggap informasi umum dari model sebagai fakta lokal.
6. Jika terdapat perbedaan antar sumber, tampilkan perbedaan tersebut.

---

# 20. Source Attribution

Jawaban ideal harus dapat menunjukkan sumber informasi.

Contoh:

```text
Canang Sari digunakan sebagai salah satu bentuk
persembahan sehari-hari dalam masyarakat Bali.

Sumber:
Buku Banten Bali
```

Metadata minimal:

```text
source.title
source.source_type
```

Pada pengembangan berikutnya dapat ditambahkan:

```text
page_number
author
publication_year
source_url
```

---

# 21. Penanganan Informasi Tidak Ditemukan

Jika retrieval tidak menemukan informasi yang relevan:

```text
similarity < threshold
```

maka sistem tidak boleh memaksakan jawaban.

Contoh respons:

> Maaf, informasi mengenai hal tersebut belum ditemukan dalam knowledge repository BantenPedia.

LLM tetap dapat memberikan konteks umum jika fitur tersebut diizinkan, tetapi harus membedakan antara:

```text
informasi dari sumber BantenPedia
```

dan

```text
pengetahuan umum model
```

Untuk MVP, lebih aman memprioritaskan jawaban berbasis repository.

---

# 22. Penanganan Konflik Sumber

Jika dua sumber memberikan informasi berbeda:

```text
Source A
→ Banten menggunakan komponen X

Source B
→ Banten menggunakan komponen Y
```

sistem tidak boleh memilih salah satu secara otomatis.

Jawaban harus menunjukkan:

```text
Menurut sumber A: ...
Menurut sumber B: ...
```

Perbedaan dapat menjadi informasi penting untuk dokumentasi variasi budaya antar wilayah.

---

# 23. MCP Integration

RAG diakses oleh AI Agent melalui MCP.

Tool:

```text
search_knowledge()
```

Tanggung jawab MCP Server:

- menerima query;
- membuat embedding;
- melakukan vector search;
- mengambil metadata sumber;
- mengembalikan hasil retrieval.

MCP Server tidak bertugas menghasilkan jawaban akhir.

---

# 24. Tanggung Jawab Komponen

| Komponen           | Tanggung Jawab                        |
| ------------------ | ------------------------------------- |
| Document Processor | Extract dan cleaning text             |
| Chunker            | Membagi dokumen                       |
| Embedding Service  | Membuat embedding                     |
| Supabase           | Menyimpan dokumen dan vector          |
| pgvector           | Similarity search                     |
| MCP Server         | Menyediakan retrieval tool            |
| MCP Client         | Memanggil MCP Server                  |
| AI Agent           | Menentukan kapan retrieval diperlukan |
| Gemini             | Menghasilkan jawaban                  |
| Next.js            | Menampilkan hasil kepada pengguna     |

---

# 25. Query Flow

Ketika pengguna bertanya:

```text
Apa saja komponen Banten Pejati?
```

alur:

```text
User
 │
 ▼
Next.js
 │
 ▼
FastAPI Agent
 │
 ▼
Gemini
 │
 │ membutuhkan informasi knowledge
 ▼
MCP Client
 │
 ▼
search_knowledge()
 │
 ▼
Generate Query Embedding
 │
 ▼
pgvector
 │
 ▼
Top 5 Chunks
 │
 ▼
MCP Client
 │
 ▼
Gemini
 │
 ▼
Final Answer
```

---

# 26. Kriteria Keberhasilan MVP

RAG dianggap berhasil jika:

### Retrieval

- Query dapat menghasilkan embedding.
- Embedding tersimpan dengan benar.
- Vector search berjalan.
- Top-K chunk dapat dikembalikan.
- Metadata sumber ikut dikembalikan.

### Relevance

Sebagian besar hasil retrieval harus relevan terhadap pertanyaan.

### Grounding

Jawaban AI dapat ditelusuri ke retrieved context.

### Reliability

Jika informasi tidak tersedia, sistem tidak mengarang informasi.

### Integration

`search_knowledge()` dapat dipanggil melalui MCP Client.

---

# 27. Evaluasi RAG

Evaluasi dilakukan menggunakan dataset pertanyaan mengenai banten.

Contoh:

| Query                                             | Expected Information   |
| ------------------------------------------------- | ---------------------- |
| Apa itu Canang Sari?                              | Deskripsi Canang Sari  |
| Apa makna Canang Sari?                            | Makna Canang Sari      |
| Apa komponen Banten Pejati?                       | Komponen Banten Pejati |
| Bagaimana fungsi Banten Pejati?                   | Fungsi Banten Pejati   |
| Apa perbedaan banten X di Bali Utara dan Selatan? | Informasi regional     |

Metric awal:

### Retrieval Relevance

Apakah chunk yang ditemukan relevan terhadap query?

### Context Precision

Apakah informasi yang diberikan kepada LLM benar-benar relevan?

### Context Recall

Apakah informasi penting berhasil ditemukan?

### Answer Faithfulness

Apakah jawaban sesuai dengan context yang diberikan?

---

# 28. Target MVP

Target awal:

```text
Documents       : ≥ 5
Chunks          : ≥ 100
Embedding       : 100% berhasil
Top-K           : 5
Vector Search   : aktif
MCP Tool        : aktif
LLM Integration : aktif
Source Metadata : tersedia
```

Target kualitas retrieval akan ditentukan setelah dataset pertanyaan tersedia.

---

# 29. Error Handling

Jika embedding gagal:

```text
Return error:
"Failed to generate query embedding."
```

Jika Supabase gagal:

```text
Return error:
"Knowledge retrieval service unavailable."
```

Jika tidak ada hasil:

```text
Return:
[]
```

AI Agent kemudian menentukan respons berdasarkan kondisi tersebut.

---

# 30. Security

API key tidak boleh disimpan di source code.

Gunakan:

```text
.env
```

Contoh:

```env
GEMINI_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
EMBEDDING_MODEL=gemini-embedding-2
EMBEDDING_DIMENSION=768
```

`.env` tidak boleh di-commit ke repository.

---

# 31. Future Development

Setelah MVP stabil, RAG dapat dikembangkan menjadi:

```text
MVP
 │
 ├── Hybrid Search
 │     ├── Vector Search
 │     └── Keyword Search
 │
 ├── Reranking
 │
 ├── Metadata Filtering
 │     ├── Kabupaten
 │     ├── Kecamatan
 │     └── Desa Adat
 │
 ├── Page-level Citation
 │
 ├── Document Versioning
 │
 └── Advanced Retrieval
       ├── Multi-query
       └── Query Expansion
```

Pengembangan berikutnya juga dapat mengintegrasikan knowledge graph/ontology untuk kebutuhan reasoning yang lebih kompleks.

---

# 32. Non-Functional Requirements

## Performance

Target awal retrieval:

```text
< 2 detik
```

tidak termasuk waktu generasi LLM.

## Reliability

Jika RAG gagal, sistem harus memberikan error yang jelas kepada Agent.

## Maintainability

Kode harus dipisahkan berdasarkan tanggung jawab:

```text
app/
├── database/
│   └── supabase.py
│
├── tools/
│   ├── banten.py
│   └── knowledge.py
│
├── mcp_client/
│   └── client.py
│
├── agent/
│   └── agent.py
│
└── mcp_server.py
```

---

# 33. Definition of Done

RAG MVP dianggap selesai apabila:

- [ ] Dokumen dapat dimasukkan ke repository.
- [ ] Dokumen dapat dipecah menjadi chunk.
- [ ] Chunk memiliki embedding 768 dimensi.
- [ ] Embedding tersimpan di `document_chunks`.
- [ ] `match_document_chunks()` berjalan.
- [ ] `search_knowledge()` berjalan.
- [ ] MCP Server mendaftarkan `search_knowledge()`.
- [ ] MCP Client dapat memanggil `search_knowledge()`.
- [ ] Agent dapat menggunakan hasil retrieval.
- [ ] Gemini dapat menghasilkan jawaban berdasarkan context.
- [ ] Sumber dapat ditampilkan.
- [ ] Sistem tidak memaksakan jawaban ketika informasi tidak ditemukan.
- [ ] Evaluasi retrieval dilakukan menggunakan dataset pertanyaan.

---

# 34. Prinsip Desain Akhir

RAG BantenPedia harus diposisikan sebagai:

> **Knowledge Retrieval Layer untuk memastikan AI Agent dapat mengakses pengetahuan banten yang terdokumentasi dan bersumber.**

Bukan sebagai:

> **AI yang menentukan kebenaran budaya Bali.**

Dengan demikian, sumber tetap menjadi dasar pengetahuan, sedangkan LLM berfungsi sebagai antarmuka untuk memahami pertanyaan, memilih informasi yang relevan, dan menyusun jawaban.

```

**Catatan penting:** PRD ini sengaja memisahkan **RAG** dari tabel `banten`, `komponen`, dan `banten_komponen`. Data terstruktur tetap menjadi **database utama**, sedangkan `document_chunks` berfungsi sebagai **knowledge repository berbasis dokumen**. Jadi nanti Agent bisa memilih:

- `search_banten()` → mencari data terstruktur.
- `get_components()` → mengambil komponen banten.
- `search_knowledge()` → mencari penjelasan dari buku/dokumen/sumber.
- Gemini → menggabungkan hasil tersebut menjadi jawaban.

Menurut saya ini lebih tepat untuk arsitektur BantenPedia daripada menjadikan semua informasi masuk ke vector database.
```
