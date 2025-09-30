import json
import logging
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

            response = await self.client.run_azure_openai(
                messages=messages,
                json_schema=self._get_schema(),
                name=f"structure_{rubric_item}",
            )

            content = response["content"]
            usage = response.get("usage", {})
            logger.info(f"📥 Received LLM response for {rubric_item} - tokens: {usage.get('total_tokens', 'unknown')}")
            
            if isinstance(content, str):
                content = json.loads(content)

            # 빈 content 체크
            if not content or content == {}:
                logger.error(f"❌ Empty content received from LLM for {rubric_item} evaluation")
                logger.debug(f"Full response: {response}")
                return {
                    "rubric_item": rubric_item,
                    "score": 0,
                    "corrections": [],
                    "feedback": f"{rubric_item} evaluation failed - empty response from AI model",
                    "token_usage": usage,
                    "evaluation_type": "structure_chain"
                }

            logger.debug(f"Parsing {rubric_item} response content: {content}")
            parsed = RubricItemResult(**content)
            result = parsed.model_dump()
            result["token_usage"] = usage
            result["evaluation_type"] = "structure_chain"
            
            logger.info(f"✅ {rubric_item} evaluation completed - score: {result['score']}, corrections: {len(result['corrections'])}")
            return result

        except Exception as exc:  # noqa: BLE001
            logger.error(f"💥 Structure evaluation FAILED for {rubric_item}: {type(exc).__name__}: {exc}")
            logger.exception("Full exception details for %s", rubric_item)
            return {
                "rubric_item": rubric_item,
                "score": 1,  # Give a neutral score instead of 0
                "corrections": [],
                "feedback": f"{rubric_item} 평가 중 기술적 문제가 발생했습니다. 다시 시도해 주세요.",
                "error": str(exc),
                "evaluation_type": "structure_chain",
                "score": 0,
                "corrections": [],
                "feedback": f"구조 평가 중 오류 발생: {exc}",
                "error": str(exc),
                "evaluation_type": "structure_chain",
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
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

        def _usage(component: Dict[str, Any], key: str) -> int:
            usage = component.get("token_usage", {})
            return int(usage.get(key, 0))

        total_usage = {
            "prompt_tokens": sum(_usage(section, "prompt_tokens") for section in (intro_res, body_res, concl_res)),
            "completion_tokens": sum(_usage(section, "completion_tokens") for section in (intro_res, body_res, concl_res)),
            "total_tokens": sum(_usage(section, "total_tokens") for section in (intro_res, body_res, concl_res)),
        }

        return {
            "introduction": intro_res,
            "body": body_res,
            "conclusion": concl_res,
            "token_usage_total": total_usage,
            "evaluation_type": "structure_chain",
        }


# 기존 함수 시그니처 유지용 래퍼
async def run_structure_chain(intro: str, body: str, conclusion: str, level: str = "Basic") -> Dict[str, Any]:
    evaluator = StructureEvaluator()
    return await evaluator.run_structure_chain(intro=intro, body=body, conclusion=conclusion, level=level)
