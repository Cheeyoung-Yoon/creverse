from pydantic import BaseModel, Field
from typing import Literal, Optional

# 기본 골조 작성 
Level = Literal["Basic","Intermediate","Advanced","Expert"]
class EssayEvalRequest(BaseModel):
    rubric_level: Level  # Changed from level_group to match Excel data
    topic_prompt: str = Field(min_length=3)
    submit_text: str = Field(min_length=10, max_length=4000)
    prompt_version: Optional[str] = Field(None, description="Prompt version to use (e.g., v1.1.0)")
