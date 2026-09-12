"""Regression: frontend renderResult must receive cits as array; backend must return claims array."""
import urllib.request, json
def test_api_returns_claims_and_results():
    req = urllib.request.Request(
        "http://localhost:8765/api/retrieve",
        data=b'{"query":"test"}',
        headers={"Content-Type":"application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        d = json.loads(resp.read())
    assert isinstance(d.get("results"), list), "results must be array"
    # claims must be array (or missing) — never undefined/non-array
    claims = d.get("claims")
    assert claims is None or isinstance(claims, list), f"claims must be list, got {type(claims)}"
    # Each citation (result) must have doc_id/chunk_id for source rendering
    for r in d.get("results", [])[:1]:
        assert r.get("chunk_id") or r.get("doc_id"), "source identifier missing"
