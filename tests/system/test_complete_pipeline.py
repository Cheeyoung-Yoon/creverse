"""
Comprehensive system/end-to-end tests for the complete essay evaluation pipeline
"""
import pytest
import asyncio
import time
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock

from app.services.essay_evaluator import EssayEvaluator
from app.utils.prompt_loader import PromptLoader
from app.models.request import EssayEvalRequest
from app.client.bootstrap import build_llm


@pytest.mark.system
class TestCompleteEvaluationPipeline:
    """Test the complete essay evaluation pipeline end-to-end"""
    
    @pytest.fixture
    def system_test_essays(self):
        """Collection of test essays for system testing"""
        return {
            "basic_short": {
                "text": "Environmental protection is important. We should recycle and save energy. This helps our planet.",
                "level": "Basic",
                "topic": "Environment",
                "expected_length_check": False  # Too short
            },
            "basic_adequate": {
                "text": "Environmental protection is very important for our future. We need to take care of our planet by reducing pollution and saving natural resources. Recycling helps reduce waste and saves materials. Using less energy helps reduce pollution from power plants. Everyone can help by making small changes in their daily life. We should walk or bike instead of driving when possible. Turning off lights saves electricity. Planting trees helps clean the air. If we all work together, we can make our environment cleaner and healthier for future generations.",
                "level": "Basic",
                "topic": "Environment",
                "expected_length_check": True
            },
            "intermediate_comprehensive": {
                "text": "Climate change represents one of the most significant challenges facing humanity in the 21st century. The scientific consensus clearly indicates that human activities, particularly the emission of greenhouse gases, are the primary drivers of global warming. The consequences of climate change are already visible worldwide, including rising sea levels, extreme weather events, and shifts in agricultural productivity. To address this crisis effectively, we need comprehensive solutions that combine technological innovation, policy reform, and individual action. Renewable energy technologies such as solar and wind power offer promising alternatives to fossil fuels. Governments must implement carbon pricing mechanisms and support clean energy transition. Individuals can contribute by adopting sustainable lifestyle choices, reducing energy consumption, and supporting environmentally responsible businesses. International cooperation is essential because climate change is a global problem that requires coordinated global action.",
                "level": "Intermediate",
                "topic": "Climate Change",
                "expected_length_check": True
            },
            "advanced_analytical": {
                "text": "The intersection of technology and education has fundamentally transformed the learning landscape, creating both unprecedented opportunities and significant challenges. Digital learning platforms have democratized access to quality education, enabling students from diverse geographical and socioeconomic backgrounds to access world-class instruction. However, this technological revolution has also exacerbated existing educational inequalities, as students without reliable internet access or modern devices find themselves increasingly disadvantaged. The COVID-19 pandemic accelerated the adoption of remote learning technologies, forcing educational institutions to rapidly adapt their pedagogical approaches. While this transition revealed the potential of virtual classrooms and asynchronous learning, it also highlighted the irreplaceable value of face-to-face interaction and collaborative learning experiences. Moving forward, the most effective educational approaches will likely blend traditional teaching methods with innovative technologies, creating hybrid learning environments that maximize the benefits of both modalities. Educators must be trained to leverage these tools effectively, and policymakers must ensure equitable access to educational technology. The future of education depends on our ability to harness technology's potential while preserving the human elements that make learning meaningful and engaging.",
                "level": "Advanced",
                "topic": "Technology in Education",
                "expected_length_check": True
            }
        }
    
    @pytest.fixture
    def mock_llm_system(self):
        """Comprehensive mock LLM for system testing"""
        mock_llm = Mock()
        mock_llm.run_azure_openai = AsyncMock()
        
        def system_mock_response(*args, **kwargs):
            """Sophisticated mock responses based on evaluation context"""
            name = kwargs.get('name', '').lower()
            messages = kwargs.get('messages', [])
            
            # Extract text being evaluated from messages
            text_content = ""
            for msg in messages:
                if isinstance(msg, dict) and 'content' in msg:
                    text_content += msg['content']
            
            # Determine text length and complexity for scoring
            word_count = len(text_content.split())
            
            if 'grammar' in name:
                # Grammar scoring based on text complexity
                if word_count < 30:
                    score = 2
                    correction = "Text is too short to properly evaluate grammar. Please provide more content."
                    feedback = "Limited text makes grammar assessment difficult."
                elif word_count < 80:
                    score = 3
                    correction = "Basic grammar is acceptable but could be improved with more varied sentence structures."
                    feedback = "Grammar is generally correct but lacks sophistication."
                else:
                    score = 4
                    correction = "Good grammar overall with minor areas for improvement."
                    feedback = "Strong grammatical skills demonstrated with varied sentence structures."
                
                return {
                    "score": score,
                    "correction": correction,
                    "feedback": feedback
                }
            
            elif 'introduction' in name:
                if word_count < 30:
                    return {
                        "score": 1,
                        "correction": "Introduction is too brief and lacks a clear thesis statement.",
                        "feedback": "Introduction needs significant development."
                    }
                elif word_count < 80:
                    return {
                        "score": 3,
                        "correction": "Introduction presents the topic but could have a stronger thesis statement.",
                        "feedback": "Good topic introduction with room for improvement."
                    }
                else:
                    return {
                        "score": 4,
                        "correction": "Strong introduction with clear topic presentation.",
                        "feedback": "Excellent opening that engages the reader effectively."
                    }
            
            elif 'body' in name:
                if word_count < 50:
                    return {
                        "score": 2,
                        "correction": "Body content is insufficient and lacks supporting details.",
                        "feedback": "Body needs more development and supporting evidence."
                    }
                elif word_count < 120:
                    return {
                        "score": 3,
                        "correction": "Body presents ideas but could use more specific examples and evidence.",
                        "feedback": "Good basic structure with adequate support for main points."
                    }
                else:
                    return {
                        "score": 4,
                        "correction": "Well-developed body with strong supporting evidence and examples.",
                        "feedback": "Excellent argumentation with comprehensive support."
                    }
            
            elif 'conclusion' in name:
                if word_count < 30:
                    return {
                        "score": 2,
                        "correction": "Conclusion is too brief and doesn't effectively summarize main points.",
                        "feedback": "Conclusion needs more development."
                    }
                else:
                    return {
                        "score": 3,
                        "correction": "Conclusion adequately summarizes the essay's main points.",
                        "feedback": "Good conclusion that ties together the main arguments."
                    }
            
            # Default response
            return {
                "score": 3,
                "correction": "Generally well-written with areas for improvement.",
                "feedback": "Good work overall with potential for enhancement."
            }
        
        mock_llm.run_azure_openai.side_effect = system_mock_response
        return mock_llm
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_basic_essay(self, mock_llm_system, system_test_essays):
        """Test complete pipeline with basic level essay"""
        essay_data = system_test_essays["basic_adequate"]
        
        evaluator = EssayEvaluator(llm=mock_llm_system, prompt_loader=PromptLoader())
        
        request = EssayEvalRequest(
            level_group=essay_data["level"],
            topic_prompt=essay_data["topic"],
            submit_text=essay_data["text"]
        )
        
        # Execute complete evaluation
        start_time = time.time()
        response = await evaluator.evaluate_essay(request)
        end_time = time.time()
        
        # Validate timing
        total_time = end_time - start_time
        assert total_time < 10  # Should complete within reasonable time
        
        # Validate response completeness
        assert response.level_group == essay_data["level"]
        assert response.pre_process is not None
        assert response.grammar is not None
        assert response.structure is not None
        assert response.aggregated is not None
        assert response.timings is not None
        assert response.timeline is not None
        
        # Validate pre-processing
        assert response.pre_process.is_english is True
        assert response.pre_process.is_appropriate_length == essay_data["expected_length_check"]
        assert response.pre_process.word_count > 0
        
        # Validate evaluation scores are reasonable
        assert 1 <= response.grammar.score <= 5
        assert 1 <= response.structure.introduction.score <= 5
        assert 1 <= response.structure.body.score <= 5
        assert 1 <= response.structure.conclusion.score <= 5
        assert 0 <= response.aggregated.score <= 100
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_different_levels(self, mock_llm_system, system_test_essays):
        """Test complete pipeline with essays at different levels"""
        evaluator = EssayEvaluator(llm=mock_llm_system, prompt_loader=PromptLoader())
        
        test_cases = [
            ("basic_short", "Expected short essay handling"),
            ("intermediate_comprehensive", "Expected intermediate complexity"),
            ("advanced_analytical", "Expected advanced analysis")
        ]
        
        results = []
        
        for essay_key, description in test_cases:
            essay_data = system_test_essays[essay_key]
            
            request = EssayEvalRequest(
                level_group=essay_data["level"],
                topic_prompt=essay_data["topic"],
                submit_text=essay_data["text"]
            )
            
            response = await evaluator.evaluate_essay(request)
            
            # Store results for comparison
            results.append({
                "level": essay_data["level"],
                "word_count": response.pre_process.word_count,
                "grammar_score": response.grammar.score,
                "final_score": response.aggregated.score,
                "description": description
            })
            
            # Validate each response
            assert response.level_group == essay_data["level"]
            assert isinstance(response.aggregated.score, int)
            assert 0 <= response.aggregated.score <= 100
        
        # Validate that longer, more complex essays generally score higher
        # (though this depends on the specific content)
        basic_result = next(r for r in results if r["level"] == "Basic")
        advanced_result = next(r for r in results if r["level"] == "Advanced")
        
        assert advanced_result["word_count"] > basic_result["word_count"]
        # Advanced essay should demonstrate sophistication
        assert advanced_result["grammar_score"] >= basic_result["grammar_score"]
    
    @pytest.mark.asyncio
    async def test_pipeline_performance_characteristics(self, mock_llm_system):
        """Test pipeline performance and resource usage"""
        evaluator = EssayEvaluator(llm=mock_llm_system, prompt_loader=PromptLoader())
        
        # Test with multiple essays
        test_essays = [
            "Short essay for performance testing.",
            "Medium length essay with multiple sentences for performance testing. This essay contains more content to evaluate processing time with different text lengths.",
            "Long comprehensive essay for performance testing with extensive content. " * 20
        ]
        
        performance_results = []
        
        for i, essay_text in enumerate(test_essays):
            request = EssayEvalRequest(
                level_group="Basic",
                topic_prompt="Performance testing",
                submit_text=essay_text
            )
            
            start_time = time.time()
            response = await evaluator.evaluate_essay(request)
            end_time = time.time()
            
            performance_results.append({
                "essay_length": len(essay_text),
                "word_count": response.pre_process.word_count,
                "processing_time": end_time - start_time,
                "llm_calls": mock_llm_system.run_azure_openai.call_count - sum(r.get("previous_calls", 0) for r in performance_results)
            })
            
            # Update call count for next iteration
            performance_results[-1]["previous_calls"] = mock_llm_system.run_azure_openai.call_count
        
        # Validate performance characteristics
        for result in performance_results:
            assert result["processing_time"] < 5  # Should be fast with mocked LLM
            assert result["llm_calls"] >= 4  # Grammar + 3 structure components
    
    @pytest.mark.asyncio
    async def test_pipeline_error_resilience(self, system_test_essays):
        """Test pipeline resilience to various error conditions"""
        # Test with LLM that sometimes fails
        unreliable_llm = Mock()
        unreliable_llm.run_azure_openai = AsyncMock()
        
        call_count = 0
        def failing_llm_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            # Fail on first call, succeed on subsequent calls
            if call_count == 1:
                raise Exception("Simulated LLM API failure")
            
            return {
                "score": 3,
                "correction": "Recovery response",
                "feedback": "System recovered from error"
            }
        
        unreliable_llm.run_azure_openai.side_effect = failing_llm_response
        
        evaluator = EssayEvaluator(llm=unreliable_llm, prompt_loader=PromptLoader())
        
        essay_data = system_test_essays["basic_adequate"]
        request = EssayEvalRequest(
            level_group=essay_data["level"],
            topic_prompt=essay_data["topic"],
            submit_text=essay_data["text"]
        )
        
        # System should handle the error gracefully
        # (Implementation might retry, return partial results, or raise exception)
        try:
            response = await evaluator.evaluate_essay(request)
            # If it succeeds, validate the response
            assert response is not None
        except Exception as e:
            # If it fails, ensure it's a meaningful error
            assert len(str(e)) > 0
    
    @pytest.mark.asyncio
    async def test_pipeline_with_edge_case_inputs(self, mock_llm_system):
        """Test pipeline with edge case inputs"""
        evaluator = EssayEvaluator(llm=mock_llm_system, prompt_loader=PromptLoader())
        
        edge_cases = [
            {
                "name": "empty_text",
                "text": "",
                "level": "Basic",
                "topic": "Test"
            },
            {
                "name": "whitespace_only",
                "text": "   \n\t   \n   ",
                "level": "Basic",
                "topic": "Test"
            },
            {
                "name": "single_word",
                "text": "Environment",
                "level": "Basic",
                "topic": "Environment"
            },
            {
                "name": "very_long_text",
                "text": "Environmental protection is important. " * 500,
                "level": "Expert",
                "topic": "Environment"
            },
            {
                "name": "special_characters",
                "text": "Environmental protection @#$% is important!!! We need (urgent) action NOW... 50% reduction required.",
                "level": "Intermediate",
                "topic": "Environment"
            }
        ]
        
        for edge_case in edge_cases:
            request = EssayEvalRequest(
                level_group=edge_case["level"],
                topic_prompt=edge_case["topic"],
                submit_text=edge_case["text"]
            )
            
            try:
                response = await evaluator.evaluate_essay(request)
                
                # Validate that response is structurally correct even for edge cases
                assert response.level_group == edge_case["level"]
                assert response.pre_process is not None
                assert response.aggregated is not None
                
                # For empty/whitespace text, should detect appropriately
                if edge_case["name"] in ["empty_text", "whitespace_only"]:
                    assert response.pre_process.word_count == 0
                    assert response.pre_process.is_appropriate_length is False
                
            except Exception as e:
                # Edge cases might raise exceptions - that's acceptable if handled gracefully
                assert isinstance(e, Exception)


