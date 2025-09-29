# app/client/azure_openai.py
import asyncio, json
from typing import Any
from openai import AzureOpenAI
from app.core.config import settings

class AzureOpenAILLM:
    """GPT-5용 최소 래퍼: JSON 스키마 강제 제어"""

    def __init__(self):
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        self.default_max_output_tokens = 800

    async def generate_json(
        self,
        *,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:

        def _invoke_sync() -> dict[str, Any]:
            resp = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": json_schema.get("name", "EvalSchema"),
                        "schema": json_schema,
                        "strict": True,
                    },
                },
            )
            result = {
                "content": json.loads(resp.choices[0].message.content),
                "usage": {
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                    "total_tokens": resp.usage.total_tokens,
                }
            }
            return result

        return await asyncio.to_thread(_invoke_sync)


# 테스트/개발용
class FakeLLM:
    def __init__(self, canned: dict[str, Any] | None = None):
        self.canned = canned or {
            "rubric_item": "introduction",
            "score": 2,
            "corrections": [],
            "feedback": "ok",
        }

    async def generate_json(self, **_: Any) -> dict[str, Any]:
        await asyncio.sleep(0)
        return self.canned
