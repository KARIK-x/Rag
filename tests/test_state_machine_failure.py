
"""State machine failure semantics — permanent/retry/review/terminal."""
import sys; sys.path.insert(0,".")
from src.pipeline.statemachine import DocumentStateMachine, DocumentState

def _chain_to_indexed(sm, doc):
    for s in [DocumentState.DISCOVERED, DocumentState.DOWNLOADING, DocumentState.DOWNLOADED,
              DocumentState.EXTRACTED, DocumentState.NORMALIZED, DocumentState.CLASSIFIED,
              DocumentState.DEDUPLICATED, DocumentState.CHUNKED, DocumentState.EMBEDDED, DocumentState.INDEXED]:
        # From DISCOVERED: only DOWNLOADING/FAILED allowed; build chain correctly
        if s == DocumentState.DISCOVERED:
            sm.transition(doc, s)
        elif s == DocumentState.DOWNLOADING:
            sm.transition(doc, s)
        elif s == DocumentState.DOWNLOADED:
            sm.transition(doc, s)
        elif s == DocumentState.EXTRACTED:
            sm.transition(doc, s)
        elif s == DocumentState.NORMALIZED:
            sm.transition(doc, s)
        elif s == DocumentState.CLASSIFIED:
            sm.transition(doc, s)
        elif s == DocumentState.DEDUPLICATED:
            sm.transition(doc, s)
        elif s == DocumentState.CHUNKED:
            sm.transition(doc, s)
        elif s == DocumentState.EMBEDDED:
            sm.transition(doc, s)
        elif s == DocumentState.INDEXED:
            # Must come from EMBEDDED
            pass  # already at EMBEDDED from previous; do direct now
    # Direct from embedded to indexed
    sm.transition(doc, DocumentState.INDEXED)

def test_dead_letter_permanent():
    sm = DocumentStateMachine(db_path="data/db/test_dead_letter.db")
    doc = "perm_01"
    sm.transition(doc, DocumentState.DISCOVERED)
    sm.transition(doc, DocumentState.DOWNLOADING)
    sm.transition(doc, DocumentState.DOWNLOADED)
    sm.transition(doc, DocumentState.EXTRACTED)
    sm.transition(doc, DocumentState.NORMALIZED)
    sm.transition(doc, DocumentState.CLASSIFIED)
    sm.transition(doc, DocumentState.DEDUPLICATED)
    sm.transition(doc, DocumentState.CHUNKED)
    sm.transition(doc, DocumentState.EMBEDDED)
    sm.transition(doc, DocumentState.INDEXED)
    sm.transition(doc, DocumentState.FAILED, error_message="permanent: data_corrupt")
    sm.transition(doc, DocumentState.DEAD_LETTER, error_message="permanent: unrecoverable")
    assert sm.get_state(doc) == DocumentState.DEAD_LETTER
    assert sm.transition(doc, DocumentState.DISCOVERED) == False
    print("PASS: dead-letter terminal + permanent enforcement")

def test_retry_transient():
    sm = DocumentStateMachine(db_path="data/db/test_retry.db")
    doc = "trans_01"
    sm.transition(doc, DocumentState.DISCOVERED)
    sm.transition(doc, DocumentState.DOWNLOADING)
    sm.transition(doc, DocumentState.FAILED, error_message="timeout")
    assert sm.get_attempt_count(doc) >= 1
    assert sm.transition(doc, DocumentState.DISCOVERED) == True
    print("PASS: retry transient from FAILED")

def test_review_path():
    sm = DocumentStateMachine(db_path="data/db/test_review.db")
    doc = "rev_01"
    # REQUIRES_REVIEW can be reached from DOWNLOADING (valid per VALID_TRANSITIONS)
    sm.transition(doc, DocumentState.DISCOVERED)
    sm.transition(doc, DocumentState.DOWNLOADING)
    sm.transition(doc, DocumentState.REQUIRES_REVIEW, error_message="extraction_quality_low")
    assert sm.get_state(doc) == DocumentState.REQUIRES_REVIEW
    print("PASS: review path from DOWNLOADING")
if __name__ == "__main__":
    test_dead_letter_permanent()
    test_retry_transient()
    test_review_path()
    print("All state-machine failure tests pass.")
