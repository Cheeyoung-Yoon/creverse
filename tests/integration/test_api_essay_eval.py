import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi.testclient import TestClient

from creverse2.main import app


def _require_azure():
    if not (os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_DEPLOYMENT")):
        pytest.skip("Azure OpenAI credentials not configured; skipping integration test.")


def test_essay_eval_endpoint():
    _require_azure()
    client = TestClient(app)
    payload = {
        "level_group": "Basic",
        "topic_prompt": "Environment",
        "submit_text": "This is an essay. It has content.",
    }
    res = client.post("/v1/essay-eval", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["level_group"] == "Basic"
    assert "pre_process" in data
    assert "grammar" in data and data["grammar"]["rubric_item"] == "grammar"
    assert "structure" in data and "introduction" in data["structure"]
    assert "aggregated" in data and isinstance(data["aggregated"]["score"], int)
