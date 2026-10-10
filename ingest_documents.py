#!/usr/bin/env python3
"""
Batch document ingestion script for BantenPedia.

Ingests all PDF files from data/documents/ into Supabase.

Usage:
    # Test with single PDF
    python ingest_documents.py --test

    # Process all PDFs
    python ingest_documents.py

    # Process specific files
    python ingest_documents.py --files "06_Canang_Tubungan.pdf" "04_Canang_Gantal.pdf"

Requirements:
    - .env configured with SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY
    - sql/schema.sql executed in Supabase
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Optional

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "app"))

from config import validate_config
from ingestion.pipeline import ingest_file
from ingestion.embedder import embed_query
from database.supabase import supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Directory containing PDF documents
DOCUMENTS_DIR = Path(__file__).parent / "data" / "documents"


def extract_title_from_filename(filename: str) -> str:
    """
    Extract readable title from filename.
    Pattern: "06_Canang_Tubungan.pdf" -> "Canang Tubungan"
    """
    # Remove extension
    name = Path(filename).stem
    
    # Remove leading numbers and underscores (e.g., "06_", "033_")
    name = re.sub(r"^\d+_", "", name)
    
    # Replace underscores with spaces
    name = name.replace("_", " ")
    
    return name


def extract_banten_name(filename: str) -> Optional[str]:
    """
    Try to extract banten name if this appears to be a banten-specific document.
    Returns None if uncertain.
    """
    title = extract_title_from_filename(filename).lower()
    
    # Common banten-related keywords that indicate a banten-specific doc
    banten_keywords = [
        "canang", "banten", "segehan", "ayaban", "pejati", "caru",
        "sampian", "tamas", "daksina", "suci", "gesingan"
    ]
    
    # Check if title starts with or contains banten name
    for keyword in banten_keywords:
        if title.startswith(keyword) or f" {keyword}" in title:
            # Capitalize first letter of each word
            return " ".join(word.capitalize() for word in title.split()[:3])
    
    return None


def get_existing_document(title: str) -> Optional[dict]:
    """Check if document already exists and is active."""
    try:
        result = (
            supabase
            .table("documents")
            .select("id, title")
            .eq("title", title)
            .eq("is_active", True)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning(f"Could not check existing document: {e}")
        return None


def verify_ingestion(document_id: str, test_query: str = "canang") -> bool:
    """
    Verify ingestion by testing vector search.
    Returns True if search returns results.
    """
    try:
        # Generate embedding for test query
        query_embedding = embed_query(test_query)
        
        # Call match_document_chunks RPC
        result = supabase.rpc(
            "match_document_chunks",
            {
                "query_embedding": query_embedding,
                "match_count": 3,
                "similarity_threshold": 0.5,
            }
        ).execute()
        
        if result.data:
            # Check if any result is from our document
            for chunk in result.data:
                if chunk.get("document_id") == document_id:
                    logger.info(
                        f"✓ Verification passed: found chunk from document "
                        f"(similarity: {chunk.get('similarity', 0):.3f})"
                    )
                    return True
            
            logger.info(f"✓ Search works but no chunks from this document yet")
            return True
        else:
            logger.warning("✗ No search results found")
            return False
            
    except Exception as e:
        logger.error(f"✗ Verification failed: {e}")
        return False


def process_pdf(
    pdf_path: Path,
    skip_existing: bool = True,
) -> tuple[bool, str]:
    """
    Process a single PDF file.
    
    Returns:
        (success, message)
    """
    title = extract_title_from_filename(pdf_path.name)
    
    # Check for existing document
    if skip_existing:
        existing = get_existing_document(title)
        if existing:
            return True, f"Skipped (exists: {existing['id']})"
    
    # Determine source_type based on filename
    source_type = "book"  # Default
    if "cara" in title.lower() or "tata" in title.lower():
        source_type = "guide"
    elif "bagan" in title.lower():
        source_type = "reference"
    
    # Build description
    banten_name = extract_banten_name(pdf_path.name)
    description = f"Dokumentasi {banten_name}" if banten_name else None
    
    logger.info(f"Processing: {pdf_path.name}")
    logger.info(f"  Title: {title}")
    logger.info(f"  Type: {source_type}")
    if banten_name:
        logger.info(f"  Banten: {banten_name}")
    
    try:
        result = ingest_file(
            path=pdf_path,
            title=title,
            source_type=source_type,
            description=description,
        )
        
        return True, f"Success: {result.chunks_inserted} chunks, doc_id={result.document_id[:8]}..."
        
    except ValueError as e:
        return False, f"Extraction error: {e}"
    except Exception as e:
        return False, f"Failed: {e}"


def main():
    parser = argparse.ArgumentParser(
        description="Ingest PDF documents into BantenPedia"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test with first PDF only",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Process specific files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process even if document exists",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify ingestion with test query",
    )
    
    args = parser.parse_args()
    
    # Validate configuration
    try:
        validate_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please copy .env.example to .env and fill in credentials")
        sys.exit(1)
    
    # Collect PDF files to process
    if args.files:
        pdf_files = [DOCUMENTS_DIR / f for f in args.files]
    elif args.test:
        # Get first PDF for testing
        pdf_files = list(DOCUMENTS_DIR.glob("*.pdf"))[:1]
        if not pdf_files:
            logger.error("No PDF files found in data/documents/")
            sys.exit(1)
    else:
        pdf_files = sorted(DOCUMENTS_DIR.glob("*.pdf"))
    
    if not pdf_files:
        logger.error("No PDF files to process")
        sys.exit(1)
    
    logger.info(f"Found {len(pdf_files)} PDF file(s) to process")
    logger.info("=" * 60)
    
    # Process each file
    results = {
        "success": 0,
        "skipped": 0,
        "failed": 0,
        "total_chunks": 0,
    }
    
    test_document_id = None
    
    for pdf_path in pdf_files:
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            results["failed"] += 1
            continue
        
        success, message = process_pdf(
            pdf_path,
            skip_existing=not args.force,
        )
        
        if success:
            if "Skipped" in message:
                results["skipped"] += 1
                logger.info(f"  ⊘ {message}")
            else:
                results["success"] += 1
                # Extract chunk count from message
                import re
                match = re.search(r"(\d+) chunks", message)
                if match:
                    results["total_chunks"] += int(match.group(1))
                
                # Store first document ID for verification
                if test_document_id is None and "doc_id=" in message:
                    match = re.search(r"doc_id=([a-f0-9]+)", message)
                    if match:
                        test_document_id = match.group(1)
                
                logger.info(f"  ✓ {message}")
        else:
            results["failed"] += 1
            logger.error(f"  ✗ {message}")
    
    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info(f"  Processed: {results['success']} documents")
    logger.info(f"  Skipped:   {results['skipped']} documents (already exist)")
    logger.info(f"  Failed:    {results['failed']} documents")
    logger.info(f"  Total chunks inserted: {results['total_chunks']}")
    
    # Verification
    if args.verify and test_document_id:
        logger.info("=" * 60)
        logger.info("VERIFICATION")
        verify_ingestion(test_document_id)
    
    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
