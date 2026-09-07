"""
LOCUS RAG Baseline Retrieval Pipeline

Simplest viable pipeline for Phase 1:
1. Format routing
2. Simple heading-aware chunking
3. Single embedding model (placeholder)
4. Dense retrieval + simple top-k

This establishes the baseline metrics before adding complexity.
"""

import sqlite3
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from enum import Enum

from src.pipeline.models import Chunk, DocType, SourceProvenance


class BaselineState(Enum):
    """Simplified document processing state for baseline."""
    DISCOVERED = "discovered"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    INDEXED = "indexed"
    FAILED = "failed"


@dataclass
class BaselineChunk:
    """Simplified chunk for baseline retrieval."""
    chunk_id: str
    doc_id: str
    raw_text: str
    normalized_text: str
    heading_path: str  # JSON string for simplicity
    page_start: Optional[int]
    drive_file_id: str
    source_locator: str  # JSON string


class BaselinePipeline:
    """
    Simplest viable retrieval pipeline.

    - Reads from existing locus_drive catalog (READ-ONLY)
    - Chunks documents with heading awareness
    - Embeds with a single model
    - Retrieves with dense vectors + top-k
    """

    def __init__(
        self,
        catalog_path: str = "/Users/ashim/locus_drive/locus_drive.db",
        data_dir: str = "/Users/ashim/locus_rag/data",
    ):
        self.catalog_path = catalog_path
        self.data_dir = Path(data_dir)
        self.chunks_dir = self.data_dir / "chunks"
        self.db_path = self.data_dir / "db" / "baseline.db"

        # Ensure directories exist
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize baseline database
        self._init_baseline_db()

    def _init_baseline_db(self):
        """Initialize the baseline state database."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS baseline_documents (
                doc_id TEXT PRIMARY KEY,
                drive_file_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                processing_state TEXT NOT NULL,
                content_hash TEXT,
                chunk_count INTEGER DEFAULT 0,
                last_updated TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS baseline_chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                heading_path TEXT,
                page_start INTEGER,
                drive_file_id TEXT NOT NULL,
                source_locator TEXT NOT NULL,
                embedding_model TEXT,
                FOREIGN KEY (doc_id) REFERENCES baseline_documents(doc_id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_doc_id
            ON baseline_chunks(doc_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_normalized
            ON baseline_chunks(normalized_text)
        """)

        conn.commit()
        conn.close()

    def _connect(self):
        """Get connection to baseline database."""
        return sqlite3.connect(str(self.db_path))

    def get_catalog_stats(self) -> Dict[str, Any]:
        """Get statistics from the existing Drive catalog."""
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()

        # Total files
        cursor.execute("SELECT COUNT(*) FROM files WHERE trashed = 0")
        total_files = cursor.fetchone()[0]

        # By mime type
        cursor.execute("""
            SELECT mime_type, COUNT(*) as count
            FROM files
            WHERE trashed = 0
            GROUP BY mime_type
            ORDER BY count DESC
        """)
        mime_types = cursor.fetchall()

        # Folders processed
        cursor.execute("SELECT COUNT(*) FROM folder_queue WHERE status = 'done'")
        folders_done = cursor.fetchone()[0]

        conn.close()

        return {
            "total_files": total_files,
            "mime_types": dict(mime_types),
            "folders_processed": folders_done,
        }

    def discover_documents(self, doc_types: List[str] = None) -> List[Dict]:
        """
        Discover documents from the existing catalog.

        Args:
            doc_types: List of mime types to include (None = all text-processable)

        Returns:
            List of document metadata dicts
        """
        if doc_types is None:
            # Focus on processable document types
            doc_types = [
                'application/pdf',
                'application/vnd.google-apps.document',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain',
                'text/markdown',
                'application/vnd.google-apps.spreadsheet',
                'text/csv',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            ]

        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id, name, mime_type, path, size,
                created_time, modified_time,
                web_view_link, parents
            FROM files
            WHERE trashed = 0
            AND mime_type IN ({seq})
            ORDER BY modified_time DESC
        """.format(seq=','.join('?' * len(doc_types))), doc_types)

        columns = [
            'drive_file_id', 'filename', 'mime_type', 'folder_path', 'size',
            'created_time', 'modified_time', 'web_view_link', 'parents'
        ]

        documents = []
        for row in cursor.fetchall():
            doc = dict(zip(columns, row))
            doc['parents'] = json.loads(doc['parents']) if doc['parents'] else []
            documents.append(doc)

        conn.close()
        return documents

    def simple_chunk_text(
        self,
        text: str,
        doc_id: str,
        drive_file_id: str,
        max_chunk_size: int = 500,
        overlap: int = 50,
    ) -> List[BaselineChunk]:
        """
        Simple text chunking with basic heading awareness.

        Splits on:
        - Double newlines (paragraphs)
        - Single newlines in short lines (potential headings)
        - Character count limit
        """
        chunks = []

        # Split on paragraph boundaries
        paragraphs = text.split('\n\n')

        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Detect potential heading (short line ending with colon or all caps)
            is_heading = (
                len(para) < 100 and
                '\n' not in para and
                (para.endswith(':') or para.isupper())
            )

            para_size = len(para)

            # If adding this paragraph exceeds limit and we have content
            if current_size + para_size > max_chunk_size and current_chunk:
                # Join current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunk_id = self._make_chunk_id(doc_id, chunk_text)

                chunks.append(BaselineChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    raw_text=chunk_text,
                    normalized_text=self._normalize_text(chunk_text),
                    heading_path="[]",
                    page_start=None,
                    drive_file_id=drive_file_id,
                    source_locator=json.dumps({
                        "drive_file_id": drive_file_id,
                        "doc_id": doc_id,
                    }),
                ))

                # Start new chunk with overlap
                overlap_texts = current_chunk[-1:] if overlap > 0 else []
                current_chunk = overlap_texts + [para]
                current_size = sum(len(t) for t in current_chunk)
            else:
                current_chunk.append(para)
                current_size += para_size

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunk_id = self._make_chunk_id(doc_id, chunk_text)
            chunks.append(BaselineChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                raw_text=chunk_text,
                normalized_text=self._normalize_text(chunk_text),
                heading_path="[]",
                page_start=None,
                drive_file_id=drive_file_id,
                source_locator=json.dumps({
                    "drive_file_id": drive_file_id,
                    "doc_id": doc_id,
                }),
            ))

        return chunks

    def _make_chunk_id(self, doc_id: str, text: str) -> str:
        """Generate deterministic chunk ID."""
        content = f"{doc_id}:{text[:200]}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _normalize_text(self, text: str) -> str:
        """
        Simple text normalization.

        Preserves meaning while standardizing format.
        """
        import unicodedata

        # Unicode normalization
        text = unicodedata.normalize('NFKC', text)

        # Collapse whitespace
        import re
        text = re.sub(r'\s+', ' ', text)

        # Lowercase for retrieval (case-insensitive by default)
        text = text.lower()

        return text.strip()

    def store_chunks(self, chunks: List[BaselineChunk]) -> int:
        """Store chunks in baseline database."""
        conn = self._connect()
        cursor = conn.cursor()

        count = 0
        for chunk in chunks:
            cursor.execute("""
                INSERT OR REPLACE INTO baseline_chunks
                (chunk_id, doc_id, raw_text, normalized_text, heading_path,
                 page_start, drive_file_id, source_locator)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk.chunk_id,
                chunk.doc_id,
                chunk.raw_text,
                chunk.normalized_text,
                chunk.heading_path,
                chunk.page_start,
                chunk.drive_file_id,
                chunk.source_locator,
            ))
            count += 1

        conn.commit()
        conn.close()
        return count

    def get_chunk_count(self) -> int:
        """Get total chunk count in baseline index."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM baseline_chunks")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def search_chunks(
        self,
        query: str,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Simple search: normalize query and find matching chunks.

        Baseline uses simple text matching (no embeddings yet).
        This is intentionally naive to establish a true baseline.
        """
        normalized_query = self._normalize_text(query)

        conn = self._connect()
        cursor = conn.cursor()

        # Simple keyword matching as baseline
        # Split query into words and search for chunks containing all words
        words = normalized_query.split()

        if not words:
            return []

        # Build LIKE pattern for each word
        patterns = [f"%{word}%" for word in words]

        # Search in normalized text
        placeholders = ' AND '.join(['normalized_text LIKE ?' for _ in patterns])
        query_sql = f"""
            SELECT
                chunk_id, doc_id, raw_text, drive_file_id,
                LENGTH(raw_text) as text_length
            FROM baseline_chunks
            WHERE {placeholders}
            ORDER BY text_length ASC
            LIMIT ?
        """

        cursor.execute(query_sql, patterns + [top_k])
        rows = cursor.fetchall()

        results = []
        for i, row in enumerate(rows):
            # Simple scoring: shorter texts that match are better
            score = 1.0 / (1 + i * 0.1)  # Decreasing score by rank

            results.append({
                "chunk_id": row[0],
                "doc_id": row[1],
                "text": row[2],
                "drive_file_id": row[3],
                "score": score,
                "rank": i + 1,
            })

        conn.close()
        return results


