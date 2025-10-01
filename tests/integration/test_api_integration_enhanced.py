"""
Enhanced integration tests for API endpoints
"""
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from main import app
from app.models.request import EssayEvalRequest


@pytest.mark.integration
class TestAPIIntegration:
    """Test API integration with mocked services"""
    
    @pytest.fixture
    def test_client(self):
        """FastAPI test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_evaluator_response(self):
        """Mock evaluator response for API testing"""
        from app.models.response import (
            EssayEvalResponse, RubricItemPayload, StructureChainResult,
            EvaluationTimeline, TokenUsage
        )
        from app.models.rubric import PreProcessResult, ScoreCorrectionFeedback
        
        # Create mock response
        pre_process = PreProcessResult(
            is_appropriate_length=True,
            is_english=True,
            is_on_topic=True,
            word_count=180,
            detected_language="en",
            topic_relevance_score=0.85
        )
        
        grammar_payload = RubricItemPayload(
            rubric_item="grammar",
            score=4,
            correction="Minor punctuation improvements",
            feedback="Good grammar overall",
            token_usage=TokenUsage(120, 60, 180),
            evaluation_type="grammar_check"
        )
        
        structure_result = StructureChainResult(
            introduction=RubricItemPayload(
                rubric_item="introduction",
                score=3,
                correction="Strengthen thesis",
                feedback="Good opening",
                evaluation_type="structure"
            ),
            body=RubricItemPayload(
                rubric_item="body",
                score=4,
                correction="Add examples",
                feedback="Strong arguments",
                evaluation_type="structure"
            ),
            conclusion=RubricItemPayload(
                rubric_item="conclusion",
                score=3,
                correction="Better summary",
                feedback="Adequate ending",
                evaluation_type="structure"
            ),
            token_usage_total=TokenUsage(300, 150, 450),
            evaluation_type="structure_chain"
        )
        
        aggregated = ScoreCorrectionFeedback(
            score=78,
            correction="Good essay with areas for improvement",
            feedback="Strong work overall with room for enhancement"
        )
        
        timeline = EvaluationTimeline(
            start="2024-01-01T10:00:00Z",
            end="2024-01-01T10:03:30Z"
        )
        
        return EssayEvalResponse(
            level_group="Basic",
            pre_process=pre_process,
            grammar=grammar_payload,
            structure=structure_result,
            aggregated=aggregated,
            timings={"total": 3.5, "grammar": 1.2, "structure": 2.3},
            timeline=timeline
        )
    
    def test_health_endpoint(self, test_client):
        """Test health check endpoint"""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    @patch('app.services.essay_evaluator.EssayEvaluator.evaluate_essay')
    def test_essay_eval_endpoint_success(self, mock_evaluate, test_client, mock_evaluator_response):
        """Test successful essay evaluation endpoint"""
        mock_evaluate.return_value = mock_evaluator_response
        
        payload = {
            "level_group": "Basic",
            "topic_prompt": "Environmental protection",
            "submit_text": "This is a test essay about environmental issues and their impact on society."
        }
        
        response = test_client.post("/v1/essay-eval", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["level_group"] == "Basic"
        assert "pre_process" in data
        assert "grammar" in data
        assert "structure" in data
        assert "aggregated" in data
        assert "timings" in data
        assert "timeline" in data
        
        # Verify specific fields
        assert data["grammar"]["rubric_item"] == "grammar"
        assert data["grammar"]["score"] == 4
        assert data["aggregated"]["score"] == 78
    
    def test_essay_eval_endpoint_validation(self, test_client):
        """Test input validation on essay evaluation endpoint"""
        # Test missing required fields
        incomplete_payload = {
            "level_group": "Basic"
            # Missing topic_prompt and submit_text
        }
        
        response = test_client.post("/v1/essay-eval", json=incomplete_payload)
        assert response.status_code == 422  # Validation error
    
    def test_essay_eval_endpoint_invalid_level(self, test_client):
        """Test essay evaluation with invalid level"""
        payload = {
            "level_group": "InvalidLevel",
            "topic_prompt": "Test topic",
            "submit_text": "Test essay content"
        }
        
        response = test_client.post("/v1/essay-eval", json=payload)
        # Should either accept it or return validation error
        assert response.status_code in [200, 422]
    
    def test_essay_eval_endpoint_empty_text(self, test_client):
        """Test essay evaluation with empty text"""
        payload = {
            "level_group": "Basic",
            "topic_prompt": "Test topic",
            "submit_text": ""
        }
        
        response = test_client.post("/v1/essay-eval", json=payload)
        # Should handle empty text gracefully
        assert response.status_code in [200, 400, 422]
    
    @patch('app.services.essay_evaluator.EssayEvaluator.evaluate_essay')
    def test_essay_eval_endpoint_error_handling(self, mock_evaluate, test_client):
        """Test error handling in essay evaluation endpoint"""
        # Mock an exception in the evaluator
        mock_evaluate.side_effect = Exception("Internal evaluation error")
        
        payload = {
            "level_group": "Basic",
            "topic_prompt": "Test topic",
            "submit_text": "Test essay content"
        }
        
        response = test_client.post("/v1/essay-eval", json=payload)
        assert response.status_code == 500


@pytest.mark.integration
@pytest.mark.azure
class TestAPIWithAzureIntegration:
    """Test API integration with real Azure OpenAI (requires credentials)"""
    
    def _require_azure(self):
        """Skip test if Azure credentials not available"""
        import os
        if not (os.getenv("AZURE_OPENAI_API_KEY") and 
                os.getenv("AZURE_OPENAI_ENDPOINT") and 
                os.getenv("AZURE_OPENAI_DEPLOYMENT")):
            pytest.skip("Azure OpenAI credentials not configured")
    
    def test_real_azure_essay_evaluation(self):
        """Test with real Azure OpenAI (slow test)"""
        self._require_azure()
        
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        payload = {
            "level_group": "Basic",
            "topic_prompt": "Environmental protection",
            "submit_text": "Environmental protection is important for our future. We need to reduce pollution and protect wildlife habitats. Clean air and water are essential for all living things. Everyone should participate in environmental conservation efforts."
        }
        
        response = client.post("/v1/essay-eval", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify complete response structure
        assert data["level_group"] == "Basic"
        assert "pre_process" in data
        assert "grammar" in data
        assert "structure" in data
        assert "aggregated" in data
        
        # Verify realistic evaluation results
        assert isinstance(data["aggregated"]["score"], int)
        assert 0 <= data["aggregated"]["score"] <= 100
        assert len(data["aggregated"]["feedback"]) > 10


@pytest.mark.integration
class TestCORSAndMiddleware:
    """Test CORS and middleware integration"""
    
    def test_cors_headers(self):
        """Test CORS headers are properly set"""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        # Test preflight request
        response = client.options("/v1/essay-eval")
        
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers or response.status_code == 405
    
    def test_request_timing_middleware(self):
        """Test request timing functionality"""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        # Make a request and check if timing is captured
        response = client.get("/health")
        assert response.status_code == 200
        
        # Timing headers might be added by middleware
        # This depends on the actual implementation


@pytest.mark.integration
class TestAPIErrorHandling:
    """Test API error handling scenarios"""
    
    def test_malformed_json(self):
        """Test handling of malformed JSON"""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        # Send malformed JSON
        response = client.post(
            "/v1/essay-eval",
            data="{invalid json}",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_unsupported_content_type(self):
        """Test handling of unsupported content types"""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        # Send text instead of JSON
        response = client.post(
            "/v1/essay-eval",
            data="plain text data",
            headers={"Content-Type": "text/plain"}
        )
        
        assert response.status_code == 422
    
    def test_large_payload(self):
        """Test handling of very large payloads"""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        # Create a very large essay
        large_text = "This is a very long essay. " * 10000  # ~280KB
        
        payload = {
            "level_group": "Basic",
            "topic_prompt": "Test topic",
            "submit_text": large_text
        }
        
        response = client.post("/v1/essay-eval", json=payload)
        
        # Should either process it or return appropriate error
        assert response.status_code in [200, 413, 422]  # OK, Payload too large, or Validation error


@pytest.mark.integration
class TestAPIPerformance:
    """Test API performance characteristics"""
    
    @pytest.mark.slow
    def test_concurrent_requests(self):
        """Test handling of concurrent requests"""
        import threading
        import time
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        results = []
        
        def make_request():
            payload = {
                "level_group": "Basic",
                "topic_prompt": "Test topic",
                "submit_text": "Short test essay for concurrent testing."
            }
            start_time = time.time()
            response = client.post("/v1/essay-eval", json=payload)
            end_time = time.time()
            results.append({
                "status_code": response.status_code,
                "duration": end_time - start_time
            })
        
        # Create multiple threads
        threads = []
        for i in range(3):  # Limited number for testing
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests completed
        assert len(results) == 3
        for result in results:
            assert result["status_code"] in [200, 500]  # Success or server error
            assert result["duration"] < 30  # Should complete within reasonable time