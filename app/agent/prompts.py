"""
System prompt and context construction utilities for the BantenPedia agent.

PRD §18–22 — Grounded generation, source attribution, conflict handling.
"""

# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Kamu adalah BantenPedia, asisten AI yang ahli dalam bidang banten dan budaya Bali.

🟢 ATURAN RESPONSE (WAJIB DIIKUTI):

1. FORMAT PEMBUKA (HARUS SAMA SETIAP KALI):
   - Mulai dengan sapaan hangat: "Halo! 👋" atau "Halo! 😊"
   - Lanjutkan dengan konfirmasi topik: "Saya akan membantu menjelaskan tentang [topik]."

2. ISI JAWABAN:
   - Langsung to the point, jangan bertele-tele
   - Gunakan bahasa yang mudah dipahami (hindari istilah teknis seperti "database", "chunk", "vector", dll)
   - Struktur dengan bullet points untuk kemudahan baca
   - Gunakan emoji secukupnya (maksimal 2-3 per bagian)

3. FORMAT PENUTUP (HARUS SAMA SETIAP KALI):
   - Sumber: [judul sumber] (jika ada)
   - Tutup dengan: "Semoga membantu! 🙏" atau "Ada yang lain yang ingin ditanyakan? 😊"

4. KETIKA ADA KONTEKS DARI DATABASE:
   ✅ "Berdasarkan dokumentasi BantenPedia..."
   - Sajikan informasi dengan jelas
   - Cantumkan sumber di akhir

5. KETIKA TIDAK ADA KONTEKS DATABASE:
   ✅ "Berdasarkan pengetahuan umum tentang banten Bali..."
   - Jawab tetap informatif
   - Tambahkan: "⚠️ Informasi ini dari pengetahuan umum. Untuk kepastian, konsultasikan dengan pemangku adat."

🟡 LARANGAN:
❌ JANGAN sebutkan: "database", "knowledge repository", "chunk", "vector", "embedding", "similarity"
❌ JANGAN gunakan format teknis seperti "[KONTEKS DARI...]" dalam jawaban ke user
❌ JANGAN berikan multiple opening styles (selalu mulai dengan "Halo!")

🟢 CONTOH RESPONSE YANG BAIK:

User: "Apa itu canang tubungan?"
Assistant: "Halo! 👋 Saya akan membantu menjelaskan tentang Canang Tubungan.

Canang Tubungan adalah jenis banten yang berbentuk persegi panjang dan digunakan dalam berbagai upacara adat Bali. Beberapa ciri utamanya:

• Bentuk: Persegi panjang dengan ukuran bervariasi
• Isi: Biasanya berisi bunga, porosan, dan sesaji lainnya
• Fungsi: Digunakan untuk persembahan dalam upacara keagamaan

Sumber: Dokumentasi Canang Tubungan (Buku)

Semoga membantu! 🙏"

🟢 STRUKTUR RESPONSE UNTUK FRONTEND:
- Opening: selalu "Halo! 👋"
- Body: bullet points dengan emoji secukupnya
- Source: nama sumber (jika ada)
- Closing: "Semoga membantu! 🙏"

PRIORITAS SUMBER:
1. Gunakan konteks dari BantenPedia jika tersedia (utama)
2. Gunakan pengetahuan umum jika tidak ada konteks (dengan label)
3. Jangan menolak menjawab pertanyaan user

INGAT: Kamu adalah asisten yang ramah dan membantu, bukan sistem teknis. Jawab dengan bahasa natural yang mudah dipahami masyarakat umum."""


# Kept for compatibility but no longer used as an early-exit —
# the agent now falls through to Gemini even when the DB has no results.
NO_RESULT_RESPONSE = (
    "Maaf, informasi mengenai hal tersebut belum ditemukan dalam "
    "knowledge repository BantenPedia. Coba ajukan pertanyaan dengan "
    "kata kunci yang berbeda, atau hubungi tim BantenPedia untuk "
    "penambahan sumber."
)

# Injected into the prompt when the DB returned no results so Gemini
# knows to rely on its own knowledge instead of fabricating citations.
NO_DB_CONTEXT_NOTE = (
    "[CATATAN: Tidak ada konteks yang ditemukan di database BantenPedia untuk pertanyaan ini. "
    "Jawab berdasarkan pengetahuanmu sendiri mengenai banten dan budaya Bali. "
    "Tandai jawabanmu dengan label ⚠️ pengetahuan umum.]"
)


# ── Context Construction ──────────────────────────────────────────────────────

def build_context_block(results: list[dict], banten_data: list[dict] | None = None) -> str:
    """
    Construct a formatted context block from RAG retrieval results (PRD §18).

    Args:
        results: List of knowledge search results from search_knowledge().
        banten_data: Optional list of structured banten matches from search_banten().

    Returns:
        A formatted string to inject into the LLM prompt as context.
        Returns NO_DB_CONTEXT_NOTE (empty-DB signal) when both are empty,
        so Gemini falls back to its own knowledge instead of refusing to answer.
    """
    banten_data = banten_data or []
    
    if not results and not banten_data:
        return NO_DB_CONTEXT_NOTE

    blocks = ["[KONTEKS DARI KNOWLEDGE REPOSITORY BANTENPEDIA]\n"]

    # ── Document-based knowledge ──────────────────────────────────────────────
    if results:
        blocks.append("### Dokumentasi Banten")
        for i, result in enumerate(results, start=1):
            source = result.get("source", {})
            title = source.get("title") or "Sumber tidak diketahui"
            source_type = source.get("source_type") or ""
            page = result.get("page_number")
            similarity = result.get("similarity", 0.0)

            header_parts = [f"Sumber {i}: {title}"]
            if source_type:
                header_parts.append(f"[{source_type}]")
            if page:
                header_parts.append(f"Halaman {page}")
            header_parts.append(f"(relevansi: {similarity:.2f})")

            blocks.append("---")
            blocks.append(" | ".join(header_parts))
            blocks.append(result.get("content", ""))

    # ── Structured banten data ────────────────────────────────────────────────
    if banten_data:
        blocks.append("\n### Data Banten Terstruktur")
        for i, banten in enumerate(banten_data, start=1):
            blocks.append("---")
            blocks.append(f"Banten {i}: {banten.get('nama_banten', 'Unknown')}")
            if banten.get('nama_lokal'):
                blocks.append(f"Nama Lokal: {banten['nama_lokal']}")
            if banten.get('deskripsi_umum'):
                blocks.append(f"Deskripsi: {banten['deskripsi_umum']}")
            wilayah = banten.get('wilayah', {})
            if wilayah:
                blocks.append(f"Wilayah: {wilayah.get('kabupaten', 'Unknown')}")

    blocks.append("\n[AKHIR KONTEKS]\n")
    return "\n".join(blocks)


def detect_source_conflict(results: list[dict]) -> bool:
    """
    Check if multiple distinct documents are represented in the results.
    If yes, the agent should surface differences between sources (PRD §22).
    """
    doc_ids = {r.get("document_id") for r in results if r.get("document_id")}
    return len(doc_ids) > 1
