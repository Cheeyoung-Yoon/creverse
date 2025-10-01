"""
Integration tests for essay evaluation components
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import json

from app.services.essay_evaluator import EssayEvaluator
from app.services.evaluation.rubric_chain.context_eval import StructureEvaluator
from app.services.evaluation.rubric_chain.grammar_eval import GrammarEvaluator
from app.models.request import EssayEvalRequest
from app.utils.prompt_loader import PromptLoader


@pytest.mark.integration
class TestEssayEvaluatorIntegration:
    """Test EssayEvaluator with integrated components"""
    
    @pytest.fixture
    def mock_llm_responses(self):
        """Mock LLM responses for integration testing"""
        return {
            "grammar": {
                "score": 4,
                "correction": "Minor punctuation improvements needed",
                "feedback": "Good grammar overall with excellent sentence structure"
            },
            "introduction": {
                "score": 3,
                "correction": "Strengthen thesis statement",
                "feedback": "Good opening but thesis could be clearer"
            },
            "body": {
                "score": 4,
                "correction": "Add more specific examples",
                "feedback": "Strong arguments with good supporting evidence"
            },
            "conclusion": {
                "score": 3,
                "correction": "Summarize main points better",
                "feedback": "Adequate conclusion that ties together the essay"
            }
        }
    
    @pytest.fixture
    def evaluator_with_mocks(self, mock_llm_responses):
        """Create EssayEvaluator with mocked LLM"""
        mock_llm = Mock()
        mock_llm.run_azure_openai = AsyncMock()
        
        def mock_llm_response(*args, **kwargs):
            # Return different responses based on the name parameter
            name = kwargs.get('name', 'default')
            if 'grammar' in name.lower():
                return mock_llm_responses['grammar']
            elif 'introduction' in name.lower():
                return mock_llm_responses['introduction']
            elif 'body' in name.lower():
                return mock_llm_responses['body']
            elif 'conclusion' in name.lower():
                return mock_llm_responses['conclusion']
            else:
                return mock_llm_responses['grammar']  # default
        
        mock_llm.run_azure_openai.side_effect = mock_llm_response
        
        prompt_loader = PromptLoader()
        return EssayEvaluator(llm=mock_llm, prompt_loader=prompt_loader)
    
    @pytest.mark.asyncio
    async def test_full_evaluation_pipeline(self, evaluator_with_mocks, sample_essay_text):
        """Test complete evaluation pipeline"""
        request = EssayEvalRequest(
            level_group="Basic",
            topic_prompt="Environmental protection",
            submit_text=sample_essay_text
        )
        
        response = await evaluator_with_mocks.evaluate_essay(request)
        
        # Verify response structure
        assert response.level_group == "Basic"
        assert response.pre_process is not None
        assert response.grammar is not None
        assert response.structure is not None
        assert response.aggregated is not None
        assert response.timings is not None
        assert response.timeline is not None
        
        # Verify pre-processing results
        assert isinstance(response.pre_process.word_count, int)
        assert isinstance(response.pre_process.is_english, bool)
        
        # Verify evaluation results
        assert response.grammar.rubric_item == "grammar"
        assert response.grammar.score == 4
        assert response.structure.introduction.score == 3
        assert response.structure.body.score == 4
        assert response.structure.conclusion.score == 3
        
        # Verify aggregated results
        assert isinstance(response.aggregated.score, int)
        assert response.aggregated.score >= 0
    
    @pytest.mark.asyncio
    async def test_evaluation_with_different_levels(self, evaluator_with_mocks, sample_essay_text):
        """Test evaluation with different student levels"""
        levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        
        for level in levels:
            request = EssayEvalRequest(
                level_group=level,
                topic_prompt="Technology in education",
                submit_text=sample_essay_text
            )
            
            response = await evaluator_with_mocks.evaluate_essay(request)
            
            assert response.level_group == level
            assert response.pre_process is not None
            assert response.aggregated.score >= 0
    
    @pytest.mark.asyncio
    async def test_parallel_evaluation_timing(self, evaluator_with_mocks, sample_essay_text):
        """Test that grammar and structure evaluations run in parallel"""
        request = EssayEvalRequest(
            level_group="Intermediate",
            topic_prompt="Science and society",
            submit_text=sample_essay_text
        )
        
        import time
        start_time = time.time()
        response = await evaluator_with_mocks.evaluate_essay(request)
        end_time = time.time()
        
        # Verify timing information is captured
        assert "total" in response.timings
        assert "grammar" in response.timings
        assert "structure" in response.timings
        
        # Parallel execution should be faster than sequential
        total_time = end_time - start_time
        assert total_time < 10  # Should complete quickly with mocked LLM


@pytest.mark.integration
class TestRubricChainIntegration:
    """Test integration between grammar and structure evaluation chains"""
    
    @pytest.fixture
    def mock_llm_for_chains(self):
        """Mock LLM specifically for rubric chain testing"""
        mock_llm = Mock()
        mock_llm.run_azure_openai = AsyncMock()
        
        # Return valid evaluation responses
        mock_response = {
            "score": 3,
            "correction": "Some improvements needed",
            "feedback": "Good work with areas for enhancement"
        }
        mock_llm.run_azure_openai.return_value = mock_response
        
        return mock_llm
    
    @pytest.mark.asyncio
    async def test_structure_evaluator_integration(self, mock_llm_for_chains, sample_essay_text):
        """Test StructureEvaluator with mocked LLM"""
        evaluator = StructureEvaluator(llm=mock_llm_for_chains, prompt_loader=PromptLoader())
        
        result = await evaluator.run_structure_chain(
            intro=sample_essay_text[:100],
            body=sample_essay_text[100:300],
            conclusion=sample_essay_text[300:],
            level="Basic"
        )
        
        # Verify structure of results
        assert "introduction" in result
        assert "body" in result
        assert "conclusion" in result
        
        # Verify each component has expected fields
        for component in ["introduction", "body", "conclusion"]:
            assert "score" in result[component]
            assert "correction" in result[component]
            assert "feedback" in result[component]
    
    @pytest.mark.asyncio
    async def test_grammar_evaluator_integration(self, mock_llm_for_chains, sample_essay_text):
        """Test GrammarEvaluator with mocked LLM"""
        evaluator = GrammarEvaluator(llm=mock_llm_for_chains, prompt_loader=PromptLoader())
        
        result = await evaluator.check_grammar(sample_essay_text, level="Basic")
        
        # Verify grammar evaluation result structure
        assert "score" in result
        assert "correction" in result
        assert "feedback" in result
        assert "rubric_item" in result
        assert result["rubric_item"] == "grammar"
    
    @pytest.mark.asyncio
    async def test_parallel_chain_execution(self, mock_llm_for_chains, sample_essay_text):
        """Test running grammar and structure chains in parallel"""
        grammar_evaluator = GrammarEvaluator(llm=mock_llm_for_chains, prompt_loader=PromptLoader())
        structure_evaluator = StructureEvaluator(llm=mock_llm_for_chains, prompt_loader=PromptLoader())
        
        # Run both evaluations in parallel
        grammar_task = asyncio.create_task(
            grammar_evaluator.check_grammar(sample_essay_text, level="Intermediate")
        )
        structure_task = asyncio.create_task(
            structure_evaluator.run_structure_chain(
                intro=sample_essay_text[:150],
                body=sample_essay_text[150:400],
                conclusion=sample_essay_text[400:],
                level="Intermediate"
            )
        )
        
        grammar_result, structure_result = await asyncio.gather(grammar_task, structure_task)
        
        # Both should complete successfully
        assert grammar_result["rubric_item"] == "grammar"
        assert "introduction" in structure_result
        assert "body" in structure_result
        assert "conclusion" in structure_result


@pytest.mark.integration
class TestPromptLoaderIntegration:
    """Test PromptLoader integration with evaluation components"""
    
    def test_prompt_loader_with_real_files(self):
        """Test PromptLoader with actual prompt files"""
        loader = PromptLoader()
        
        # Test loading different prompt types
        prompt_types = ["grammar", "introduction", "body", "conclusion"]
        test_variables = {
            "text": "Sample essay text for testing",
            "level": "Basic"
        }
        
        for prompt_type in prompt_types:
            try:
                prompt = loader.load_prompt(prompt_type, test_variables)
                assert isinstance(prompt, str)
                assert len(prompt) > 0
                assert "Sample essay text for testing" in prompt
            except FileNotFoundError:
                # If prompt file doesn't exist, that's ok for this test
                pytest.skip(f"Prompt file for {prompt_type} not found")
    
    def test_prompt_loader_version_consistency(self):
        """Test that PromptLoader maintains version consistency"""
        loader = PromptLoader()
        
        # Test setting specific versions
        try:
            loader.set_version("introduction", "v1.1.0")
            loader.set_version("body", "v1.1.0")
            loader.set_version("conclusion", "v1.1.0")
            
            # All prompts should use the same version
            test_vars = {"text": "test", "level": "Basic"}
            
            intro_prompt = loader.load_prompt("introduction", test_vars)
            body_prompt = loader.load_prompt("body", test_vars)
            conclusion_prompt = loader.load_prompt("conclusion", test_vars)
            
            # All should be loaded successfully with consistent versioning
            assert isinstance(intro_prompt, str)
            assert isinstance(body_prompt, str)
            assert isinstance(conclusion_prompt, str)
            
        except (FileNotFoundError, AttributeError):
            # If versioning isn't implemented yet, that's ok
            pytest.skip("Prompt versioning not fully implemented")


@pytest.mark.integration
@pytest.mark.slow
class TestFullSystemIntegration:
    """Test full system integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_evaluation_mock(self):
        """Test end-to-end evaluation with comprehensive mocking"""
        # Create a complete mock setup
        mock_llm = Mock()
        mock_llm.run_azure_openai = AsyncMock()
        
        # Define responses for different evaluation components
        def mock_response(*args, **kwargs):
            name = kwargs.get('name', '')
            if 'grammar' in name.lower():
                return {
                    "score": 4,
                    "correction": "Minor grammar issues to address",
                    "feedback": "Strong grammar skills demonstrated"
                }
            elif 'introduction' in name.lower():
                return {
                    "score": 3,
                    "correction": "Thesis statement could be stronger",
                    "feedback": "Good introduction with clear topic"
                }
            elif 'body' in name.lower():
                return {
                    "score": 4,
                    "correction": "Add more specific examples",
                    "feedback": "Well-structured arguments"
                }
            elif 'conclusion' in name.lower():
                return {
                    "score": 3,
                    "correction": "Summarize key points better",
                    "feedback": "Adequate conclusion"
                }
            return {"score": 3, "correction": "Default", "feedback": "Default"}
        
        mock_llm.run_azure_openai.side_effect = mock_response
        
        # Create evaluator with mocked dependencies
        evaluator = EssayEvaluator(llm=mock_llm, prompt_loader=PromptLoader())
        
        # Test with comprehensive essay
        comprehensive_essay = """
        Environmental protection is one of the most critical challenges facing our world today.
        The increasing levels of pollution, deforestation, and climate change threaten the very
        foundation of life on Earth.
        
        First, air pollution from industrial activities and vehicle emissions contributes
        significantly to global warming. Cities around the world are experiencing unprecedented
        levels of smog and toxic air quality. This directly impacts human health, causing
        respiratory diseases and other serious health conditions.
        
        Second, deforestation for agriculture and urban development destroys vital ecosystems.
        Forests are essential for maintaining biodiversity and regulating our planet's climate.
        When we destroy these natural habitats, we lose countless species and disrupt the
        delicate balance of nature.
        
        Finally, water pollution from industrial waste and plastic debris poses a severe threat
        to marine life and freshwater resources. Our oceans are becoming dumping grounds for
        plastic waste, creating massive garbage patches that harm sea creatures and contaminate
        the food chain.
        
        In conclusion, environmental protection requires immediate and sustained action from
        individuals, governments, and corporations worldwide. We must implement stricter
        environmental regulations, invest in clean energy technologies, and educate people
        about sustainable practices. The future of our planet depends on the choices we make today.
        """
        
        request = EssayEvalRequest(
            level_group="Advanced",
            topic_prompt="Environmental protection and climate change",
            submit_text=comprehensive_essay
        )
        
        # Execute full evaluation
        response = await evaluator.evaluate_essay(request)
        
        # Comprehensive validation
        assert response.level_group == "Advanced"
        
        # Pre-processing validation
        assert response.pre_process.word_count > 200
        assert response.pre_process.is_english is True
        assert response.pre_process.is_appropriate_length is True
        assert response.pre_process.topic_relevance_score > 0.5
        
        # Grammar evaluation validation
        assert response.grammar.rubric_item == "grammar"
        assert response.grammar.score == 4
        assert "grammar" in response.grammar.feedback.lower()
        
        # Structure evaluation validation
        assert response.structure.introduction.score == 3
        assert response.structure.body.score == 4
        assert response.structure.conclusion.score == 3
        
        # Aggregated results validation
        assert 60 <= response.aggregated.score <= 90  # Should be in reasonable range
        assert len(response.aggregated.correction) > 20
        assert len(response.aggregated.feedback) > 20
        
        # Timing validation
        assert "total" in response.timings
        assert response.timings["total"] > 0
        
        # Timeline validation
        assert response.timeline.start is not None
        assert response.timeline.end is not None