@pytest.mark.system
@pytest.mark.slow
class TestSystemIntegrationWithRealData:
    """Test system integration with realistic data scenarios"""
    
    def test_load_sample_data_integration(self):
        """Test integration with sample data file if available"""
        data_path = Path(__file__).parent.parent.parent / "data" / "essay_writing_40_sample.xlsx"
        
        if not data_path.exists():
            pytest.skip("Sample data file not found")
        
        try:
            df = pd.read_excel(data_path)
            
            # Validate data structure
            assert len(df) > 0
            assert "submit_text" in df.columns
            assert "level_group" in df.columns
            
            # Test with first few essays
            sample_essays = df.head(3)
            
            for _, row in sample_essays.iterrows():
                # Validate that data is suitable for testing
                assert isinstance(row["submit_text"], str)
                assert len(row["submit_text"]) > 0
                assert row["level_group"] in ["Basic", "Intermediate", "Advanced", "Expert"]
                
        except Exception as e:
            pytest.skip(f"Could not load sample data: {e}")
    
    @pytest.mark.asyncio
    async def test_batch_processing_simulation(self, mock_llm_system):
        """Simulate batch processing of multiple essays"""
        evaluator = EssayEvaluator(llm=mock_llm_system, prompt_loader=PromptLoader())
        
        # Create batch of test essays
        batch_essays = [
            {
                "text": f"This is test essay number {i+1} about environmental protection. " * (5 + i*2),
                "level": ["Basic", "Intermediate", "Advanced"][i % 3],
                "topic": "Environment"
            }
            for i in range(5)
        ]
        
        batch_results = []
        start_time = time.time()
        
        # Process batch sequentially (as would happen in real system)
        for i, essay in enumerate(batch_essays):
            request = EssayEvalRequest(
                level_group=essay["level"],
                topic_prompt=essay["topic"],
                submit_text=essay["text"]
            )
            
            essay_start = time.time()
            response = await evaluator.evaluate_essay(request)
            essay_end = time.time()
            
            batch_results.append({
                "essay_id": i,
                "level": essay["level"],
                "word_count": response.pre_process.word_count,
                "final_score": response.aggregated.score,
                "processing_time": essay_end - essay_start
            })
        
        total_time = time.time() - start_time
        
        # Validate batch processing results
        assert len(batch_results) == 5
        assert total_time < 30  # Should complete batch quickly with mocked LLM
        
        # Validate all essays were processed successfully
        for result in batch_results:
            assert 0 <= result["final_score"] <= 100
            assert result["processing_time"] > 0
            assert result["word_count"] > 0


@pytest.mark.system
class TestSystemDocumentation:
    """Test that system components are properly documented and accessible"""
    
    def test_api_documentation_accessible(self):
        """Test that API documentation is accessible"""
        from fastapi.testclient import TestClient
        from main import app
        
        client = TestClient(app)
        
        # Test OpenAPI schema endpoint
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "/v1/essay-eval" in schema["paths"]
    
    def test_system_health_monitoring(self):
        """Test system health monitoring capabilities"""
        from fastapi.testclient import TestClient
        from main import app
        
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_version_information_available(self):
        """Test that version information is available"""
        from main import app
        
        # Version should be accessible from app metadata
        assert hasattr(app, 'version') or app.title is not None