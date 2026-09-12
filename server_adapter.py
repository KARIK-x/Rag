#!/usr/bin/env python3
"""Lightweight adapter connecting frontend to validated LOCUS RAG backend.
Uses only existing modules — no duplicate retrieval logic."""
import sys, json
sys.path.insert(0, '.')
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from src.indexing.vector import (BM25Index, ExactEntityIndex, DenseVectorIndex, RetrievalCandidate, SearchQuery)
from src.retrieval.hybrid import HybridRetriever, retrieve

# Load fixture indexes from validated build
IDX_DIR = Path('data/indexes')
BM25 = BM25Index(db_path=str(IDX_DIR/'bm25.db')) if (IDX_DIR/'bm25.db').exists() else None
EXACT = ExactEntityIndex(db_path=str(IDX_DIR/'exact.db')) if (IDX_DIR/'exact.db').exists() else None
# Dense requires embeddings; skip if empty
DENSE = DenseVectorIndex(dim=384, db_path=str(IDX_DIR/'dense.db')) if (IDX_DIR/'dense.db').exists() else None

class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()
    def do_POST(self):
        if self.path != '/api/retrieve':
            self.send_error(404); return
        length = int(self.headers.get('Content-Length',0))
        body = self.rfile.read(length) if length else b'{}'
        try: q = json.loads(body.decode('utf-8')).get('query','')
        except: q = ''
        try:
            # Real backend call — uses validated HybridRetriever / retrieve
            retriever = HybridRetriever(dense=DENSE, bm25=BM25, exact=EXACT)
            results = retriever.retrieve(q, top_k=10) if q else []
            out = [{
                'chunk_id': r.chunk_id,
                'doc_id': r.doc_id,
                'score': r.score,
                'text': r.text[:1200] if r.text else '',
                'source_locator': r.source_locator or {},
                'index_name': r.index_name,
                'metadata': r.metadata or {},
            } for r in results]
        except Exception as e:
            out = [{'error': str(e), 'note': 'Real backend retrieval attempted; fixture index loaded.'}]
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers()
        self.wfile.write(json.dumps({'query':q,'results':out,'backend':'HybridRetriever (validated V1)','count':len(out),'read_only_drive':True}).encode())
    def log_message(self, fmt, *a): pass  # silent

if __name__ == '__main__':
    s = HTTPServer(('', 8765), Handler)
    print('LOCUS adapter on http://localhost:8765/api/retrieve (real backend; POST {"query":"..."})')
    s.serve_forever()
