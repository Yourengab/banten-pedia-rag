-- ============================================================
-- BantenPedia RAG Schema
-- Run this in Supabase SQL Editor
-- ============================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Table: documents
-- Stores metadata of source documents.
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title         TEXT        NOT NULL,
    source_type   TEXT        NOT NULL,     -- 'book', 'article', 'transcript', etc.
    file_url      TEXT,
    description   TEXT,
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Table: document_chunks
-- Stores text chunks and vector embeddings.
-- ============================================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content       TEXT        NOT NULL,
    chunk_index   INTEGER     NOT NULL,
    -- Page-level citation (Phase 2)
    page_number   INTEGER,
    -- Vector embedding (768 dims for Gemini Embedding 2)
    embedding     VECTOR(768) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast similarity search
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
    ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Index for fast document lookup
CREATE INDEX IF NOT EXISTS document_chunks_document_id_idx
    ON document_chunks (document_id);

-- ============================================================
-- RPC: match_document_chunks
-- Basic vector similarity search (cosine distance).
-- Called by search_knowledge().
-- ============================================================
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding      VECTOR(768),
    match_count          INTEGER DEFAULT 5,
    similarity_threshold FLOAT   DEFAULT 0.60
)
RETURNS TABLE (
    id          UUID,
    document_id UUID,
    content     TEXT,
    chunk_index INTEGER,
    page_number INTEGER,
    similarity  FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.document_id,
        dc.content,
        dc.chunk_index,
        dc.page_number,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    WHERE
        d.is_active = TRUE
        AND 1 - (dc.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================
-- RPC: match_document_chunks_filtered
-- Vector search with metadata filter support.
-- Supports source_type filter; reserved for hybrid/Phase 2.
-- ============================================================
CREATE OR REPLACE FUNCTION match_document_chunks_filtered(
    query_embedding      VECTOR(768),
    match_count          INTEGER DEFAULT 5,
    similarity_threshold FLOAT   DEFAULT 0.60,
    filter_source_type   TEXT    DEFAULT NULL
)
RETURNS TABLE (
    id          UUID,
    document_id UUID,
    content     TEXT,
    chunk_index INTEGER,
    page_number INTEGER,
    similarity  FLOAT,
    source_type TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.document_id,
        dc.content,
        dc.chunk_index,
        dc.page_number,
        1 - (dc.embedding <=> query_embedding) AS similarity,
        d.source_type
    FROM document_chunks dc
    JOIN documents d ON d.id = dc.document_id
    WHERE
        d.is_active = TRUE
        AND 1 - (dc.embedding <=> query_embedding) >= similarity_threshold
        AND (filter_source_type IS NULL OR d.source_type = filter_source_type)
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;


