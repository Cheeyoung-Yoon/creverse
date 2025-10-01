"""
Unit tests for models/rubric.py
"""
import pytest

from app.models.rubric import (
    Correction, RubricItemResult, ScoreCorrectionFeedback, PreProcessResult
)


@pytest.mark.unit
class TestCorrection:
    """Test Correction model"""
    
    def test_correction_creation(self):
        """Test creating Correction"""
        correction = Correction(
            highlight="there",
            issue="Wrong word usage",
            correction="their"
        )
        
        assert correction.highlight == "there"
        assert correction.issue == "Wrong word usage"
        assert correction.correction == "their"


@pytest.mark.unit
class TestPreProcessResult:
    """Test PreProcessResult model"""
    
    def test_pre_process_result_creation(self):
        """Test creating PreProcessResult with all fields"""
        result = PreProcessResult(
            word_count=150,
            meets_length_req=True,
            is_english=True,
            is_valid=True
        )
        
        assert result.word_count == 150
        assert result.meets_length_req is True
        assert result.is_english is True
        assert result.is_valid is True
    
    def test_pre_process_result_defaults(self):
        """Test PreProcessResult with minimal required fields"""
        result = PreProcessResult(
            word_count=0,
            meets_length_req=False,
            is_english=False,
            is_valid=False
        )
        
        assert result.meets_length_req is False
        assert result.is_english is False
        assert result.is_valid is False
        assert result.word_count == 0
    
    def test_pre_process_result_validation(self):
        """Test PreProcessResult field validation"""
        # Test with valid data
        result = PreProcessResult(
            word_count=100,
            meets_length_req=True,
            is_english=True,
            is_valid=True
        )
        
        # Should not raise any validation errors
        assert isinstance(result.word_count, int)
        assert isinstance(result.meets_length_req, bool)
        assert isinstance(result.is_english, bool)
        assert isinstance(result.is_valid, bool)


@pytest.mark.unit
class TestRubricItemResult:
    """Test RubricItemResult model"""
    
    def test_rubric_item_result_creation(self):
        """Test creating RubricItemResult"""
        result = RubricItemResult(
            rubric_item="grammar",
            score=2,
            corrections=[
                {
                    "highlight": "there",
                    "issue": "Wrong word usage",
                    "correction": "their"
                }
            ],
            feedback="Grammar is good with room for minor improvements"
        )
        
        assert result.rubric_item == "grammar"
        assert result.score == 2
        assert len(result.corrections) == 1
        assert result.feedback == "Grammar is good with room for minor improvements"
    
    def test_rubric_item_result_score_validation(self):
        """Test score validation in RubricItemResult"""
        # Valid scores (0-2 scale)
        for score in [0, 1, 2]:
            result = RubricItemResult(
                rubric_item="grammar",
                score=score,
                corrections=[],
                feedback="Test feedback"
            )
            assert result.score == score
    
    def test_rubric_item_result_required_fields(self):
        """Test that all required fields are present"""
        result = RubricItemResult(
            rubric_item="introduction",
            score=2,
            corrections=[],
            feedback="Good structure overall"
        )
        
        assert hasattr(result, "rubric_item")
        assert hasattr(result, "score")
        assert hasattr(result, "corrections")
        assert hasattr(result, "feedback")
    
    def test_rubric_item_different_categories(self):
        """Test RubricItemResult with different rubric categories"""
        categories = ["introduction", "body", "conclusion", "grammar"]
        
        for category in categories:
            result = RubricItemResult(
                rubric_item=category,
                score=1,
                corrections=[],
                feedback=f"Test feedback for {category}"
            )
            assert result.rubric_item == category


@pytest.mark.unit
class TestScoreCorrectionFeedback:
    """Test ScoreCorrectionFeedback model"""
    
    def test_score_correction_feedback_creation(self):
        """Test creating ScoreCorrectionFeedback"""
        scf = ScoreCorrectionFeedback(
            score=2,
            corrections=[
                {
                    "highlight": "example",
                    "issue": "Needs improvement",
                    "correction": "Add more specific examples"
                }
            ],
            feedback="Overall good work with some areas for improvement"
        )
        
        assert scf.score == 2
        assert len(scf.corrections) == 1
        assert "improvement" in scf.feedback.lower()
    
    def test_score_correction_feedback_score_range(self):
        """Test ScoreCorrectionFeedback score validation"""
        # Test valid scores (0-2)
        for score in [0, 1, 2]:
            scf = ScoreCorrectionFeedback(
                score=score,
                corrections=[],
                feedback=f"Feedback for score {score}"
            )
            assert scf.score == score
    
    def test_score_correction_feedback_long_text(self):
        """Test ScoreCorrectionFeedback with long feedback text"""
        long_feedback = "This is a very detailed feedback. " * 10
        
        scf = ScoreCorrectionFeedback(
            score=1,
            corrections=[],
            feedback=long_feedback
        )
        
        assert len(scf.feedback) > 100
        assert scf.score == 1


@pytest.mark.unit
class TestModelInteractions:
    """Test interactions between different models"""
    
    def test_models_json_serialization(self):
        """Test that models can be serialized to JSON"""
        # Test PreProcessResult
        pre_result = PreProcessResult(
            word_count=150,
            meets_length_req=True,
            is_english=True,
            is_valid=True
        )
        
        # Test RubricItemResult  
        rubric_result = RubricItemResult(
            rubric_item="grammar",
            score=2,
            corrections=[
                {
                    "highlight": "test",
                    "issue": "test issue",
                    "correction": "test correction"
                }
            ],
            feedback="Test feedback"
        )
        
        # Test that they can be converted to dict (JSON serializable)
        pre_dict = pre_result.model_dump()
        rubric_dict = rubric_result.model_dump()
        
        assert isinstance(pre_dict, dict)
        assert isinstance(rubric_dict, dict)
        assert pre_dict["word_count"] == 150
        assert rubric_dict["score"] == 2
    
    def test_model_field_types(self):
        """Test field types are preserved correctly"""
        pre_result = PreProcessResult(
            word_count=150,
            meets_length_req=True,
            is_english=True,
            is_valid=True
        )
        
        assert isinstance(pre_result.word_count, int)
        assert isinstance(pre_result.meets_length_req, bool)
        assert isinstance(pre_result.is_english, bool)
        assert isinstance(pre_result.is_valid, bool)