import asyncio, json
from typing import Any, Dict, Optional
from openai import AzureOpenAI
from app.core.config import settings
from app.utils.tracer import LLM


class AzureOpenAILLM(LLM):
    """GPT-5용 최소 래퍼: JSON 스키마 강제 제어"""

    def __init__(self):
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        self.default_max_output_tokens = 1500  # Increased from 800 to allow complete responses

    def _ensure_strict_json_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively enforce additionalProperties=false on all object schemas.

        OpenAI's json_schema response_format requires top-level 'additionalProperties'
        to be present and set to false, and nested object schemas should also be
        explicit. This patches a Pydantic-generated schema accordingly.
        """
        def walk(node: Any):  # type: ignore[no-untyped-def]
            if isinstance(node, dict):
                # If this dict represents an object schema, enforce additionalProperties=false
                if node.get("type") == "object":
                    node.setdefault("additionalProperties", False)
                    # Recurse into properties
                    props = node.get("properties")
                    if isinstance(props, dict):
                        for v in props.values():
                            walk(v)
                # Recurse into items (arrays)
                if "items" in node:
                    walk(node.get("items"))
                # Recurse into $defs/definitions
                defs = node.get("$defs") or node.get("definitions")
                if isinstance(defs, dict):
                    for v in defs.values():
                        walk(v)
                # Recurse into combinators
                for key in ("allOf", "anyOf", "oneOf"):
                    if key in node and isinstance(node[key], list):
                        for v in node[key]:
                            walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        patched = json.loads(json.dumps(schema))  # deep copy
        walk(patched)
        # Ensure top-level object has additionalProperties=false as well
        if patched.get("type") == "object":
            patched.setdefault("additionalProperties", False)
        return patched

    async def run_azure_openai(
        self,
        *,
        messages: list[dict[str, str]],
        json_schema: dict[str, Any],
        trace_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> dict[str, Any]:

        def _invoke_sync() -> dict[str, Any]:
            # Patch schema to satisfy OpenAI strict JSON Schema requirements
            strict_schema = self._ensure_strict_json_schema(json_schema)
            
            # Use the correct chat completions API with structured outputs
            resp = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": json_schema.get("title", json_schema.get("name", "EvalSchema")),
                        "schema": strict_schema,
                        "strict": True,
                    },
                },
                # max_completion_tokens 제거 - 토큰 제한 없음
            )
            
            # Parse the response content
            content = resp.choices[0].message.content
            if content:
                try:
                    parsed_content = json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON response: {content}")
                    print(f"JSON decode error: {e}")
                    parsed_content = {}
            else:
                print(f"Empty content received from Azure OpenAI. Full response: {resp}")
                parsed_content = {}
            
            result = {
                "content": parsed_content,
                "usage": {
                    "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                    "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                    "total_tokens": resp.usage.total_tokens if resp.usage else 0,
                }
            }
            return result

        return await asyncio.to_thread(_invoke_sync)

    
    
    
    

# Note: No Fake/Mock LLM implementation here; tests should use real Azure or skip.
