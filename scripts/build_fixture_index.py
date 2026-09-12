#!/usr/bin/env python3
"""Build fixture index from the 21 extracted documents using production code.

Execution:
  python3 scripts/build_fixture_index.py

Behavior (idempotent):
  1. For each .json in data/extracted/:
       a) Read as a dictionary (ExtractionResult.to_dict format).
       b) Convert to ExtractionResult via ExtractionResult.from_dict().
       c) Run StructuralChunker.chunk() on ExtractionResult.
       d) Normalize via Normalizer.normalize() on ExtractionResult.to_dict().
       e) Persist chunks to data/chunks/<chunk_id>.json.
       f) Persist normalized to data/normalized/<doc_id>.normalized.json.
       g) For each chunk, add to ExactEntityIndex, BM25Index, DenseVectorIndex.
       h) Use EmbeddingCache.lookup/store for dense embeddings.
  2. Indexes persist to data/indexes/*.db (managed by their classes).
  3. Write summary JSON with counts at data/index_artifacts.json.

All uses existing production code — no re-implementations.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, DefaultDict
from collections import defaultdict
from datetime import date, datetime

from src.extraction.router import ExtractionResult
from src.normalization.text import Normalizer
from src.chunking.structural import StructuralChunker
from src.indexing.vector import (
    ExactEntityIndex,
    BM25Index,
    DenseVectorIndex,
    SearchQuery,
)
from src.cache.query_cache import EmbeddingCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_ROOT = Path("data")
EXTRACTED_DIR = DATA_ROOT / "extracted"
CHUNKS_DIR = DATA_ROOT / "chunks"
NORMALIZED_DIR = DATA_ROOT / "normalized"
INDEXES_DIR = DATA_ROOT / "indexes"

CHUNKS_DIR.mkdir(exist_ok=True)
NORMALIZED_DIR.mkdir(exist_ok=True)
INDEXES_DIR.mkdir(exist_ok=True)

# Initialize production components (they manage their own DB persistence)
EXACT_INDEX = ExactEntityIndex(db_path=str(INDEXES_DIR / "exact.db"))
BM25_INDEX = BM25Index(db_path=str(INDEXES_DIR / "bm25.db"))
DENSE_INDEX = DenseVectorIndex(dim=384, db_path=str(INDEXES_DIR / "dense.db"))
EMBEDDER = EmbeddingCache()
CHUNKER = StructuralChunker(target_size=600, hard_cap=1200, min_size=100, overlap=100)
NORMALIZER = Normalizer()

# Global cache for embeddings (EmbeddingCache already does lookup/store)
# Track counts for validation
embed_calls = defaultdict(int)

# Real sentence-transformers available (ST 6.0.1 installed). Use real embeddings.
# ponytail: uses all-MiniLM-L6-v2 (384 dim); swap model name if you want a different ST model.
from sentence_transformers import SentenceTransformer
_real_model = None

def _load_model():
    global _real_model
    if _real_model is None:
        _real_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _real_model

def get_embedding(text: str) -> List[float]:
    model = _load_model()
    emb = model.encode(text, convert_to_numpy=True).tolist()
    embed_calls[text] = embed_calls.get(text, 0) + 1
    return emb


def process_extracted_json(file_path: Path) -> int:
    """Run the full pipeline on a single extracted JSON, return chunk count."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    doc_id = data.get("doc_id")
    if not doc_id:
        logger.warning(f"Skipping {file_path.name} – no doc_id")
        return 0

    # Convert dict to ExtractionResult (ExtractionResult is a dataclass with from_dict/to_dict)
    extraction_result = ExtractionResult.from_dict(data)

    # Step 1: Normalize using Normalizer.normalize on ExtractionResult.to_dict()
    normalized = NORMALIZER.normalize(extraction_result.to_dict())

    # Persist normalized document with JSON-safe serialization (Normalizer produces date objects)
    def _json_default(o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")
    norm_path = NORMALIZED_DIR / f"{doc_id}.normalized.json"
    with open(norm_path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2, default=_json_default)
    logger.info(f"Normalized document saved: {norm_path}")

    # Step 2: Chunk using StructuralChunker.chunk() on ExtractionResult
    chunks = CHUNKER.chunk(extraction_result)

    # Persist chunks
    for chunk in chunks:
        chunk_path = CHUNKS_DIR / f"{chunk.chunk_id}.json"
        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(chunk.to_dict(), f, ensure_ascii=False, indent=2)

    # Step 3: Add each chunk to indexes
    for chunk in chunks:
        metadata = {
            "doc_id": chunk.doc_id,
            "source_locator": chunk.source_locator,
            "chunk_type": chunk.chunk_type,
            "metadata": chunk.metadata,
        }
        # Exact index
        EXACT_INDEX.add(chunk.chunk_id, chunk.raw_text, metadata)
        # BM25 index
        BM25_INDEX.add(chunk.chunk_id, chunk.raw_text, metadata)
        # Dense index - get embedding and add with it
        embedding = get_embedding(chunk.raw_text)
        dense_metadata = {**metadata, "embedding": embedding}
        DENSE_INDEX.add(chunk.chunk_id, chunk.raw_text, dense_metadata)

    logger.info(f"Processed {doc_id}: {len(chunks)} chunks")
    return len(chunks)


def main() -> None:
    logger.info("Starting fixture index build from 21 extracted documents...")
    json_files = sorted(EXTRACTED_DIR.glob("*.json"))
    logger.info(f"Found {len(json_files)} extracted JSONs")

    total_chunks = 0
    for file_path in json_files:
        total_chunks += process_extracted_json(file_path)

    # Write summary artifact
    summary = {
        "exact_count": len(EXACT_INDEX._index),
        "bm25_count": len(BM25_INDEX.doc_ids) if hasattr(BM25_INDEX, "doc_ids") else "N/A",
        "dense_count": len(DENSE_INDEX.embeddings) if hasattr(DENSE_INDEX, "embeddings") else "N/A",
        "chunk_files": len(list(CHUNKS_DIR.glob("*.json"))),
        "normalized_files": len(list(NORMALIZED_DIR.glob("*.json"))),
        "embedded_texts": len(embed_calls),
        "total_chunks_processed": total_chunks,
    }
    summary_path = DATA_ROOT / "index_artifacts.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"Index build complete. Summary written to {summary_path}")

    # Output counts for validation
    print("\n[RESULT]")
    print(f"exact_count: {summary['exact_count']}")
    print(f"bm25_count: {summary['bm25_count']}")
    print(f"dense_count: {summary['dense_count']}")
    print(f"chunk_files: {summary['chunk_files']}")
    print(f"normalized_files: {summary['normalized_files']}")
    print(f"embedded_texts: {summary['embedded_texts']}")
    print(f"total_chunks_processed: {summary['total_chunks_processed']}")
    print(f"artifact_paths: {list(CHUNKS_DIR.glob('*.json'))[:5]}...")


if __name__ == "__main__":
    main()
