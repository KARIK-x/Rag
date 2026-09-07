from typing import Protocol, List, Dict, Any, Optional
from src.pipeline.models import (
    SourceProvenance,
    Chunk,
    AnalyzedQuery,
    EvidenceSet,
    VerificationResult,
    ExportArtifact
)

class Extractor(Protocol):
    def extract(self, file_path: str, mime_type: str) -> Dict[str, Any]: ...

class Normalizer(Protocol):
    def normalize(self, raw_document: Dict[str, Any]) -> Dict[str, Any]: ...

class Chunker(Protocol):
    def chunk(self, normalized_document: Dict[str, Any]) -> List[Chunk]: ...

class Embedder(Protocol):
    def embed(self, texts: List[str]) -> List[List[float]]: ...

class Retriever(Protocol):
    def retrieve(self, query: AnalyzedQuery, top_k: int) -> List[Dict[str, Any]]: ...

class EvidenceAssembler(Protocol):
    def assemble(self, candidates: List[Dict[str, Any]], query: AnalyzedQuery) -> EvidenceSet: ...

class ComputationEngine(Protocol):
    def execute(self, plan: Dict[str, Any], data_path: str) -> Dict[str, Any]: ...

class Verifier(Protocol):
    def verify(self, draft_answer: str, evidence: EvidenceSet) -> VerificationResult: ...

class Exporter(Protocol):
    def export(self, data: Any, format: str) -> ExportArtifact: ...
