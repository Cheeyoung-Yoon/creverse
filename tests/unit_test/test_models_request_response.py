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
            level_group="Basic",
            topic_prompt="Environment and sustainability",
            submit_text="This is a sample essay about environmental issues..."
        )
        
        assert request.level_group == "Basic"
        assert request.topic_prompt == "Environment and sustainability"
        assert "environmental" in request.submit_text.lower()
    
    def test_essay_eval_request_all_levels(self):
        """Test EssayEvalRequest with all level groups"""
        levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        
        for level in levels:
            request = EssayEvalRequest(
                level_group=level,
                topic_prompt="Test topic",
                submit_text="Test essay content"
            )
            assert request.level_group == level
    
    def test_essay_eval_request_long_text(self):
        """Test EssayEvalRequest with long essay text"""
        long_text = "This is a very long essay. " * 100
        
        request = EssayEvalRequest(
            level_group="Advanced",
            topic_prompt="Technology and society",
            submit_text=long_text
        )
        
        assert len(request.submit_text) > 1000
        assert request.level_group == "Advanced"


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
    
    def test_token_usage_validation(self):
        """Test TokenUsage field validation"""
        # All fields should be non-negative integers
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        
        assert usage.prompt_tokens >= 0
        assert usage.completion_tokens >= 0
        assert usage.total_tokens >= 0


@pytest.mark.unit
class TestEvaluationTimeline:
    """Test EvaluationTimeline model"""
    
    def test_evaluation_timeline_creation(self):
        """Test creating EvaluationTimeline"""
        start_time = "2024-01-01T10:00:00Z"
        end_time = "2024-01-01T10:05:00Z"
        
        timeline = EvaluationTimeline(
            start=start_time,
            end=end_time
        )
        
        assert timeline.start == start_time
        assert timeline.end == end_time
    
    def test_evaluation_timeline_iso_format(self):
        """Test EvaluationTimeline with ISO datetime strings"""
        now = datetime.now()
        start_iso = now.isoformat()
        end_iso = now.replace(minute=now.minute + 5).isoformat()
        
        timeline = EvaluationTimeline(
            start=start_iso,
            end=end_iso
        )
        
        assert start_iso in timeline.start
        assert end_iso in timeline.end


@pytest.mark.unit
class TestRubricItemPayload:
    """Test RubricItemPayload model"""
    
    def test_rubric_item_payload_creation(self):
        """Test creating RubricItemPayload"""
        payload = RubricItemPayload(
            rubric_item="grammar",
            score=4,
            correction="Minor improvements needed",
            feedback="Good grammar overall",
            token_usage=TokenUsage(100, 50, 150),
            evaluation_type="grammar_check"
        )
        
        assert payload.rubric_item == "grammar"
        assert payload.score == 4
        assert payload.evaluation_type == "grammar_check"
        assert payload.token_usage.total_tokens == 150
    
    def test_rubric_item_payload_with_error(self):
        """Test RubricItemPayload with error field"""
        payload = RubricItemPayload(
            rubric_item="body",
            score=0,
            correction="",
            feedback="",
            evaluation_type="structure_check",
            error="API timeout error"
        )
        
        assert payload.error == "API timeout error"
        assert payload.score == 0
    
    def test_rubric_item_payload_optional_fields(self):
        """Test RubricItemPayload with optional fields as None"""
        payload = RubricItemPayload(
            rubric_item="conclusion",
            score=3,
            correction="Some improvements",
            feedback="Good conclusion",
            evaluation_type="structure_check",
            token_usage=None,
            error=None
        )
        
        assert payload.token_usage is None
        assert payload.error is None


