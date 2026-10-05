import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from database.supabase import supabase

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "gemini-embedding-2"
)
EMBEDDING_DIMENSION = int(
    os.getenv("EMBEDDING_DIMENSION", "768")
)

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY belum diatur di .env")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def generate_query_embedding(query: str) -> list[float]:
    """Generate an embedding for a user's search query."""

    response = gemini_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSION
        )
    )

    if not response.embeddings:
        raise ValueError("Gemini tidak menghasilkan embedding.")

    return response.embeddings[0].values


def search_knowledge(
    query: str,
    top_k: int = 5
) -> list[dict]:
    """Search relevant knowledge chunks using vector similarity."""

    if not query or not query.strip():
        return []

    top_k = max(1, min(top_k, 20))

    # Convert the question into a vector.
    embedding = generate_query_embedding(query.strip())

    # Search matching chunks through the Supabase RPC function.
    response = supabase.rpc(
        "match_document_chunks",
        {
            "query_embedding": embedding,
            "match_count": top_k
        }
    ).execute()

    chunks = response.data or []

    if not chunks:
        return []

    # Retrieve document metadata for the matched chunks.
    document_ids = list({
        chunk["document_id"]
        for chunk in chunks
        if chunk.get("document_id")
    })

    documents_by_id = {}

    if document_ids:
        documents_response = (
            supabase
            .table("documents")
            .select("id, title, source_type, file_url, description")
            .in_("id", document_ids)
            .execute()
        )

        documents_by_id = {
            document["id"]: document
            for document in documents_response.data
        }

    results = []

    for chunk in chunks:
        document = documents_by_id.get(
            chunk.get("document_id"), {}
        )

        results.append({
            "content": chunk.get("content"),
            "chunk_index": chunk.get("chunk_index"),
            "similarity": chunk.get("similarity"),
            "document_id": chunk.get("document_id"),
            "source": {
                "title": document.get("title"),
                "source_type": document.get("source_type"),
                "file_url": document.get("file_url"),
                "description": document.get("description")
            }
        })

    return results