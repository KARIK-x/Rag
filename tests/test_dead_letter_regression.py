"""Regression: DEAD_LETTER must never silently become INDEXED (state != indexed -> can_index False)."""
from src.indexing.index_contract import IndexContract

def test_dead_letter_never_indexed():
    # Current contract: 11 fields (doc_id, state, has_normalized, has_chunks, chunk_ids,
    # has_embeddings, has_dense, has_bm25, has_exact, provenance_intact, consistent)
    dead = IndexContract(
        doc_id="dead_001",
        state="dead_letter",
        has_normalized=True,
        has_chunks=True,
        chunk_ids=["c1"],
        has_embeddings=True,
        has_dense=True,
        has_bm25=True,
        has_exact=True,
        provenance_intact=True,
        consistent=True,
    )
    assert dead.state == "dead_letter"
    assert dead.can_index() is False  # state != "indexed" => guard rejects
