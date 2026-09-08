from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Protocol
from enum import Enum

class DocType(Enum):
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    TXT = "txt"
    MD = "md"
    SPREADSHEET = "spreadsheet"
    CSV = "csv"
    GSHEET = "gsheet"
    GDOC = "gdoc"
    OTHER = "other"

class ProcessingState(Enum):
    DISCOVERED = "discovered"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    EXTRACTED = "extracted"
    NORMALIZED = "normalized"
    CLASSIFIED = "classified"
    DEDUPLICATED = "deduplicated"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    INDEXED = "indexed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"

@dataclass
class SourceProvenance:
    drive_file_id: str
    filename: str
    folder_path: str
    mime_type: str
    revision_id: Optional[str] = None
    page: Optional[int] = None
    section: Optional[str] = None
    heading_path: List[str] = field(default_factory=list)
    table_id: Optional[str] = None
    sheet_name: Optional[str] = None
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    col_start: Optional[int] = None
    col_end: Optional[int] = None
    cell: Optional[str] = None
    chunk_id: Optional[str] = None
    source_view_link: Optional[str] = None

@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    parent_chunk_id: Optional[str]
    heading_path: List[str]
    page_start: Optional[int]
    page_end: Optional[int]
    sheet_name: Optional[str]
    row_start: Optional[int]
    row_end: Optional[int]
    raw_text: str
    normalized_text: str
    contextual_prefix: Optional[str]
    provenance: SourceProvenance

@dataclass
class AnalyzedQuery:
    raw_query: str
    normalized_query: str
    intents: List[str]
    filters: Dict[str, Any]
    temporal_constraints: Dict[str, Any]
    decomposed_subqueries: List[str]
    requires_computation: bool
    requires_export: bool
    export_format: Optional[str]

@dataclass
class EvidenceItem:
    chunk_id: str
    doc_id: str
    score: float
    text: str
    provenance: SourceProvenance
    authority_score: float

@dataclass
class EvidenceSet:
    query: str
    items: List[EvidenceItem]
    is_sufficient: bool
    missing_aspects: List[str]
    conflicts_detected: bool
    conflict_notes: Optional[str] = None

@dataclass
class VerificationResult:
    is_faithful: bool
    unsupported_claims: List[str]
    contradictions: List[str]
    numeric_checks_passed: bool
    completeness_score: float
    confidence_level: str  # HIGH, MEDIUM, LOW, ABSTAIN
    reasoning: str

@dataclass
class ExportArtifact:
    format: str
    content: bytes
    filename: str
    mime_type: str
    provenance_summary: List[Dict[str, Any]]
