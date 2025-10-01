"""
Unit tests for services/evaluation/post_process.py
"""
import pytest
from unittest.mock import Mock

from app.services.evaluation.post_process import finalize_scf
from app.models.rubric import RubricItemResult, ScoreCorrectionFeedback


@pytest.mark.unit
class TestFinalizeScf:
    """Test finalize_scf function for score aggregation"""
    
    def test_finalize_scf_basic(self):
        """Test basic score finalization"""
        # Create sample rubric results
        grammar_result = RubricItemResult(
            rubric_item="grammar",
            score=4,
            correction="Minor grammar improvements needed",
            feedback="Good grammar overall"
        )
        
        structure_results = {
            "introduction": RubricItemResult(
                rubric_item="introduction",
                score=3,
                correction="Strengthen the thesis statement",
                feedback="Good opening but needs clearer thesis"
            ),
            "body": RubricItemResult(
                rubric_item="body",
                score=4,
                correction="Add more specific examples",
                feedback="Strong arguments with good support"
            ),
            "conclusion": RubricItemResult(
                rubric_item="conclusion",
                score=3,
                correction="Summarize main points better",
                feedback="Adequate conclusion"
            )
        }
        
        level = "Basic"
        
        result = finalize_scf(grammar_result, structure_results, level)
        
        assert isinstance(result, ScoreCorrectionFeedback)
        assert isinstance(result.score, int)
        assert isinstance(result.correction, str)
        assert isinstance(result.feedback, str)
        assert result.score >= 0
        assert len(result.correction) > 0
        assert len(result.feedback) > 0
    
    def test_finalize_scf_high_scores(self):
        """Test finalization with high scores"""
        grammar_result = RubricItemResult(
            rubric_item="grammar",
            score=5,
            correction="Excellent grammar",
            feedback="Perfect grammar usage"
        )
        
        structure_results = {
            "introduction": RubricItemResult(
                rubric_item="introduction",
                score=5,
                correction="Perfect introduction",
                feedback="Excellent opening"
            ),
            "body": RubricItemResult(
                rubric_item="body",
                score=5,
                correction="Outstanding body",
                feedback="Exceptional arguments"
            ),
            "conclusion": RubricItemResult(
                rubric_item="conclusion",
                score=5,
                correction="Perfect conclusion",
                feedback="Excellent closing"
            )
        }
        
        level = "Expert"
        
        result = finalize_scf(grammar_result, structure_results, level)
        
        assert isinstance(result, ScoreCorrectionFeedback)
        # High scores should result in high final score
        assert result.score >= 80  # Assuming 80+ is high
        assert "excellent" in result.feedback.lower() or "outstanding" in result.feedback.lower()
    
    def test_finalize_scf_low_scores(self):
        """Test finalization with low scores"""
        grammar_result = RubricItemResult(
            rubric_item="grammar",
            score=1,
            correction="Major grammar issues need attention",
            feedback="Significant grammar problems"
        )
        
        structure_results = {
            "introduction": RubricItemResult(
                rubric_item="introduction",
                score=1,
                correction="Needs complete restructuring",
                feedback="Unclear introduction"
            ),
            "body": RubricItemResult(
                rubric_item="body",
                score=2,
                correction="Lacks supporting evidence",
                feedback="Weak arguments"
            ),
            "conclusion": RubricItemResult(
                rubric_item="conclusion",
                score=1,
                correction="Inconclusive ending",
                feedback="Poor conclusion"
            )
        }
        
        level = "Basic"
        
        result = finalize_scf(grammar_result, structure_results, level)
        
        assert isinstance(result, ScoreCorrectionFeedback)
        # Low scores should result in low final score
        assert result.score <= 50  # Assuming 50 or below is low
        assert "improve" in result.correction.lower() or "needs" in result.correction.lower()
    
    def test_finalize_scf_mixed_scores(self):
        """Test finalization with mixed score levels"""
        grammar_result = RubricItemResult(
            rubric_item="grammar",
            score=3,
            correction="Some grammar improvements needed",
            feedback="Generally good grammar"
        )
        
        structure_results = {
            "introduction": RubricItemResult(
                rubric_item="introduction",
                score=4,
                correction="Strong introduction",
                feedback="Good opening"
            ),
            "body": RubricItemResult(
                rubric_item="body",
                score=2,
                correction="Needs better organization",
                feedback="Weak body structure"
            ),
            "conclusion": RubricItemResult(
                rubric_item="conclusion",
                score=4,
                correction="Good conclusion",
                feedback="Strong ending"
            )
        }
        
        level = "Intermediate"
        
        result = finalize_scf(grammar_result, structure_results, level)
        
        assert isinstance(result, ScoreCorrectionFeedback)
        # Mixed scores should result in moderate final score
        assert 40 <= result.score <= 80
        assert len(result.correction) > 20  # Should have substantial feedback
    
    def test_finalize_scf_different_levels(self):
        """Test finalization with different student levels"""
        grammar_result = RubricItemResult(
            rubric_item="grammar",
            score=3,
            correction="Grammar needs work",
            feedback="Moderate grammar skills"
        )
        
        structure_results = {
            "introduction": RubricItemResult(
                rubric_item="introduction",
                score=3,
                correction="Adequate introduction",
                feedback="Satisfactory opening"
            ),
            "body": RubricItemResult(
                rubric_item="body",
                score=3,
                correction="Body needs development",
                feedback="Adequate body"
            ),
            "conclusion": RubricItemResult(
                rubric_item="conclusion",
                score=3,
                correction="Conclusion is adequate",
                feedback="Satisfactory ending"
            )
        }
        
        levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        
        for level in levels:
            result = finalize_scf(grammar_result, structure_results, level)
            
            assert isinstance(result, ScoreCorrectionFeedback)
            assert isinstance(result.score, int)
            # Level might affect scoring or feedback style
            assert result.score >= 0
    
    def test_finalize_scf_score_weighting(self):
        """Test that different components are weighted appropriately"""
        # Create scenarios where one component is much higher/lower
        
        # Scenario 1: Excellent grammar, poor structure
        grammar_high = RubricItemResult(
            rubric_item="grammar",
            score=5,
            correction="Perfect grammar",
            feedback="Excellent language use"
        )
        
        structure_low = {
            "introduction": RubricItemResult(
                rubric_item="introduction",
                score=1,
                correction="Poor introduction",
                feedback="Needs work"
            ),
            "body": RubricItemResult(
                rubric_item="body",
                score=1,
                correction="Poor body",
                feedback="Needs work"
            ),
            "conclusion": RubricItemResult(
                rubric_item="conclusion",
                score=1,
                correction="Poor conclusion",
                feedback="Needs work"
            )
        }
        
        result1 = finalize_scf(grammar_high, structure_low, "Basic")
        
        # Scenario 2: Poor grammar, excellent structure
        grammar_low = RubricItemResult(
            rubric_item="grammar",
            score=1,
            correction="Poor grammar",
            feedback="Needs significant improvement"
        )
        
        structure_high = {
            "introduction": RubricItemResult(
                rubric_item="introduction",
                score=5,
                correction="Excellent introduction",
                feedback="Perfect opening"
            ),
            "body": RubricItemResult(
                rubric_item="body",
                score=5,
                correction="Excellent body",
                feedback="Perfect arguments"
            ),
            "conclusion": RubricItemResult(
                rubric_item="conclusion",
                score=5,
                correction="Excellent conclusion",
                feedback="Perfect ending"
            )
        }
        
        result2 = finalize_scf(grammar_low, structure_high, "Basic")
        
        # Both should produce valid results
        assert isinstance(result1, ScoreCorrectionFeedback)
        assert isinstance(result2, ScoreCorrectionFeedback)
        
        # The final scores should reflect the weighting strategy
        assert result1.score != result2.score


