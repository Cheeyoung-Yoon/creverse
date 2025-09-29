from pydantic import BaseModel
from typing import List, Literal
# 기본 골조 작성 
RubricName = Literal["introduction","body","conclusion","grammar"]

class Correction(BaseModel):
    highlight: str
    issue: str
    correction: str

class RubricItemResult(BaseModel):
    rubric_item: RubricName
    score: int  # 0-2
    corrections: List[Correction]
    feedback: str
