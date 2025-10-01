"""
Pytest configuration and shared fixtures
"""
import os
import sys
import pytest
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.prompt_loader import PromptLoader
from app.utils.price_tracker import PriceTracker, TokenUsage


@pytest.fixture
def mock_llm():
    """Mock LLM client for testing"""
    llm = Mock()
    llm.run_azure_openai = AsyncMock()
    llm.run_azure_openai.return_value = {
        "score": 3,
        "correction": "Some correction text",
        "feedback": "Some feedback text"
    }
    return llm


@pytest.fixture
def sample_essay_text():
    """Sample essay text for testing"""
    return """
    This is a sample essay for testing purposes. 
    It contains multiple paragraphs to test the evaluation system.
    
    The introduction presents the main topic clearly.
    The body provides supporting arguments and examples.
    The conclusion summarizes the main points effectively.
    
    This essay is designed to be of adequate length for testing
    various evaluation criteria including grammar, structure, and content.
    """


@pytest.fixture
def sample_token_usage():
    """Sample token usage data"""
    return {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150
    }


@pytest.fixture
def prompt_loader():
    """PromptLoader instance"""
    return PromptLoader()


@pytest.fixture
def price_tracker():
    """Fresh PriceTracker instance"""
    return PriceTracker()


@pytest.fixture
def mock_azure_env(monkeypatch):
    """Mock Azure OpenAI environment variables"""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test_key_123")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "test-deployment")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-04-01-preview")


@pytest.fixture
def sample_pre_process_result():
    """Sample pre-process result for testing"""
    from app.models.rubric import PreProcessResult
    return PreProcessResult(
        is_appropriate_length=True,
        is_english=True,
        is_on_topic=True,
        word_count=150,
        detected_language="en",
        topic_relevance_score=0.8
    )


@pytest.fixture
def sample_rubric_result():
    """Sample rubric evaluation result"""
    from app.models.rubric import RubricItemResult
    return RubricItemResult(
        rubric_item="grammar",
        score=3,
        correction="Minor grammar improvements needed",
        feedback="Good overall grammar with room for improvement"
    )


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests for component interactions"
    )
    config.addinivalue_line(
        "markers", "system: System/end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow running tests"
    )
    config.addinivalue_line(
        "markers", "azure: Tests requiring Azure OpenAI credentials"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on file location"""
    for item in items:
        # Mark tests based on file path
        if "unit_test" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "system" in str(item.fspath):
            item.add_marker(pytest.mark.system)
        
        # Mark tests that use Azure
        if any(keyword in item.name.lower() for keyword in ["azure", "openai", "llm"]):
            item.add_marker(pytest.mark.azure)