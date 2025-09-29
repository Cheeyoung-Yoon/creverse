import pytest


import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.services.evaluation.pre_process import (
    pre_process_essay, LEVEL_WORD_REQUIREMENTS
)


class TestPreProcessEssay:
    """Test the main pre-processing function."""
    
    def test_valid_basic_essay(self):
        topic = "Describe your hobby"
        submit = "I will move to a higher ground. I have two reasons. First, Because tsunamis are dangerous. Because tsunamis can sweep us away. Second, tsunamis are big waves. But it can't come at the high ground. For these reasons, I will move to a higher ground."
        
        result = pre_process_essay(submit, topic, "Basic")
        
        assert "is_valid" in result
        assert "word_count" in result
        assert "meets_length_req" in result
        assert "is_english" in result
    
    def test_too_short_essay(self):
        submit = "I like reading."
        result = pre_process_essay(submit, "Describe your hobby", "Basic")
        
        assert result["meets_length_req"] is False
    
    def test_different_levels(self):
        topic = "Describe your hobby"
        submit = "Reading is my favorite hobby because it expands my knowledge." * 10
        
        for level in ["Basic", "Intermediate", "Advanced", "Expert"]:
            result = pre_process_essay(submit, topic, level)
            assert "word_count" in result
            assert result["word_count"] > 0
    
    def test_level_requirements_exist(self):
        """Test that all level requirements are properly defined."""
        required_levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        
        for level in required_levels:
            assert level in LEVEL_WORD_REQUIREMENTS
            reqs = LEVEL_WORD_REQUIREMENTS[level]
            assert "min_words" in reqs
            assert "max_words" in reqs
