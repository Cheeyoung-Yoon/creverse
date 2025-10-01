from pydantic import BaseModel, Field, validator, root_validator
from typing import Literal, Optional
import re

Level = Literal["Basic", "Intermediate", "Advanced", "Expert"]

class EssayEvalRequest(BaseModel):
    rubric_level: Level
    topic_prompt: str = Field(
        min_length=10, 
        max_length=500,
        description="The essay topic or prompt"
    )
    submit_text: str = Field(
        min_length=50, 
        max_length=4000,
        description="The essay text to evaluate"
    )
    prompt_version: Optional[str] = Field(
        None, 
        regex=r"^v\d+\.\d+\.\d+$",
        description="Prompt version to use (e.g., v1.4.1)"
    )
    
    @validator('submit_text')
    def validate_submit_text(cls, v):
        """Validate essay content"""
        if not v or not v.strip():
            raise ValueError("Essay text cannot be empty")
        
        # Check for minimum word count
        word_count = len(v.strip().split())
        if word_count < 10:
            raise ValueError(f"Essay too short. Minimum 10 words, got {word_count}")
        
        # Check for suspicious patterns
        if len(set(v.lower().split())) < word_count * 0.3:
            raise ValueError("Essay appears to have too much repetition")
        
        return v.strip()
    
    @validator('topic_prompt')
    def validate_topic_prompt(cls, v):
        """Validate topic prompt"""
        if not v or not v.strip():
            raise ValueError("Topic prompt cannot be empty")
        
        # Remove excessive whitespace
        return re.sub(r'\s+', ' ', v.strip())
    
    @root_validator
    def validate_level_and_length(cls, values):
        """Validate essay length against rubric level"""
        level = values.get('rubric_level')
        text = values.get('submit_text', '')
        
        if level and text:
            word_count = len(text.split())
            
            # Level-specific word count requirements
            requirements = {
                "Basic": (50, 150),
                "Intermediate": (100, 200),
                "Advanced": (150, 300),
                "Expert": (200, 400)
            }
            
            if level in requirements:
                min_words, max_words = requirements[level]
                if word_count < min_words:
                    raise ValueError(
                        f"{level} level requires at least {min_words} words, got {word_count}"
                    )
                if word_count > max_words:
                    raise ValueError(
                        f"{level} level allows maximum {max_words} words, got {word_count}"
                    )
        
        return values

    class Config:
        schema_extra = {
            "example": {
                "rubric_level": "Intermediate",
                "topic_prompt": "Describe your dream vacation destination and explain why you would like to visit there.",
                "submit_text": "My dream vacation destination is Japan because it offers a unique blend of traditional culture and modern technology. I would love to visit ancient temples in Kyoto and experience the bustling streets of Tokyo.",
                "prompt_version": "v1.4.1"
            }
        }