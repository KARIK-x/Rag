
"""INDEXED invariant — enforced before transition."""
from dataclasses import dataclass
from typing import Optional, List, Dict

@dataclass
class IndexContract:
    doc_id: str
    state: str  # must == "indexed"
    has_normalized: bool
    has_chunks: bool
    chunk_ids: List[str]
    has_embeddings: bool
    has_dense: bool
    has_bm25: bool
    has_exact: bool
    provenance_intact: bool
    consistent: bool  # all required true && provenance present

    def can_index(self) -> bool:
        return (self.state == "indexed" and
                self.has_normalized and self.has_chunks and len(self.chunk_ids) > 0 and
                self.has_embeddings and self.has_dense and self.has_bm25 and self.has_exact and
                self.provenance_intact and self.consistent)