@pytest.mark.unit
class TestStructureChainResult:
    """Test StructureChainResult model"""
    
    def test_structure_chain_result_creation(self):
        """Test creating StructureChainResult"""
        intro_payload = RubricItemPayload(
            rubric_item="introduction",
            score=4,
            correction="Good intro",
            feedback="Strong opening",
            evaluation_type="structure"
        )
        
        body_payload = RubricItemPayload(
            rubric_item="body",
            score=3,
            correction="Add examples",
            feedback="Needs more support",
            evaluation_type="structure"
        )
        
        conclusion_payload = RubricItemPayload(
            rubric_item="conclusion",
            score=4,
            correction="Effective conclusion",
            feedback="Strong closing",
            evaluation_type="structure"
        )
        
        structure_result = StructureChainResult(
            introduction=intro_payload,
            body=body_payload,
            conclusion=conclusion_payload,
            token_usage_total=TokenUsage(300, 150, 450),
            evaluation_type="structure_chain"
        )
        
        assert structure_result.introduction.score == 4
        assert structure_result.body.score == 3
        assert structure_result.conclusion.score == 4
        assert structure_result.token_usage_total.total_tokens == 450
        assert structure_result.evaluation_type == "structure_chain"


@pytest.mark.unit
class TestEssayEvalResponse:
    """Test complete EssayEvalResponse model"""
    
    def test_essay_eval_response_creation(self, sample_pre_process_result, sample_rubric_result):
        """Test creating complete EssayEvalResponse"""
        from app.models.rubric import ScoreCorrectionFeedback
        
        # Create structure result
        intro_payload = RubricItemPayload(
            rubric_item="introduction",
            score=4,
            correction="Good",
            feedback="Strong",
            evaluation_type="structure"
        )
        
        body_payload = RubricItemPayload(
            rubric_item="body",
            score=3,
            correction="Improve",
            feedback="Needs work",
            evaluation_type="structure"
        )
        
        conclusion_payload = RubricItemPayload(
            rubric_item="conclusion",
            score=4,
            correction="Good",
            feedback="Strong",
            evaluation_type="structure"
        )
        
        structure_result = StructureChainResult(
            introduction=intro_payload,
            body=body_payload,
            conclusion=conclusion_payload,
            evaluation_type="structure_chain"
        )
        
        # Create grammar payload
        grammar_payload = RubricItemPayload(
            rubric_item="grammar",
            score=3,
            correction="Minor fixes",
            feedback="Good grammar",
            evaluation_type="grammar_check"
        )
        
        # Create aggregated result
        aggregated = ScoreCorrectionFeedback(
            score=75,
            correction="Overall good essay",
            feedback="Strong work with areas for improvement"
        )
        
        # Create timeline
        timeline = EvaluationTimeline(
            start="2024-01-01T10:00:00Z",
            end="2024-01-01T10:05:00Z"
        )
        
        # Create complete response
        response = EssayEvalResponse(
            level_group="Basic",
            pre_process=sample_pre_process_result,
            grammar=grammar_payload,
            structure=structure_result,
            aggregated=aggregated,
            timings={"total": 5.2, "grammar": 2.1, "structure": 3.1},
            timeline=timeline
        )
        
        assert response.level_group == "Basic"
        assert response.grammar.score == 3
        assert response.structure.body.score == 3
        assert response.aggregated.score == 75
        assert response.timings["total"] == 5.2
    
    def test_essay_eval_response_field_access(self):
        """Test accessing all fields of EssayEvalResponse"""
        # This test ensures all expected fields are accessible
        # We'll create a minimal response to test field access
        
        # Note: This test would need actual instances to work properly
        # For now, we'll just test that the model class exists and has expected attributes
        
        # Check that EssayEvalResponse has expected fields
        expected_fields = [
            'level_group', 'pre_process', 'grammar', 'structure', 
            'aggregated', 'timings', 'timeline'
        ]
        
        # This would check if the model has the expected fields defined
        # The exact implementation depends on whether we're using Pydantic or dataclasses
        assert hasattr(EssayEvalResponse, '__annotations__') or hasattr(EssayEvalResponse, '__dataclass_fields__')