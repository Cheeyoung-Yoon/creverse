from typing import Any, Dict, Optional, List, Protocol, runtime_checkable
from langfuse import observe
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

@runtime_checkable
class LLM(Protocol):
    deployment: Optional[str]
    async def run_azure_openai(
        self, *, messages: List[Dict[str, str]],
        json_schema: Dict[str, Any],
        trace_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]: ...

class ObservedLLM:
    def __init__(self, inner: LLM, service: str = "azure-openai"):
        self.inner = inner
        self.service = service

    @observe(name="llm.run_azure_openai", as_type="generation")  # v3
    async def run_azure_openai(self, *, messages, json_schema, trace_id=None, name=None):
        # 추가 수동 generation 없음 (중복 관찰 방지)
        return await self.inner.run_azure_openai(
            messages=messages, json_schema=json_schema,
            trace_id=trace_id, name=name,
        )
