# app/utils/tracer.py
from typing import Any, Dict, Optional, List, Protocol, runtime_checkable
import logging, os
from app.core.config import settings
from app.utils.price_tracker import track_api_usage

logger = logging.getLogger(__name__)

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

LANGFUSE_AVAILABLE = bool(public_key and secret_key)

# Langfuse 관련 import 및 초기화
lf = None
observe = None

if LANGFUSE_AVAILABLE:
    try:
        from langfuse import Langfuse, observe
        lf = Langfuse(public_key=public_key, secret_key=secret_key, host=host, release="v1.0.0")
        logger.info(f"Langfuse initialized. Host: {host}")
    except ImportError:
        logger.warning("Langfuse not installed. Tracing disabled.")
        LANGFUSE_AVAILABLE = False
    except Exception as e:
        logger.warning(f"Langfuse initialization failed: {e}. Tracing disabled.")
        LANGFUSE_AVAILABLE = False
else:
    logger.warning("Langfuse credentials not set. Tracing disabled.")

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

    async def run_azure_openai(
        self,
        *,
        messages: List[Dict[str, str]],
        json_schema: Dict[str, Any],
        trace_id: Optional[str] = None,
        name: Optional[str] = None,
        # ---- 프롬프트 추적 파라미터 ----
        prompt_key: str = "generate",           # e.g. "introduction" | "body" | "conclusion"
        prompt_name: Optional[str] = None,      # Langfuse Prompt Store name (있을 때 링크)
        prompt_label: str = "production",
        prompt_version: Optional[int] = None,   # 없으면 config 기본값
        prompt_meta: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, Any]] = None,  # Prompt Store 사용할 때 렌더 변수
        use_prompt_store_messages: bool = False,     # True면 Prompt Store에서 messages 렌더
    ) -> Dict[str, Any]:

        # 1) 버전 기본값: config에서 읽기
        version: Optional[int] = prompt_version if prompt_version is not None else settings.PROMPT_VERSIONS.get(prompt_key)

        # 2) Prompt Store: 프롬프트 가져오기 (선택)
        prompt_obj = None
        compiled_messages = None
        if LANGFUSE_AVAILABLE and lf and prompt_name:
            try:
                # label 우선, 필요하면 version으로 조회 로직 바꿔도 됨
                kwargs: Dict[str, Any] = {"name": prompt_name}
                if version is not None:
                    kwargs["version"] = version
                else:
                    kwargs["label"] = prompt_label  # 버전 미지정 시 라벨로
                prompt_obj = lf.get_prompt(**kwargs)  # 클라이언트 캐시/리트라이 지원
                if use_prompt_store_messages:
                    compiled = prompt_obj.compile(variables or {})
                    # compile은 자유 포맷 허용. ChatMessage 포맷이면 그대로 사용 가능
                    compiled_messages = compiled.get("messages")
            except Exception as e:
                logger.debug(f"Failed to fetch/compile prompt '{prompt_name}': {e}")

        # 실제 보낼 메시지 결정
        effective_messages = compiled_messages or messages

        # 3) 하위 generation 만들기 (이름= llm.{prompt_key})
        #    UI에서 "Type: Generation" + "Name: llm.introduction" 로 필터하세요.
        if LANGFUSE_AVAILABLE and lf:
            model_name = getattr(self.inner, "deployment", None) or os.getenv("AZURE_OPENAI_DEPLOYMENT") or "azure-openai"
            with lf.start_as_current_generation(name=f"llm.{prompt_key}", model=model_name) as gen:
                # 입력/메타 업데이트 (프롬프트 링크 포함)
                md = {
                    "service": self.service,
                    "prompt_key": prompt_key,
                    "prompt_label": prompt_label,
                    **({"prompt_version": version} if version is not None else {}),
                    **(prompt_meta or {}),
                }
                if prompt_obj is not None:
                    # ★ 프롬프트 링크: 이 키로 Langfuse가 프롬프트 버전과 generation을 연결
                    md["langfuse_prompt"] = prompt_obj

                gen.update(input={"messages": effective_messages, "json_schema": json_schema}, metadata=md)

                try:
                    result = await self.inner.run_azure_openai(
                        messages=effective_messages,
                        json_schema=json_schema,
                        trace_id=trace_id,
                        name=name,
                    )
                    
                    # Token usage 정보 추출 및 cost 계산
                    usage_info = result.get("usage", {})
                    cost_info = track_api_usage(usage_info, operation=f"llm.{prompt_key}")
                    
                    # 기존 metadata에 cost 정보 추가
                    updated_metadata = {
                        **md,  # 기존 metadata 포함
                    }
                    
                    # Cost 정보를 metadata에 추가
                    if cost_info and "cost" in cost_info:
                        cost_data = cost_info["cost"]
                        updated_metadata.update({
                            "cost_usd": cost_data.get("total_cost", 0),
                            "input_cost_usd": cost_data.get("input_cost", 0),
                            "output_cost_usd": cost_data.get("output_cost", 0),
                            "model_pricing": "azure-gpt5-mini"
                        })
                    
                    # Langfuse에 token usage와 cost 정보 전달
                    gen.update(
                        output=result,
                        metadata=updated_metadata,
                        usage={
                            "promptTokens": usage_info.get("prompt_tokens", 0),
                            "completionTokens": usage_info.get("completion_tokens", 0), 
                            "totalTokens": usage_info.get("total_tokens", 0),
                            "unit": "TOKENS"
                        }
                    )
                    
                    return result
                except Exception as e:
                    gen.update(error=str(e))
                    raise
                finally:
                    try:
                        lf.flush()
                    except Exception:
                        pass
        else:
            # Langfuse 미사용 시 그냥 호출
            return await self.inner.run_azure_openai(
                messages=effective_messages,
                json_schema=json_schema,
                trace_id=trace_id,
                name=name,
            )
