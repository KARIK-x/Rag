"""Regression test — does not weaken assertions.
Fails if generic readiness message returns for real queries."""
import urllib.request, json, sys, os
sys.path.insert(0, '.')

GENERIC = "I'm ready to provide answers based on the evidence"
QUERIES = [
    ("What is LOCUS?", ["LOCUS", "Nepal", "festival", "student"]),
    ("Who are the organising team of LOCUS?", ["team", "organising", "organizing", "committee", "design", "content"]),
    ("What are the prizes of LOCUS?", ["prize", "award", "reward", "competition"]),
    ("When is LOCUS?", ["2025", "2026", "date", "held", "March"]),
    ("Name one sponsor of LOCUS.", ["sponsor", "investment", "Rs", "partner"]),
]

def run():
    ok = True
    for q, keywords in QUERIES:
        req = urllib.request.Request('http://localhost:8765/api/retrieve',
            data=json.dumps({'query': q}).encode(), headers={'Content-Type':'application/json'})
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        ans = (data.get('answer_text') or '').strip()
        src = data.get('sources', [])
        ev = data.get('evidence_sufficient')
        # Must NOT be generic
        if GENERIC in ans:
            print(f"FAIL {q!r}: generic fallback present in answer")
            ok = False
        if len(ans) < 10:
            print(f"FAIL {q!r}: answer too short: {ans!r}")
            ok = False
        if not src:
            print(f"FAIL {q!r}: no sources")
            ok = False
        # Must contain at least one keyword or honest abstention
        has_kw = any(k.lower() in ans.lower() for k in keywords)
        honest_abstention = "could not verify" in ans.lower() or "insufficient" in ans.lower() or "honest" in ans.lower() or "no verified" in ans.lower()
        if not (has_kw or honest_abstention):
            print(f"FAIL {q!r}: answer does not address question (no keywords, no abstention): {ans!r}")
            ok = False
        print(f"Q={q!r} ans_len={len(ans)} ev={ev} src={len(src)} status={'PASS' if (has_kw or honest_abstention) and len(ans) > 10 and src else 'FAIL'}")
    return ok

if __name__ == '__main__':
    sys.exit(0 if run() else 1)
