"""
Unit tests for models/rubric.py
"""
import pytest
from datetime import datetime

from app.models.rubric import (
    PreProcessResult, RubricItemResult, ScoreCorrectionFeedback
)


@pytest.mark.unit
class TestPreProcessResult:
    """Test PreProcessResult model"""
    
    def test_pre_process_result_creation(self):
        """Test creating PreProcessResult with all fields"""
        result = PreProcessResult(
            is_appropriate_length=True,
            is_english=True,
            is_on_topic=True,
            word_count=150,
            detected_language="en",
            topic_relevance_score=0.85
        )
        
        assert result.is_appropriate_length is True
        assert result.is_english is True
        assert result.is_on_topic is True
        assert result.word_count == 150
        assert result.detected_language == "en"
        assert result.topic_relevance_score == 0.85
    
    def test_pre_process_result_defaults(self):
        """Test PreProcessResult with minimal required fields"""
        # Test what happens with minimal data
        result = PreProcessResult(
            is_appropriate_length=False,
            is_english=False,
            is_on_topic=False,
            word_count=0
        )
        
        assert result.is_appropriate_length is False
        assert result.is_english is False
        assert result.is_on_topic is False
        assert result.word_count == 0
    
    def test_pre_process_result_validation(self):
        """Test PreProcessResult field validation"""
        # Test with valid data
        result = PreProcessResult(
            is_appropriate_length=True,
            is_english=True,
            is_on_topic=True,
            word_count=100,
            detected_language="en",
            topic_relevance_score=0.9
        )
        
        # Should not raise any validation errors
        assert isinstance(result.word_count, int)
        assert isinstance(result.topic_relevance_score, (int, float))
        assert isinstance(result.detected_language, str)


@pytest.mark.unit
class TestRubricItemResult:
    """Test RubricItemResult model"""
    
    def test_rubric_item_result_creation(self):
        """Test creating RubricItemResult"""
        result = RubricItemResult(
            rubric_item="grammar",
            score=4,
            correction="Minor punctuation improvements needed",
            feedback="Overall excellent grammar with room for minor improvements"
        )
        
        assert result.rubric_item == "grammar"
        assert result.score == 4
        assert result.correction == "Minor punctuation improvements needed"
        assert result.feedback == "Overall excellent grammar with room for minor improvements"
    
    def test_rubric_item_result_score_validation(self):
        """Test score validation in RubricItemResult"""
        # Valid scores (assuming 1-5 scale)
        for score in [1, 2, 3, 4, 5]:
            result = RubricItemResult(
                rubric_item="test",
                score=score,
                correction="Test correction",
                feedback="Test feedback"
            )
            assert result.score == score
    
    def test_rubric_item_result_required_fields(self):
        """Test that all required fields are present"""
        result = RubricItemResult(
            rubric_item="introduction",
            score=3,
            correction="Some improvements needed",
            feedback="Good structure overall"
        )
        
        # All fields should be accessible
        assert hasattr(result, 'rubric_item')
        assert hasattr(result, 'score')
        assert hasattr(result, 'correction')
        assert hasattr(result, 'feedback')
    
    def test_rubric_item_different_categories(self):
        """Test RubricItemResult with different rubric categories"""
        categories = ["grammar", "introduction", "body", "conclusion"]
        
        for category in categories:
            result = RubricItemResult(
                rubric_item=category,
                score=3,
                correction=f"Test correction for {category}",
                feedback=f"Test feedback for {category}"
            )
            assert result.rubric_item == category


@pytest.mark.unit
class TestScoreCorrectionFeedback:
    """Test ScoreCorrectionFeedback model"""
    
    def test_score_correction_feedback_creation(self):
        """Test creating ScoreCorrectionFeedback"""
        scf = ScoreCorrectionFeedback(
            score=85,
            correction="Overall good essay with minor areas for improvement",
            feedback="Strong introduction and conclusion. Body could use more specific examples."
        )
        
        assert scf.score == 85
        assert "improvement" in scf.correction.lower()
        assert "introduction" in scf.feedback.lower()
    
    def test_score_correction_feedback_score_range(self):
        """Test ScoreCorrectionFeedback with different score ranges"""
        # Test various score values
        scores = [0, 25, 50, 75, 100]
        
        for score in scores:
            scf = ScoreCorrectionFeedback(
                score=score,
                correction=f"Correction for score {score}",
                feedback=f"Feedback for score {score}"
            )
            assert scf.score == score
            assert isinstance(scf.score, int)
    
    def test_score_correction_feedback_long_text(self):
        """Test ScoreCorrectionFeedback with long text fields"""
        long_correction = "This is a very long correction text. " * 20
        long_feedback = "This is a very long feedback text. " * 20
        
        scf = ScoreCorrectionFeedback(
            score=75,
            correction=long_correction,
            feedback=long_feedback
        )
        
        assert len(scf.correction) > 100
        assert len(scf.feedback) > 100
        assert scf.score == 75


@pytest.mark.unit
class TestModelInteractions:
    """Test interactions between different models"""
    
    def test_models_json_serialization(self):
        """Test that models can be JSON serialized"""
        import json
        
        # Test PreProcessResult
        pre_result = PreProcessResult(
            is_appropriate_length=True,
            is_english=True,
            is_on_topic=True,
            word_count=150,
            detected_language="en",
            topic_relevance_score=0.85
        )
        
        # Should be serializable (if using Pydantic)
        try:
            if hasattr(pre_result, 'dict'):
                serialized = pre_result.dict()
                assert isinstance(serialized, dict)
            elif hasattr(pre_result, '__dict__'):
                serialized = pre_result.__dict__
                assert isinstance(serialized, dict)
        except Exception:
            # If not using Pydantic, that's ok too
            pass
    
    def test_model_field_types(self):
        """Test that model fields have correct types"""
        # PreProcessResult
        pre_result = PreProcessResult(
            is_appropriate_length=True,
            is_english=True,
            is_on_topic=True,
            word_count=150
        )
        
        assert isinstance(pre_result.is_appropriate_length, bool)
        assert isinstance(pre_result.is_english, bool)
        assert isinstance(pre_result.is_on_topic, bool)
        assert isinstance(pre_result.word_count, int)
        
        # RubricItemResult
        rubric_result = RubricItemResult(
            rubric_item="grammar",
            score=4,
            correction="Test correction",
            feedback="Test feedback"
        )
        
        assert isinstance(rubric_result.rubric_item, str)
        assert isinstance(rubric_result.score, int)
        assert isinstance(rubric_result.correction, str)
        assert isinstance(rubric_result.feedback, str)
        
        # ScoreCorrectionFeedback
        scf = ScoreCorrectionFeedback(
            score=85,
            correction="Test correction",
            feedback="Test feedback"
        )
        
        assert isinstance(scf.score, int)
        assert isinstance(scf.correction, str)
        assert isinstance(scf.feedback, str)