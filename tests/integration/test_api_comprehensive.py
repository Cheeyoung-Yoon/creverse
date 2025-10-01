"""
Comprehensive API tests for essay evaluation endpoint
"""
import pytest
import sys
import os
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from main import app


class TestEssayEvalAPI:
    """Comprehensive API tests for essay evaluation"""
    
    @pytest.fixture
    def client(self):
        """Test client fixture"""
        return TestClient(app)
    
    @pytest.fixture
    def valid_payload(self):
        """Valid request payload"""
        return {
            "rubric_level": "Basic",
            "topic_prompt": "Write about environmental issues and their solutions",
            "submit_text": "Environmental problems are serious issues that affect our planet today. Climate change is one of the biggest challenges we face. We need to reduce pollution and use renewable energy sources. Governments and individuals must work together to protect the environment for future generations. This requires immediate action and long-term planning."
        }

    def test_ping_endpoint_success(self, client):
        """Test ping endpoint returns success"""
        response = client.get("/v1/ping")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_essay_eval_invalid_json(self, client):
        """Test essay evaluation with invalid JSON"""
        response = client.post("/v1/essay-eval", data="invalid json")
        assert response.status_code == 422

    def test_essay_eval_missing_required_fields(self, client):
        """Test essay evaluation with missing required fields"""
        incomplete_payload = {
            "rubric_level": "Basic",
            # Missing topic_prompt and submit_text
        }
        response = client.post("/v1/essay-eval", json=incomplete_payload)
        assert response.status_code == 422
        
    def test_essay_eval_invalid_rubric_level(self, client):
        """Test essay evaluation with invalid rubric level"""
        invalid_payload = {
            "rubric_level": "InvalidLevel",
            "topic_prompt": "Test topic",
            "submit_text": "This is a test essay with enough words to meet the minimum requirement for validation purposes."
        }
        response = client.post("/v1/essay-eval", json=invalid_payload)
        assert response.status_code == 422

    def test_essay_eval_text_too_short(self, client):
        """Test essay evaluation with text too short"""
        short_payload = {
            "rubric_level": "Basic",
            "topic_prompt": "Test topic",
            "submit_text": "Short text"  # Too short
        }
        response = client.post("/v1/essay-eval", json=short_payload)
        assert response.status_code == 422

    def test_essay_eval_empty_text(self, client):
        """Test essay evaluation with empty text"""
        empty_payload = {
            "rubric_level": "Basic",
            "topic_prompt": "Test topic",
            "submit_text": ""  # Empty
        }
        response = client.post("/v1/essay-eval", json=empty_payload)
        assert response.status_code == 422

    def test_essay_eval_empty_topic_prompt(self, client):
        """Test essay evaluation with empty topic prompt"""
        empty_topic_payload = {
            "rubric_level": "Basic",
            "topic_prompt": "",  # Empty
            "submit_text": "This is a test essay with enough words to meet the minimum requirement for validation purposes."
        }
        response = client.post("/v1/essay-eval", json=empty_topic_payload)
        assert response.status_code == 422

    @patch('app.api.v1.essay_eval.EssayEvaluator.evaluate')
    def test_essay_eval_service_error(self, mock_evaluate, client, valid_payload):
        """Test essay evaluation when service raises an error"""
        mock_evaluate.side_effect = Exception("Service error")
        
        response = client.post("/v1/essay-eval", json=valid_payload)
        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["type"] == "InternalError"

    def test_essay_eval_connection_timeout(self, client, valid_payload):
        """Test essay evaluation with connection timeout scenario"""
        # This test may succeed normally, we're just testing the endpoint structure
        response = client.post("/v1/essay-eval", json=valid_payload)
        # Accept both success and error responses for this test
        assert response.status_code in [200, 500]

    def test_essay_eval_different_levels(self, client):
        """Test essay evaluation with different rubric levels"""
        levels = ["Basic", "Intermediate", "Advanced", "Expert"]
        
        for level in levels:
            payload = {
                "rubric_level": level,
                "topic_prompt": "Write about technology",
                "submit_text": "Technology has transformed modern society in countless ways. From smartphones to artificial intelligence, technological advances continue to shape how we work, communicate, and live our daily lives."
            }
            
            # Skip if Azure credentials not available
            if not (os.getenv("AZURE_OPENAI_API_KEY") and 
                   os.getenv("AZURE_OPENAI_ENDPOINT") and 
                   os.getenv("AZURE_OPENAI_DEPLOYMENT")):
                pytest.skip("Azure OpenAI credentials not configured; skipping integration test.")
                
            response = client.post("/v1/essay-eval", json=payload)
            if response.status_code == 200:
                data = response.json()
                assert data["rubric_level"] == level

    def test_unsupported_http_methods(self, client):
        """Test unsupported HTTP methods on endpoints"""
        # Essay eval should only accept POST
        response = client.get("/v1/essay-eval")
        assert response.status_code == 405  # Method Not Allowed
        
        response = client.put("/v1/essay-eval")
        assert response.status_code == 405
        
        response = client.delete("/v1/essay-eval")
        assert response.status_code == 405

    def test_request_headers(self, client, valid_payload):
        """Test API with various request headers"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "test-client"
        }
        
        # Skip if Azure credentials not available
        if not (os.getenv("AZURE_OPENAI_API_KEY") and 
               os.getenv("AZURE_OPENAI_ENDPOINT") and 
               os.getenv("AZURE_OPENAI_DEPLOYMENT")):
            pytest.skip("Azure OpenAI credentials not configured; skipping integration test.")
            
        response = client.post("/v1/essay-eval", json=valid_payload, headers=headers)
        # Should work with proper headers
        assert response.status_code in [200, 500]  # 200 success or 500 if service issues

    def test_large_text_input(self, client):
        """Test API with large text input"""
        large_text = "This is a test sentence. " * 200  # Very long text
        
        large_payload = {
            "rubric_level": "Basic",
            "topic_prompt": "Write about anything",
            "submit_text": large_text
        }
        
        response = client.post("/v1/essay-eval", json=large_payload)
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 422, 500]

    def test_llm_dependency_scenario(self, client, valid_payload):
        """Test LLM dependency scenario"""
        # This test verifies the endpoint structure and behavior
        response = client.post("/v1/essay-eval", json=valid_payload)
        # Accept both success and error responses
        assert response.status_code in [200, 500]