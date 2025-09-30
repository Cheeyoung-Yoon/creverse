from typing import Any, Dict, Optional, List, Protocol, runtime_checkable
from langfuse import Langfuse, observe
from dotenv import load_dotenv

load_dotenv()

# Initialize Langfuse client if available; otherwise keep as None
_lf = None
def lf():
    global _lf
    if _lf is None:
        _lf = Langfuse()  # 이 시점에 이미 .env 로드되어 있어야 함
    return _lf  # LANGFUSE_* env used when present

@runtime_checkable
class LLM(Protocol):
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

    @observe(name="llm.run_azure_openai")
    async def run_azure_openai(self, *, messages, json_schema, trace_id=None, name=None):
        schema_name = json_schema.get("title") or json_schema.get("name") or "EvalSchema"
        with lf().start_as_current_generation(
            name=name or f"{self.service}.responses.parse",
            model=getattr(self.inner, "deployment", "unknown"),
            input={"messages": messages, "json_schema_name": schema_name},
        ) as gen:
            res = await self.inner.run_azure_openai(
                messages=messages, json_schema=json_schema,
                trace_id=None, name=name,   # 내부 중복 로깅 방지
            )
            gen.set_output({"content": res.get("content"), "usage": res.get("usage")})
            return res
