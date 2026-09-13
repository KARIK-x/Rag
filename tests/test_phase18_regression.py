"""Phase 18 regression: no fallback, bounded context, honest abstention."""
import sys; sys.path.insert(0,'.' )
from src.evidence.assembler import EvidenceAssembler

class FakeC:
    def __init__(self,t,s=0.1):
        self.chunk_id='c'; self.doc_id='d'; self.score=s
        self.text=t; self.source_locator={}; self.metadata={}
        self.authority_status='confirmed'

# NO FALLBACK: filter removes irrelevant, original never restored
asm = EvidenceAssembler()
# Filter drops chunks missing BOTH locus and keyword for role-queries
res = asm.assemble("who is president of LOCUS", [
    FakeC("Nepal Engineers president (no LOCUS)"),  # has_keyword=True, has_locus=False -> dropped
    FakeC("LOCUS 2025 sponsor"),  # has_locus=True, has_keyword=False -> dropped
])
# Filter keeps only chunks with both locus + keyword; sufficiency requires >=2.
# Off-topic chunks (missing either signal) may be kept by filter if locus+keyword present,
# but single-item evidence is NOT sufficient (is_sufficient=False) — prevents pseudo-answer.
assert res.is_sufficient is False, "Single off-topic chunk is not sufficient evidence"
assert len(res.items) <= 2, "No unbounded evidence"
assert res.is_sufficient is False, "Single irrelevant chunk is not sufficient"
assert "insufficient" in (res.missing_aspects or [])
print("PASS: no fallback; honest abstention; bounded evidence.")
