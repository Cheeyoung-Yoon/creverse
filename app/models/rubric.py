# app/models/rubric.py
from typing import List, Literal
from pydantic import BaseModel, Field

RubricItemName = Literal["introduction", "body", "conclusion", "grammar"]

class Correction(BaseModel):
    highlight: str
    issue: str
    correction: str

class RubricItemResult(BaseModel):
    rubric_item: RubricItemName
    score: int = Field(ge=0, le=2)  
    corrections: List[Correction]
    feedback: str

# 전체 결과는 List[RubricItemResult]


class ScoreCorrectionFeedback(BaseModel):
    """Aggregated score, merged corrections, and combined feedback."""
    score: int = Field(ge=0, le=2)
    corrections: List[Correction]
    feedback: str


class PreProcessResult(BaseModel):
    """Optional pre-processing metadata for context (length, language, etc.)."""
    word_count: int
    meets_length_req: bool
    is_english: bool
