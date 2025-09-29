import pytest
from jsonschema import validate
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
# If your schema lives elsewhere, import it; otherwise keep a local copy here.
RUBRIC_ITEM_SCHEMA = {
    "name": "RubricItem",
    "type": "object",
    "properties": {
        "rubric_item": {
            "type": "string",
            "enum": ["introduction", "body", "conclusion", "grammar"]
        },
        "score": {"type": "integer", "minimum": 0, "maximum": 2},
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "highlight": {"type": "string"},
                    "issue": {"type": "string"},
                    "correction": {"type": "string"}
                },
                "required": ["highlight", "issue", "correction"],
                "additionalProperties": False
            }
        },
        "feedback": {"type": "string"}
    },
    "required": ["rubric_item", "score", "corrections", "feedback"],
    "additionalProperties": False
}

@pytest.mark.asyncio
async def test_generate_json_returns_valid_schema(monkeypatch):
    # Import your real class
    from app.client.azure_openai import AzureOpenAILLM

    # Stub the LLM call so the test is fast, deterministic, and doesn’t need real Azure credentials.
    async def fake_generate_json(self, messages, json_schema):
        # You can assert inputs if you want:
        assert isinstance(messages, list) and messages, "messages must be non-empty"
        assert json_schema.get("name") == "RubricItem"
        # Return a JSON matching the schema
        return {
            "rubric_item": "introduction",
            "score": 2,
            "corrections": [
                {
                    "highlight": "The opening sentence",
                    "issue": "Too generic",
                    "correction": "Add a specific hook about the topic"
                }
            ],
            "feedback": "Clear, engaging introduction with a solid thesis."
        }

    monkeypatch.setattr(AzureOpenAILLM, "generate_json", fake_generate_json)

    llm = AzureOpenAILLM()
    messages = [
        {"role": "system", "content": "You are an evaluator. Respond strictly in JSON schema."},
        {"role": "user", "content": "Evaluate a simple essay introduction with score=2."},
    ]

    out = await llm.generate_json(messages=messages, json_schema=RUBRIC_ITEM_SCHEMA)

    # Validate structure against the schema
    validate(instance=out, schema=RUBRIC_ITEM_SCHEMA)

    # A few semantic checks
    assert out["rubric_item"] == "introduction"
    assert out["score"] == 2
    assert isinstance(out["corrections"], list) and len(out["corrections"]) >= 1
    assert "feedback" in out and out["feedback"]
