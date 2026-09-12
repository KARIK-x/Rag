"""Pre-index extraction quality gate — must pass before allowing INDEXED."""
import re
from typing import Dict, Any, Optional

class ExtractionQualityGate:
    def check(self, extracted_text: str, source_doc_id: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        result = {"passed": True, "issues": [], "quality_score": 1.0}
        if not extracted_text or len(extracted_text.strip()) < 10:
            result["passed"] = False
            result["issues"].append("empty_or_tiny_extraction")
            result["quality_score"] = 0.0
        # Abnormal yield check (e.g., mostly whitespace or binary artifacts)
        whitespace_ratio = len(re.findall(r"\s", extracted_text)) / max(len(extracted_text), 1)
        if whitespace_ratio > 0.9:
            result["passed"] = False
            result["issues"].append("abnormal_whitespace_yield")
            result["quality_score"] *= 0.5
        # Parser warning tracking (simulated — would read extraction log)
        result["parser_warnings"] = metadata.get("parser_warnings") if metadata else None
        return result
