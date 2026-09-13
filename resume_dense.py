"""Resume dense embeddings from checkpoint — one writer, parallel compute, preserve existing."""
import sqlite3, json, os, sys, time
sys.path.insert(0,'.')
from sentence_transformers import SentenceTransformer
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np

DB = 'data/indexes/dense.db'
CHUNK_DIR = 'data/chunks'
MODELS = 'all-MiniLM-L6-v2'
DIM = 384
BATCH = 200

def init_writer():
    conn = sqlite3.connect(DB, timeout=30.0)
    conn.execute("CREATE TABLE IF NOT EXISTS dense_index (chunk_id TEXT PRIMARY KEY, embedding TEXT NOT NULL)")
    conn.commit(); conn.close()

# Preload existing IDs
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT chunk_id FROM dense_index")
existing = {r[0] for r in cur.fetchall()}
conn.close()
print(f"Existing dense: {len(existing)}; target chunks: 112392")

# Read missing chunk IDs (deterministic from filenames)
all_ids = sorted([f.replace('.json','') for f in os.listdir(CHUNK_DIR) if f.endswith('.json')])
missing = [cid for cid in all_ids if cid not in existing]
print(f"Missing to embed: {len(missing)}")

# Load model once per worker via lazy init; use main process for model load
model = SentenceTransformer(MODELS)

def embed_batch(ids):
    res = {}
    for cid in ids:
        try:
            with open(os.path.join(CHUNK_DIR, cid+'.json'), 'r', encoding='utf-8') as f:
                data = json.load(f)
            text = data.get('raw_text') or data.get('text') or ''
            emb = model.encode(text, convert_to_numpy=True).tolist()
            res[cid] = emb
        except Exception as e:
            res[cid] = None
    return res

# Process in batches with single writer
written = 0
start = time.time()
for i in range(0, len(missing), BATCH):
    batch = missing[i:i+BATCH]
    batch_res = embed_batch(batch)
    # Single SQLite writer
    conn = sqlite3.connect(DB, timeout=30.0)
    cur = conn.cursor()
    for cid, emb in batch_res.items():
        if emb is not None and len(emb) == DIM and not any(np.isnan(np.array(emb))):
            cur.execute("INSERT OR IGNORE INTO dense_index (chunk_id, embedding) VALUES (?, ?)", (cid, json.dumps(emb)))
            if cur.rowcount > 0:
                written += 1
    conn.commit(); conn.close()
    if (i // BATCH) % 10 == 0:
        total_now = len(existing) + written
        print(f"Batch {i//BATCH}: embedded {len(batch)}; total dense now ~{total_now}; rate ~{(total_now)/(time.time()-start+0.001):.1f}/sec")
        # Update checkpoint
        with open('data/embedding_build_checkpoint.json', 'w') as f:
            json.dump({"dense_count": total_now, "processed_batch": i//BATCH, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)

total_final = len(existing) + written
print(f"DONE — written this run: {written}; total dense: {total_final}; target 112392; remaining: {112392-total_final}")
# Verify
conn = sqlite3.connect(DB)
cur = conn.cursor(); cur.execute("SELECT COUNT(*) FROM dense_index"); final = cur.fetchone()[0]; conn.close()
print(f"DB verified count: {final}")
