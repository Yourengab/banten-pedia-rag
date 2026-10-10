#!/usr/bin/env python3
import sys
sys.path.insert(0, 'app')
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from ingestion.pipeline import ingest_file
from pathlib import Path

result = ingest_file(
    path=Path('data/documents/029_Sesana_Ethika_Membuat_Upakara.pdf'),
    title='Sesana Ethika Membuat Upakara',
    source_type='book',
    description='Dokumentasi etika membuat upakara',
)
print(f'Success: {result.chunks_inserted} chunks, doc_id={result.document_id}')