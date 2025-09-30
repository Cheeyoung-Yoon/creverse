from app.client.azure_openai import AzureOpenAILLM
from app.utils.tracer import ObservedLLM

# 필요 시 싱글턴/캐시
_llm = None

def build_llm():
    global _llm
    if _llm is None:
        base = AzureOpenAILLM()     # 순수 LLM 클라이언트
        _llm = ObservedLLM(base)    # Langfuse v3 관측 래퍼로 감싸기
    return _llm