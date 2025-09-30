# app/factory/llm_factory.py  (경로는 상황에 맞게)
from typing import Optional
from app.client.azure_openai import AzureOpenAILLM
from app.utils.tracer import ObservedLLM, LLM

_llm_singleton: Optional[LLM] = None

def build_llm() -> LLM:
    global _llm_singleton
    if _llm_singleton is None:
        base = AzureOpenAILLM()       # 순수 LLM 클라이언트
        _llm_singleton = ObservedLLM(base)  # Langfuse 관측 래퍼
    return _llm_singleton
