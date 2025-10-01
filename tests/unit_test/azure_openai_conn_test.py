import pytest
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

def validate_rubric_item_structure(data):
    """Manual validation of rubric item structure without jsonschema dependency"""
    required_fields = ["rubric_item", "score", "corrections", "feedback"]
    
    # Check all required fields exist
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # Validate rubric_item
    assert data["rubric_item"] in ["introduction", "body", "conclusion", "grammar"]
    
    # Validate score
    assert isinstance(data["score"], int)
    assert 0 <= data["score"] <= 2
    
    # Validate corrections array
    assert isinstance(data["corrections"], list)
    for correction in data["corrections"]:
        assert isinstance(correction, dict)
        required_correction_fields = ["highlight", "issue", "correction"]
        for field in required_correction_fields:
            assert field in correction, f"Missing correction field: {field}"
            assert isinstance(correction[field], str)
    
    # Validate feedback
    assert isinstance(data["feedback"], str)

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
async def test_generate_json_returns_valid_schema():
    # Real call only when Azure creds are present
    if not (os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_DEPLOYMENT")):
        pytest.skip("Azure OpenAI credentials not configured; skipping LLM test.")

    from app.client.azure_openai import AzureOpenAILLM

    llm = AzureOpenAILLM()
    messages = [
        {"role": "system", "content": "You are an evaluator. Respond strictly in JSON schema."},
        {"role": "user", "content": "Evaluate a simple essay introduction with score=2."},
    ]

    out = await llm.generate_json(messages=messages, json_schema=RUBRIC_ITEM_SCHEMA)

    # The client returns a dict with content and usage
    assert "content" in out and "usage" in out
    content = out["content"]
    usage = out["usage"]

    # Validate structure against the schema
    validate_rubric_item_structure(content)

    # A few semantic checks
    assert content["rubric_item"] in ["introduction", "body", "conclusion", "grammar"]
    assert isinstance(usage.get("total_tokens"), int)
