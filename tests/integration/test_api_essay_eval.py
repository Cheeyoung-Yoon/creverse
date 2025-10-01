import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi.testclient import TestClient

from main import app


def _require_azure():
    if not (os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_DEPLOYMENT")):
        pytest.skip("Azure OpenAI credentials not configured; skipping integration test.")


def test_essay_eval_endpoint():
    _require_azure()
    client = TestClient(app)
    payload = {
        "rubric_level": "Basic",  # Changed from level_group to rubric_level
        "topic_prompt": "Write about environmental issues and their solutions",
        "submit_text": "Environmental problems are serious issues that affect our planet today. Climate change is one of the biggest challenges we face. We need to reduce pollution and use renewable energy sources. Governments and individuals must work together to protect the environment for future generations. This requires immediate action and long-term planning.",
    }
    res = client.post("/v1/essay-eval", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["rubric_level"] == "Basic"  # Changed from level_group
    assert "pre_process" in data
    assert "grammar" in data and data["grammar"]["rubric_item"] == "grammar"
    assert "structure" in data and "introduction" in data["structure"]
    assert "aggregated" in data and isinstance(data["aggregated"]["score"], int)
