from typing import Dict, Any, Optional
from app.client.azure_openai import AzureOpenAILLM
from app.utils.prompt_loader import PromptLoader
from app.models.rubric import RubricItemResult


class StructureEvaluator:
    """서론/본론/결론 구조 평가 체인 (PromptLoader + AzureOpenAI)"""

    def __init__(self, client: Optional[AzureOpenAILLM] = None):
        self.client = client or AzureOpenAILLM()
        self.prompt_loader = PromptLoader()

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
                    f"[Previous section summary]\n{previous_summary}\n\n[Current section]\n{text}"
                )
            else:
                user_content = text

            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_content},
            ]

            response = await self.client.generate_json(
                messages=messages,
                json_schema=self._get_schema(),
            )

            content = response["content"]
            if isinstance(content, str):
                import json as _json
                content = _json.loads(content)

            parsed = RubricItemResult(**content)
            result = parsed.model_dump()
            result["token_usage"] = response.get("usage", {})
            result["evaluation_type"] = "structure_chain"
            return result

        except Exception as e:
            return {
                "rubric_item": rubric_item,
                "score": 0,
                "corrections": [],
                "feedback": f"구조 평가 중 오류 발생: {str(e)}",
                "error": str(e),
                "evaluation_type": "structure_chain",
                "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
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

        total_usage = {
            "prompt_tokens": sum(x.get("token_usage", {}).get("prompt_tokens", 0) for x in [intro_res, body_res, concl_res]),
            "completion_tokens": sum(x.get("token_usage", {}).get("completion_tokens", 0) for x in [intro_res, body_res, concl_res]),
            "total_tokens": sum(x.get("token_usage", {}).get("total_tokens", 0) for x in [intro_res, body_res, concl_res]),
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
