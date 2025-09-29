from pydantic import BaseModel, Field
from typing import Literal

# 기본 골조 작성 
Level = Literal["Basic","Intermediate","Advanced","Expert"]
class EssayEvalRequest(BaseModel):
    level_group: Level
    topic_prompt: str = Field(min_length=3)
    submit_text: str = Field(min_length=10, max_length=4000)
