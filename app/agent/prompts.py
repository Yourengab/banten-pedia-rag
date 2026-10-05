"""
System prompt and context construction utilities for the BantenPedia agent.

PRD §18–22 — Grounded generation, source attribution, conflict handling.
"""

# ── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Kamu adalah BantenPedia, asisten AI yang membantu menjawab pertanyaan mengenai banten Bali.

PRINSIP UTAMA:
1. Prioritaskan informasi dari konteks yang diberikan (retrieved context).
2. Jangan membuat fakta budaya tanpa dasar dari sumber.
3. Jangan mengubah makna atau terjemahan istilah lokal Bali secara otomatis.
4. Jika terdapat perbedaan antar sumber, tampilkan perbedaan tersebut secara jelas.
5. Jika informasi tidak tersedia di konteks, katakan bahwa informasi belum ditemukan.
6. Jangan menganggap pengetahuan umum model sebagai fakta budaya lokal.

FORMAT JAWABAN:
- Berikan jawaban yang jelas dan terstruktur.
- Sebutkan sumber informasi (judul dan jenis sumber).
- Jika ada nomor halaman, sebutkan halaman sumbernya.
- Jika ada konflik antar sumber, tampilkan pendapat setiap sumber secara terpisah.

KETERBATASAN:
- Kamu hanya menjawab berdasarkan informasi yang tersedia.
- Kamu bukan penentu kebenaran budaya Bali secara absolut.
- Validasi akhir harus dilakukan oleh ahli budaya atau pemangku adat."""


NO_RESULT_RESPONSE = (
    "Maaf, informasi mengenai hal tersebut belum ditemukan dalam "
    "knowledge repository BantenPedia. Coba ajukan pertanyaan dengan "
    "kata kunci yang berbeda, atau hubungi tim BantenPedia untuk "
    "penambahan sumber."
)


# ── Context Construction ──────────────────────────────────────────────────────

def build_context_block(results: list[dict]) -> str:
    """
    Construct a formatted context block from RAG retrieval results (PRD §18).

    Args:
        results: List of knowledge search results from search_knowledge().

    Returns:
        A formatted string to inject into the LLM prompt as context.
    """
    if not results:
        return ""

    blocks = ["[KONTEKS DARI KNOWLEDGE REPOSITORY BANTENPEDIA]\n"]

    for i, result in enumerate(results, start=1):
        source = result.get("source", {})
        title = source.get("title") or "Sumber tidak diketahui"
        source_type = source.get("source_type") or ""
        page = result.get("page_number")
        similarity = result.get("similarity", 0.0)
        chunk_idx = result.get("chunk_index", "?")

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
