import json
import logging
import time
from typing import Any, Dict, Optional

from app.client.bootstrap import build_llm
from app.models.rubric import RubricItemResult
from app.utils.prompt_loader import PromptLoader
from app.utils.tracer import LLM

logger = logging.getLogger(__name__)


class StructureEvaluator:
    """서론/본론/결론 구조 평가 체인 (PromptLoader + AzureOpenAI)"""

    def __init__(self, client: Optional[LLM] = None, loader: Optional[PromptLoader] = None) -> None:
        self.client = client or build_llm()
        # Use provided PromptLoader if given; otherwise create a new one.
        self.prompt_loader = loader or PromptLoader()

    def _get_schema(self) -> Dict[str, Any]:
        return RubricItemResult.model_json_schema()

    async def _evaluate_section(
        self,
        *,
        rubric_item: str,
        text: str,
        level: str = "Basic",
        previous_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            # Clean text input before processing
            text = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
            
            system_message = self.prompt_loader.load_prompt(rubric_item, level)
            # 이전 섹션 요약을 사용자 메시지 컨텍스트로 첨부(있을 경우)
            if previous_summary:
                user_content = (
                    f"""[Previous section summary]
{previous_summary}

[Current section]
{text}"""
                )
            else:
                user_content = text

            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_content},
            ]

            # 실행 시간 측정 시작
            start_time = time.time()
            
            response = await self.client.run_azure_openai(
                messages=messages,
                json_schema=self._get_schema(),
                name=f"structure_{rubric_item}",
                prompt_key=rubric_item,
                prompt_meta={
                    "evaluation_type": "structure_chain",
                    "level": level,
                    "section": rubric_item,
                    "text_length": len(text),
                    "has_previous_context": previous_summary is not None,
                    "prompt_source": "local_file",
                    "prompt_file": f"{rubric_item}_{level.lower()}",
                }
            )
            
            # 실행 시간 측정 종료 및 출력
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"LLM execution time for {rubric_item}: {execution_time:.3f} seconds")
            
            # 토큰 사용량 로깅 (가격 추적용)
            token_usage = response.get("usage", {})
            if token_usage:
                print(f"Token usage for {rubric_item} - Prompt: {token_usage.get('prompt_tokens', 0)}, "
                      f"Completion: {token_usage.get('completion_tokens', 0)}, "
                      f"Total: {token_usage.get('total_tokens', 0)}")

            content = response["content"]
            logger.info(f"Structure LLM response content for {rubric_item}: {content}")
            
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error for {rubric_item}: {e}")
                    logger.error(f"Raw content: {content}")
                    return {
                        "rubric_item": rubric_item,
                        "score": 0,
                        "corrections": [],
                        "feedback": f"{rubric_item} evaluation failed - invalid JSON response from AI model",
                        "evaluation_type": "structure_chain",
                        "json_error": str(e)
                    }

            # 빈 content 체크
            if not content or content == {}:
                logger.warning("Empty content received from LLM for %s evaluation", rubric_item)
                return {
                    "rubric_item": rubric_item,
                    "score": 0,
                    "corrections": [],
                    "feedback": f"{rubric_item} evaluation failed - empty response from AI model",
                    "evaluation_type": "structure_chain"
                }

            parsed = RubricItemResult(**content)
            result = parsed.model_dump()
            result["evaluation_type"] = "structure_chain"
            return result

        except Exception as exc:  # noqa: BLE001
            logger.exception("Structure evaluation failed for %s", rubric_item)
            return {
                "rubric_item": rubric_item,
                "score": 0,
                "corrections": [],
                "feedback": f"{rubric_item} 평가 중 기술적 문제가 발생했습니다. 다시 시도해 주세요.",
                "error": str(exc),
                "evaluation_type": "structure_chain"
            }

    async def run_structure_chain(
        self,
        *,
        intro: str,
        body: str,
        conclusion: str,
        level: str = "Basic",
    ) -> Dict[str, Any]:
        """서론→본론→결론 순으로 평가하며, 이전 섹션 요약(피드백)을 다음 섹션 컨텍스트로 제공."""
        intro_res = await self._evaluate_section(
            rubric_item="introduction", text=intro, level=level
        )
        body_res = await self._evaluate_section(
            rubric_item="body",
            text=body,
            level=level,
            previous_summary=intro_res.get("feedback"),
        )
        concl_res = await self._evaluate_section(
            rubric_item="conclusion",
            text=conclusion,
            level=level,
            previous_summary=body_res.get("feedback"),
        )

        return {
            "introduction": intro_res,
            "body": body_res,
            "conclusion": concl_res,
            "evaluation_type": "structure_chain",
        }


# 기존 함수 시그니처 유지용 래퍼
async def run_structure_chain(intro: str, body: str, conclusion: str, level: str = "Basic") -> Dict[str, Any]:
    evaluator = StructureEvaluator()
    return await evaluator.run_structure_chain(intro=intro, body=body, conclusion=conclusion, level=level)
