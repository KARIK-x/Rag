"""
LOCUS RAG OCR engine (fallback path).

Per spec §19:
  - OCR is a fallback, not the primary path
  - Measures: character/word error rate, numeric accuracy, table accuracy
  - Carries: engine, model/version, confidence, page, bounding box, OCR-used flag

Tesseract 5.5.0 (pytesseract) is the V1 OCR provider.
Devanagari/Nepali support is limited by installed tessdata (currently eng/osd/snum).
The interface supports swapping in Surya or another engine later.
"""

import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Suppress PIL's decompression-bomb warnings for large rendered scans
# (legitimate in an OCR pipeline — we render high-DPI pages ourselves).
from PIL import Image  # noqa: E402
Image.MAX_IMAGE_PIXELS = 200_000_000  # allow up to 200M pixels (e.g. 300 DPI A3)
Image.warnings.simplefilter("ignore", Image.DecompressionBombWarning)  # noqa: E402

# Suppress PIL's decompression-bomb warnings for large rendered scans
# (legitimate in an OCR pipeline — we render high-DPI pages ourselves).
from PIL import Image  # noqa: E402
Image.MAX_IMAGE_PIXELS = 200_000_000  # allow up to 200M pixels (e.g. 300 DPI A3)
Image.warnings.simplefilter("ignore", Image.DecompressionBombWarning)  # noqa: E402

logger = logging.getLogger(__name__)


class OCREngine(Enum):
    TESSERACT = "tesseract"
    SURYA = "surya"


@dataclass
class OCRResult:
    """Result of OCR on a single page or image."""
    text: str
    confidence: float  # 0-100 aggregate, if available
    word_confidences: List[float] = field(default_factory=list)
    bboxes: List[Dict[str, Any]] = field(default_factory=list)  # page-space boxes
    engine: str = "tesseract"
    model_version: Optional[str] = None
    language: Optional[str] = None
    used: bool = False
    error: Optional[str] = None

    def as_metadata(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "model_version": self.model_version,
            "language": self.language,
            "confidence": self.confidence,
            "ocr_used": self.used,
        }


