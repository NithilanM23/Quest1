from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Candidate:
    """A single candidate match for the target dialogue line."""
    start_sec: float
    end_sec: float
    text: str                     # raw extracted text (unmodified)
    source: Literal["asr", "ocr"]
    score: float                  # rapidfuzz similarity 0-100


@dataclass
class Result:
    """Final output of the pipeline."""
    timestamp: str                 # HH:MM:SS.sss
    frame_number: int
    extracted_text: str
    matched_against: str
    similarity_score: float
    confidence: Literal["high", "medium", "low", "not_found"]
    source: str                    # "audio", "visual", or "audio+visual"
    frame_image: Optional[str] = None
    alternates: list = field(default_factory=list)  # other candidates, if confidence < high
