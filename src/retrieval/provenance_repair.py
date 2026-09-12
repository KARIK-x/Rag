"""Repair provenance mapping from structured provenance files to retrieval results."""
import json, os
from pathlib import Path
from typing import Dict, Any

PROV_DIR = Path('data/structured')
_PROV_CACHE = None

def _load_provenance_map() -> Dict[str, Dict[str, Any]]:
    global _PROV_CACHE
    if _PROV_CACHE is not None:
        return _PROV_CACHE
    m = {}
    if not PROV_DIR.exists():
        _PROV_CACHE = m; return m
    for f in PROV_DIR.glob('*.provenance.json'):
        try:
            data = json.load(open(f))
            did = data.get('doc_id') or data.get('drive_file_id')
            if did:
                m[str(did)] = {
                    'filename': data.get('filename') or data.get('name'),
                    'folder_path': data.get('folder_path'),
                    'mime_type': data.get('mime_type'),
                    'drive_file_id': data.get('drive_file_id'),
                    'page_start': data.get('page_start'),
                    'page_end': data.get('page_end'),
                    'table_id': data.get('table_id'),
                    'sheet_name': data.get('sheet_name'),
                }
        except Exception:
            pass
    _PROV_CACHE = m
    return m

def repair_candidate(candidate) -> None:
    """Enrich a RetrievalCandidate's source_locator/metadata from provenance map."""
    prov_map = _load_provenance_map()
    doc_id = getattr(candidate, 'doc_id', None) or ''
    meta = (getattr(candidate, 'metadata', None) or {})
    loc = (getattr(candidate, 'source_locator', None) or {})
    # Try doc_id first, then drive_file_id from metadata
    key = doc_id
    if not key or key not in prov_map:
        for k in [meta.get('drive_file_id'), meta.get('doc_id'), meta.get('filename')]:
            if k and str(k) in prov_map:
                key = str(k); break
    if key and key in prov_map:
        info = prov_map[key]
        # Enrich source_locator
        if info.get('filename') and not loc.get('filename'):
            loc['filename'] = info['filename']
        if info.get('folder_path') and not loc.get('folder_path'):
            loc['folder_path'] = info['folder_path']
        if info.get('mime_type') and not loc.get('mime_type'):
            loc['mime_type'] = info['mime_type']
        if info.get('drive_file_id') and not loc.get('drive_file_id'):
            loc['drive_file_id'] = info['drive_file_id']
        if info.get('page_start') is not None and not loc.get('page'):
            loc['page'] = info['page_start']
        if info.get('table_id') and not loc.get('table_id'):
            loc['table_id'] = info['table_id']
        if info.get('sheet_name') and not loc.get('sheet_name'):
            loc['sheet_name'] = info['sheet_name']
        # Enrich metadata
        meta['filename'] = info.get('filename')
        meta['folder_path'] = info.get('folder_path')
        meta['mime_type'] = info.get('mime_type')
        meta['drive_file_id'] = info.get('drive_file_id')
        meta['page_start'] = info.get('page_start')
        meta['page_end'] = info.get('page_end')
        meta['table_id'] = info.get('table_id')
        meta['sheet_name'] = info.get('sheet_name')
