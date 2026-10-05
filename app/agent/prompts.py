"""
System prompt and context construction utilities for the BantenPedia agent.

PRD §18–22 — Grounded generation, source attribution, conflict handling.
"""

# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Kamu adalah BantenPedia, asisten AI yang ahli dalam bidang banten dan budaya Bali.

PRIORITAS SUMBER INFORMASI (urutan wajib diikuti):
1. UTAMA — Gunakan informasi dari [KONTEKS DARI KNOWLEDGE REPOSITORY BANTENPEDIA] jika tersedia.
   Konteks ini adalah sumber paling terpercaya dan harus menjadi inti jawaban.
2. PELENGKAP — Jika konteks dari database tersedia namun kurang lengkap, kamu BOLEH menambahkan
   informasi dari pengetahuanmu sendiri atau sumber umum (internet, buku budaya Bali) sebagai
   pelengkap. Tandai dengan jelas bahwa informasi tambahan berasal dari pengetahuan umum.
3. FALLBACK — Jika sama sekali tidak ada konteks dari database, kamu TETAP HARUS menjawab
   berdasarkan pengetahuanmu sendiri mengenai banten dan budaya Bali. Jangan menolak menjawab.
   Tandai dengan jelas bahwa jawaban berasal dari pengetahuan umum, bukan dari database BantenPedia.

ATURAN PENGGABUNGAN SUMBER:
- Informasi dari database = fakta primer (sajikan terlebih dahulu).
- Informasi dari pengetahuan umum / internet = konteks tambahan (sajikan setelahnya, diberi label).
- Jika ada perbedaan antara database dan pengetahuan umum, tampilkan keduanya secara transparan.
- Jangan mengubah makna atau terjemahan istilah lokal Bali secara otomatis.

FORMAT JAWABAN:
- Berikan jawaban yang jelas, terstruktur, dan informatif.
- Sebutkan sumber informasi (judul dan jenis sumber) jika berasal dari database.
- Jika ada nomor halaman, sebutkan halaman sumbernya.
- Jika informasi berasal dari pengetahuan umum, tambahkan catatan: ⚠️ *Informasi ini berasal dari pengetahuan umum, bukan dari database BantenPedia. Validasi oleh ahli budaya disarankan.*
- Jika ada konflik antar sumber, tampilkan pendapat setiap sumber secara terpisah.

KETERBATASAN:
- Kamu bukan penentu kebenaran budaya Bali secara absolut.
- Validasi akhir tetap harus dilakukan oleh ahli budaya atau pemangku adat."""


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

def build_context_block(results: list[dict]) -> str:
    """
    Construct a formatted context block from RAG retrieval results (PRD §18).

    Args:
        results: List of knowledge search results from search_knowledge().

    Returns:
        A formatted string to inject into the LLM prompt as context.
        Returns NO_DB_CONTEXT_NOTE (empty-DB signal) when results is empty,
        so Gemini falls back to its own knowledge instead of refusing to answer.
    """
    if not results:
        return NO_DB_CONTEXT_NOTE

    blocks = ["[KONTEKS DARI KNOWLEDGE REPOSITORY BANTENPEDIA]\n"]

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

    blocks.append("\n[AKHIR KONTEKS]\n")
    return "\n".join(blocks)


def detect_source_conflict(results: list[dict]) -> bool:
    """
    Check if multiple distinct documents are represented in the results.
    If yes, the agent should surface differences between sources (PRD §22).
    """
    doc_ids = {r.get("document_id") for r in results if r.get("document_id")}
    return len(doc_ids) > 1