class OCRProvider:
    """OCR provider abstraction (Phase 2b: Tesseract)."""

    def __init__(
        self,
        engine: OCREngine = OCREngine.TESSERACT,
        languages: Optional[List[str]] = None,
        tesseract_bin: Optional[str] = None,
        dpi: int = 300,
    ):
        self.engine = engine
        self.languages = languages or ["eng"]
        self.dpi = dpi

        if engine == OCREngine.TESSERACT:
            # pytesseract wraps the tesseract binary
            import pytesseract
            self._pytesseract = pytesseract
            self.tesseract_bin = (
                tesseract_bin or pytesseract.pytesseract.tesseract_cmd
            )
            self.model_version = self._get_tesseract_version()
            self._check_languages()
        elif engine == OCREngine.SURYA:
            # Surya is GPU-accelerated but heavy to install.
            # Stub: raise on use unless installed.
            self._pytesseract = None
            self.tesseract_bin = None
            self.model_version = "surya-unavailable"

    # ─── Diagnostics ──────────────────────────────────────────────────────

    def _get_tesseract_version(self) -> Optional[str]:
        try:
            result = subprocess.run(
                [self.tesseract_bin, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            first_line = result.stdout.splitlines()[0] if result.stdout else ""
            return first_line.strip()
        except Exception as e:
            logger.warning("Could not detect Tesseract version: %s", e)
            return None

    def _check_languages(self):
        """Verify the requested languages are available in tessdata."""
        try:
            result = subprocess.run(
                [self.tesseract_bin, "--list-langs"],
                capture_output=True, text=True, timeout=10,
            )
            available = {
                line.strip() for line in result.stdout.splitlines()
                if line.strip() and not line.strip().startswith("List")
            }
            self.available_languages = available
            missing = [lang for lang in self.languages if lang not in available]
            if missing:
                logger.warning(
                    "Tesseract lacks language data for: %s. "
                    "Only %s available. Consider downloading tessdata for %s.",
                    missing, sorted(available), missing,
                )
        except Exception as e:
            logger.warning("Could not list Tesseract languages: %s", e)
            self.available_languages = set()

    # ─── OCR entry points ─────────────────────────────────────────────────────

    def ocr_image(
        self,
        image_bytes: bytes,
        page_number: int = 1,
        language: Optional[str] = None,
    ) -> OCRResult:
        """Run OCR on a raw image (PNG/JPEG bytes)."""
        import io
        from PIL import Image

        try:
            img = Image.open(io.BytesIO(image_bytes))
            # Convert to RGB (Tesseract prefers RGB/grayscale)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            lang = language or "+".join(self.languages)

            ocr_data = self._pytesseract.image_to_data(
                img,
                lang=lang,
                config=f"--dpi {self.dpi}",
                output_type=self._pytesseract.Output.DICT,
                timeout=60,
            )

            text_lines: List[str] = []
            confidences: List[float] = []
            bboxes: List[Dict[str, Any]] = []

            for i, text in enumerate(ocr_data.get("text", [])):
                if text and text.strip():
                    text_lines.append(text.strip())
                    conf_total = float(ocr_data.get("conf", [0])[i] if i < len(ocr_data.get("conf", [])) else 0)
                    if conf_total > 0:
                        confidences.append(conf_total)
                    bboxes.append({
                        "left": ocr_data.get("left", [])[i] if i < len(ocr_data.get("left", [])) else 0,
                        "top": ocr_data.get("top", [])[i] if i < len(ocr_data.get("top", [])) else 0,
                        "width": ocr_data.get("width", [])[i] if i < len(ocr_data.get("width", [])) else 0,
                        "height": ocr_data.get("height", [])[i] if i < len(ocr_data.get("height", [])) else 0,
                        "page": page_number,
                    })

            confidence = (
                sum(confidences) / len(confidences) if confidences else 0.0
            )
            return OCRResult(
                text="\n".join(text_lines),
                confidence=confidence,
                word_confidences=confidences,
                bboxes=bboxes,
                engine="tesseract",
                model_version=self.model_version,
                language=lang,
                used=True,
            )
        except Exception as e:
            logger.warning("OCR failed: %s", e)
            return OCRResult(
                text="",
                confidence=0.0,
                engine="tesseract",
                used=True,
                error=str(e),
            )

    def ocr_pdf_page(
        self,
        pdf_path: str,
        page_number: int,
        language: Optional[str] = None,
    ) -> OCRResult:
        """Render a PDF page to an image then OCR it."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return OCRResult(
                text="", confidence=0.0, engine="tesseract",
                used=True, error="PyMuPDF not installed; cannot render PDF page",
            )

        try:
            pdf = fitz.open(pdf_path)
            if page_number < 1 or page_number > pdf.page_count:
                pdf.close()
                return OCRResult(
                    text="", confidence=0.0, engine="tesseract",
                    used=True,
                    error=f"page {page_number} out of range (1-{pdf.page_count})",
                )

            page = pdf[page_number - 1]
            # Render at high DPI for OCR accuracy
            zoom = self.dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            image_bytes = pix.tobytes("png")

            pdf.close()
            return self.ocr_image(image_bytes, page_number=page_number, language=language)
        except Exception as e:
            return OCRResult(
                text="", confidence=0.0, engine="tesseract",
                used=True, error=f"PDF page OCR failed: {e}",
            )

    # ─── OCR text quality evaluation ────────────────────────────────────────

    def evaluate_ocr_quality(
        self,
        ocr_text: str,
        reference_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate OCR output quality.

        If reference_text is given, compute character error rate (CER) and
        word error rate (WER). Otherwise report structural statistics.
        """
        import math

        if reference_text:
            cer = self._char_error_rate(reference_text, ocr_text)
            wer = self._word_error_rate(reference_text, ocr_text)
        else:
            cer = None
            wer = None

        return {
            "chars": len(ocr_text),
            "words": len(ocr_text.split()),
            "cer": cer,
            "wer": wer,
            "numeric_accuracy": self._numeric_accuracy(ocr_text),
        }

    def _char_error_rate(self, ref: str, hyp: str) -> float:
        """Normalized edit distance using difflib ratio (0=perfect, 1=worst)."""
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, ref, hyp).ratio()
        return 1.0 - ratio

    def _word_error_rate(self, ref: str, hyp: str) -> float:
        from difflib import SequenceMatcher
        ref_words = ref.split()
        hyp_words = hyp.split()
        if not ref_words:
            return 1.0 if hyp_words else 0.0
        ratio = SequenceMatcher(None, ref_words, hyp_words).ratio()
        return 1.0 - ratio

    def _numeric_accuracy(self, ocr_text: str) -> float:
        """Fraction of numeric tokens that parse cleanly."""
        import re
        numeric_tokens = re.findall(r"\b\d[\d,.]*\b", ocr_text)
        if not numeric_tokens:
            return 1.0  # no numbers → perfect by vacuous truth
        clean = sum(1 for t in numeric_tokens if t.replace(",", "").replace(".", "").isdigit())
        return clean / len(numeric_tokens)