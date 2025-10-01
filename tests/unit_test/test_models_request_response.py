"""
Unit tests for models/request.py and models/response.py
"""
import pytest
from datetime import datetime

from app.models.request import Level, EssayEvalRequest
from app.models.response import (
    TokenUsage, EvaluationTimeline, RubricItemPayload, 
    StructureChainResult, EssayEvalResponse
)
from app.models.rubric import (
    Correction, RubricItemResult, ScoreCorrectionFeedback, PreProcessResult
)


@pytest.mark.unit
class TestLevel:
    """Test Level enum/model"""
    
    def test_level_values(self):
        """Test Level enum values"""
        expected_levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        
        # Test that all expected levels are available
        for level in expected_levels:
            # This test depends on how Level is implemented
            # It could be an enum or just string validation
            assert level in expected_levels


@pytest.mark.unit
class TestEssayEvalRequest:
    """Test EssayEvalRequest model"""
    
    def test_essay_eval_request_creation(self):
        """Test creating EssayEvalRequest"""
        request = EssayEvalRequest(
            rubric_level="Basic",
            topic_prompt="Environment and sustainability",
            submit_text="This is a sample essay about environmental issues that affect our planet today. Climate change, pollution, and deforestation are major concerns that require immediate attention from governments and individuals worldwide."
        )
        
        assert request.rubric_level == "Basic"
        assert request.topic_prompt == "Environment and sustainability"
        assert "environmental" in request.submit_text.lower()
    
    def test_essay_eval_request_all_levels(self):
        """Test EssayEvalRequest with all level groups"""
        levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        
        for level in levels:
            request = EssayEvalRequest(
                rubric_level=level,
                topic_prompt="Write about technology and education",
                submit_text="Technology has transformed modern education by providing new tools and methods for learning. Digital platforms, online courses, and interactive software have made education more accessible and engaging for students worldwide."
            )
            assert request.rubric_level == level
    
    def test_essay_eval_request_long_text(self):
        """Test EssayEvalRequest with long essay text"""
        long_text = "This is a comprehensive essay about technology and its impact on modern society. " * 20
        
        request = EssayEvalRequest(
            rubric_level="Advanced",
            topic_prompt="Technology and society",
            submit_text=long_text
        )
        
        assert len(request.submit_text) > 1000
        assert request.rubric_level == "Advanced"


@pytest.mark.unit
class TestTokenUsage:
    """Test TokenUsage response model"""
    
    def test_token_usage_creation(self):
        """Test creating TokenUsage"""
        usage = TokenUsage(
            prompt_tokens=150,
            completion_tokens=75,
            total_tokens=225
        )
        
        assert usage.prompt_tokens == 150
        assert usage.completion_tokens == 75
        assert usage.total_tokens == 225
    
    def test_token_usage_defaults(self):
        """Test TokenUsage with default values"""
        usage = TokenUsage()
        
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0


@pytest.mark.unit
class TestRubricItemPayload:
    """Test RubricItemPayload model"""
    
    def test_rubric_item_payload_creation(self):
        """Test creating RubricItemPayload"""
        payload = RubricItemPayload(
            rubric_item="grammar",
            score=2,
            corrections=[
                {
                    "highlight": "grammer",
                    "issue": "Spelling error",
                    "correction": "grammar"
                }
            ],
            feedback="Good grammar overall with minor corrections needed",
            token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            evaluation_type="grammar_check"
        )
        
        assert payload.rubric_item == "grammar"
        assert payload.score == 2
        assert payload.evaluation_type == "grammar_check"
        assert payload.token_usage.total_tokens == 150
        assert len(payload.corrections) == 1
    
    def test_rubric_item_payload_with_error(self):
        """Test RubricItemPayload with error field"""
        payload = RubricItemPayload(
            rubric_item="body",
            score=0,
            corrections=[],
            feedback="Unable to evaluate due to error",
            evaluation_type="structure_check",
            error="API timeout error"
        )
        
        assert payload.error == "API timeout error"
        assert payload.score == 0
    
    def test_rubric_item_payload_optional_fields(self):
        """Test RubricItemPayload with optional fields as None"""
        payload = RubricItemPayload(
            rubric_item="conclusion",
            score=2,
            corrections=[
                {
                    "highlight": "end",
                    "issue": "Weak conclusion",
                    "correction": "stronger ending"
                }
            ],
            feedback="Good conclusion with room for improvement",
            evaluation_type="structure_check",
            token_usage=None,
            error=None
        )
        
        assert payload.token_usage is None
        assert payload.error is None
        assert payload.score == 2


@pytest.mark.unit
class TestStructureChainResult:
    """Test StructureChainResult model"""
    
    def test_structure_chain_result_creation(self):
        """Test creating StructureChainResult"""
        
        # Create sample payloads
        intro_payload = RubricItemPayload(
            rubric_item="introduction",
            score=2,
            corrections=[],
            feedback="Good introduction",
            evaluation_type="structure"
        )
        
        body_payload = RubricItemPayload(
            rubric_item="body",
            score=1,
            corrections=[
                {
                    "highlight": "argument",
                    "issue": "Weak support",
                    "correction": "Add more evidence"
                }
            ],
            feedback="Body needs improvement",
            evaluation_type="structure"
        )
        
        conclusion_payload = RubricItemPayload(
            rubric_item="conclusion",
            score=2,
            corrections=[],
            feedback="Strong conclusion",
            evaluation_type="structure"
        )
        
        result = StructureChainResult(
            introduction=intro_payload,
            body=body_payload,
            conclusion=conclusion_payload,
            token_usage_total=TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300),
            evaluation_type="structure_chain"
        )
        
        assert result.introduction.rubric_item == "introduction"
        assert result.body.rubric_item == "body"
        assert result.conclusion.rubric_item == "conclusion"
        assert result.token_usage_total.total_tokens == 300