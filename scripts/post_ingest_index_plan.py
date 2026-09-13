"""Post-ingest indexing plan — READ-ONLY, no embedding execution."""
# Plan for full indexing pipeline after ingestion completes.
# Read-only: references only, does NOT write indexes, embed, or modify DB.

CHUNK_STORE = "data/chunks/"
STATE_DB = "data/db/rag_state.db"
INDEX_DENSE = "data/indexes/dense.db"
INDEX_BM25 = "data/indexes/bm25.db"
INDEX_EXACT = "data/indexes/exact.db"
EMBED_DIM = 768  # DenseVectorIndex default

# BM25 fix verified (line 367, src/indexing/vector.py): load_state inversion corrected.
# Protected path: /Users/ashim/locus_drive — never modified by this pipeline.
# No commit / no push.

PIPELINE_STEPS = [
    "1) verify chunk schema",
    "2) generate embeddings (batch, skip existing)",
    "3) dense index add (INSERT OR REPLACE)",
    "4) BM25 rebuild (clear + add with correct load_state)",
    "5) exact index rebuild",
    "6) metadata index load",
    "7) consistency validation (compare chunk IDs vs DB)",
    "8) retrieval smoke tests (HybridRetriever from src/indexing/vector.py)",
]

if __name__ == "__main__":
    import os
    assert os.path.isfile(__file__), "plan file missing"
    count = len([n for n in os.listdir(CHUNK_STORE) if os.path.isfile(os.path.join(CHUNK_STORE, n))])
    assert count > 0, f"chunk store empty: {count} files"
    print("Plan verified (read-only); chunk count:", count)