def run_baseline_evaluation():
    """
    Run baseline evaluation on seed benchmark.

    Measures:
    - Candidate pool size
    - Retrieval latency
    - Simple match rate
    """
    import time

    pipeline = BaselinePipeline()

    # Get catalog stats
    stats = pipeline.get_catalog_stats()
    print(f"\n{'='*60}")
    print(f"LOCUS RAG Baseline Evaluation")
    print(f"{'='*60}")
    print(f"\nCatalog Stats:")
    print(f"  Total files: {stats['total_files']}")
    print(f"  Folders processed: {stats['folders_processed']}")
    print(f"\nProcessable document types:")
    for mime, count in list(stats['mime_types'].items())[:10]:
        print(f"  {mime}: {count}")

    # Load seed benchmark
    benchmark_path = Path(__file__).parent.parent.parent / "eval" / "benchmark" / "seed_cases.json"
    if benchmark_path.exists():
        with open(benchmark_path) as f:
            cases = json.load(f)

        print(f"\n{'='*60}")
        print(f"Baseline Retrieval Results")
        print(f"{'='*60}")

        total_recall = 0
        total_cases = 0
        latencies = []

        for case in cases[:10]:  # First 10 cases
            query = case['question']
            start = time.time()
            results = pipeline.search_chunks(query, top_k=20)
            latency = time.time() - start
            latencies.append(latency)

            # Simple evaluation: did we get any results?
            has_results = len(results) > 0

            print(f"\nCase {case['case_id']}: {case['category']}")
            print(f"  Query: {query[:60]}...")
            print(f"  Results: {len(results)}")
            print(f"  Latency: {latency*1000:.1f}ms")

            if has_results:
                total_recall += 1

            total_cases += 1

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        print(f"\n{'='*60}")
        print(f"Baseline Summary:")
        print(f"  Cases evaluated: {total_cases}")
        print(f"  Avg latency: {avg_latency*1000:.1f}ms")
        print(f"  Chunk count: {pipeline.get_chunk_count()}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    run_baseline_evaluation()