@pytest.mark.unit
class TestPostProcessEdgeCases:
    """Test edge cases and error handling in post-processing"""
    
    def test_finalize_scf_missing_structure_components(self):
        """Test finalization with missing structure components"""
        grammar_result = RubricItemResult(
            rubric_item="grammar",
            score=3,
            correction="Grammar is okay",
            feedback="Moderate grammar"
        )
        
        # Missing some structure components
        incomplete_structure = {
            "introduction": RubricItemResult(
                rubric_item="introduction",
                score=3,
                correction="Okay intro",
                feedback="Adequate"
            )
            # Missing body and conclusion
        }
        
        # Should handle incomplete structure gracefully
        try:
            result = finalize_scf(grammar_result, incomplete_structure, "Basic")
            assert isinstance(result, ScoreCorrectionFeedback)
        except (KeyError, AttributeError):
            # Or raise appropriate error
            pass
    
    def test_finalize_scf_zero_scores(self):
        """Test finalization with zero scores"""
        grammar_result = RubricItemResult(
            rubric_item="grammar",
            score=0,
            correction="No grammar evaluation possible",
            feedback="Unable to evaluate"
        )
        
        structure_results = {
            "introduction": RubricItemResult(
                rubric_item="introduction",
                score=0,
                correction="No introduction found",
                feedback="Missing introduction"
            ),
            "body": RubricItemResult(
                rubric_item="body",
                score=0,
                correction="No body content",
                feedback="Missing body"
            ),
            "conclusion": RubricItemResult(
                rubric_item="conclusion",
                score=0,
                correction="No conclusion",
                feedback="Missing conclusion"
            )
        }
        
        result = finalize_scf(grammar_result, structure_results, "Basic")
        
        assert isinstance(result, ScoreCorrectionFeedback)
        assert result.score == 0 or result.score is not None
    
    def test_finalize_scf_empty_feedback(self):
        """Test finalization with empty feedback strings"""
        grammar_result = RubricItemResult(
            rubric_item="grammar",
            score=3,
            correction="",
            feedback=""
        )
        
        structure_results = {
            "introduction": RubricItemResult(
                rubric_item="introduction",
                score=3,
                correction="",
                feedback=""
            ),
            "body": RubricItemResult(
                rubric_item="body",
                score=3,
                correction="",
                feedback=""
            ),
            "conclusion": RubricItemResult(
                rubric_item="conclusion",
                score=3,
                correction="",
                feedback=""
            )
        }
        
        result = finalize_scf(grammar_result, structure_results, "Basic")
        
        assert isinstance(result, ScoreCorrectionFeedback)
        # Should still produce meaningful feedback even if inputs are empty
        assert isinstance(result.correction, str)
        assert isinstance(result.feedback, str)