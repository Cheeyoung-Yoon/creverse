from typing import Dict, Optional

from pydantic import BaseModel

from app.models.request import Level
from app.models.rubric import PreProcessResult, RubricItemResult, ScoreCorrectionFeedback


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class EvaluationTimeline(BaseModel):
    start: str
    end: str


class RubricItemPayload(RubricItemResult):
    token_usage: Optional[TokenUsage] = None
    evaluation_type: str
    error: Optional[str] = None


class StructureChainResult(BaseModel):
    introduction: RubricItemPayload
    body: RubricItemPayload
    conclusion: RubricItemPayload
    token_usage_total: Optional[TokenUsage] = None
    evaluation_type: str


class EssayEvalResponse(BaseModel):
    rubric_level: Level
    pre_process: PreProcessResult
    grammar: RubricItemPayload
    structure: StructureChainResult
    aggregated: ScoreCorrectionFeedback
    timings: Dict[str, float]
    timeline: EvaluationTimeline
