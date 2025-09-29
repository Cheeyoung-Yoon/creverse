import asyncio
import json
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.client.azure_openai import AzureOpenAILLM
from app.core.config import settings

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


async def main():
    llm = AzureOpenAILLM()

    messages = [
        {"role": "system", "content": "You are an evaluator. Respond strictly in JSON schema."},
        {"role": "user", "content": "Evaluate a simple essay introduction with score=2."},
    ]

    out = await llm.generate_json(messages=messages, json_schema=RUBRIC_ITEM_SCHEMA)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
