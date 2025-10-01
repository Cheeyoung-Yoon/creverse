from pydantic import BaseModel, Field, validator
from typing import Literal
import re

# 기본 골조 작성 
Level = Literal["Basic","Intermediate","Advanced","Expert"]

class EssayEvalRequest(BaseModel):
    rubric_level: Level  # Changed from level_group to match Excel data
    topic_prompt: str = Field(min_length=10, max_length=500, description="The essay topic or prompt")
    submit_text: str = Field(min_length=50, max_length=4000, description="The essay text to evaluate")
    
    @validator('submit_text')
    def validate_submit_text(cls, v):
        """Validate essay content"""
        if not v or not v.strip():
            raise ValueError("Essay text cannot be empty")
        
        # Check for minimum word count
        word_count = len(v.strip().split())
        if word_count < 10:
            raise ValueError(f"Essay too short. Minimum 10 words, got {word_count}")
        
        return v.strip()
    
    @validator('topic_prompt')
    def validate_topic_prompt(cls, v):
        """Validate topic prompt"""
        if not v or not v.strip():
            raise ValueError("Topic prompt cannot be empty")
        
        # Remove excessive whitespace
        return re.sub(r'\s+', ' ', v.strip())
    
    class Config:
        json_schema_extra = {
            "example": {
                "rubric_level": "Intermediate",
                "topic_prompt": "Describe your dream vacation destination and explain why you would like to visit there.",
                "submit_text": "My dream vacation destination is Japan because it offers a unique blend of traditional culture and modern technology. I would love to visit ancient temples in Kyoto and experience the bustling streets of Tokyo. The food culture is also fascinating, with everything from street food to high-end restaurants."
            }
        }
